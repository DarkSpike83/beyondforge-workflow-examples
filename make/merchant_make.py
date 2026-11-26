"""Audit an export on the customer's account, then deliver a minimal receipt to Make."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from importlib import import_module
import json
import os
from pathlib import Path
import re
import sqlite3
import ssl
import sys
from urllib import error, request
from urllib.parse import urlencode
from xml.etree import ElementTree

from run_workflow import Apify, Incomplete, SameEndpoint, encoded, execute, fingerprint, open_journal

ACTOR_ID = "kiyhZwamPiGAxKkcw"
ACTOR_PATH = "acts/" + ACTOR_ID
START_RATE = Decimal("0.00005")
OFFER_RATE = Decimal("0.0009")
GOOGLE_ID = "{http://base.google.com/ns/1.0}id"
PROOF = "exact-sku-price-and-start-v1"


def verified_opener():
    context = None
    if sys.platform == "win32":
        try:
            truststore = import_module("truststore")
        except ModuleNotFoundError as exc:
            if exc.name != "truststore":
                raise Incomplete("Unable to load the Windows TLS verifier.") from None
        except ImportError:
            raise Incomplete("Unable to load the Windows TLS verifier.") from None
        else:
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if context is None:
        context = ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise Incomplete("TLS requires certificate and hostname verification.")
    return request.build_opener(SameEndpoint, request.HTTPSHandler(context=context))


class MerchantAPI(Apify):
    def __init__(self, token):
        super().__init__(token)
        self.opener = verified_opener()

    def start(self, flow, payload, budget):
        query = urlencode({"maxTotalChargeUsd": budget, "restartOnError": "false", "memory": 256})
        return self.request(ACTOR_PATH + "/runs?" + query, payload)["data"]["id"]


def offer_keys(payload):
    if not isinstance(payload, dict) or set(payload) - {"offers", "feedXml", "maxResults"}:
        raise Incomplete("Use an immutable inline offers or RSS XML snapshot and optional maxResults.")
    if ("offers" in payload) == ("feedXml" in payload) or len(encoded(payload)) > 8_000_000:
        raise Incomplete("Supply one inline source within 8 MB.")
    if "offers" in payload:
        items = payload["offers"]
        if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
            raise Incomplete("Expected an array of product offers.")
        ids = [item.get("id") for item in items]
    else:
        raw = payload["feedXml"]
        if not isinstance(raw, str) or "\x00" in raw or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b",raw,re.I):
            raise Incomplete("Use RSS XML without document types or entity declarations.")
        try:
            root = ElementTree.fromstring(raw)
        except (ElementTree.ParseError, ValueError) as e:
            raise Incomplete("Malformed RSS XML.") from e
        channels = root.findall("channel")
        if root.tag != "rss" or len(channels) != 1 or channels[0].find("title") is None:
            raise Incomplete("Use one RSS channel with a title.")
        items = channels[0].findall("item")
        if sum(node.tag.rsplit("}", 1)[-1] in {"item", "entry"} for node in root.iter()) != len(items):
            raise Incomplete("An item or entry is outside the supported RSS structure.")
        ids = []
        for item in items:
            nodes = item.findall(GOOGLE_ID) + item.findall("id")
            if len(nodes) != 1 or len(nodes[0]):
                raise Incomplete("Each offer must have exactly one plain product ID.")
            ids.append(nodes[0].text)
    if len(ids) > 5000 or any(not isinstance(value, str) or not value.strip() for value in ids):
        raise Incomplete("Provide at most 5000 products, each with a nonempty product ID.")
    keys = {"id:" + value.strip() for value in ids}
    if len(keys) != len(ids):
        raise Incomplete("Normalize the feed to one row per unique product ID before the audit.")
    return keys


def check_catalog_terms(api, expected, cap):
    info = api.request(ACTOR_PATH)["data"]
    if info.get("id") != ACTOR_ID or info.get("isPublic") is not True or info.get("username") != "beyondforge" or info.get("name") != "merchant-feed-preflight":
        raise Incomplete("Cannot verify the intended public Merchant Actor.")
    now = datetime.now(timezone.utc)
    choices = []
    for terms in info.get("pricingInfos", []):
        started = datetime.fromisoformat(terms["startedAt"].replace("Z", "+00:00"))
        if started <= now:
            choices.append((started, terms))
    if not choices:
        raise Incomplete("No effective pricing entry is available.")
    terms = max(choices,key=lambda pair:pair[0])[1]
    events = terms.get("pricingPerEvent", {}).get("actorChargeEvents", {})
    expected_rates = {"apify-actor-start": START_RATE, "offer-audited": OFFER_RATE}
    pass_through = terms.get("isPPEPlatformUsagePaidByUser")
    if (terms.get("pricingModel") != "PAY_PER_EVENT" or (pass_through is not None and pass_through is not False)
            or set(events) != set(expected_rates)
            or any(e.get("eventTieredPricingUsd") is not None or type(e.get("eventPriceUsd")) not in (float,int,Decimal)
                   or Decimal(str(e["eventPriceUsd"])) != expected_rates[k] for k,e in events.items())):
        raise Incomplete("Pricing changed. Review the current Merchant listing before dispatch.")
    minimum = terms.get("minimalMaxTotalChargeUsd") or info.get("minimalMaxTotalChargeUsd") or 0
    if Decimal(str(minimum)) > cap:
        raise Incomplete("Budget is below the Actor's current minimum.")
    if expected > 25:
        profile = api.request("users/me")["data"]
        # Apify's profile marks effective paying status at the top level.
        # The plan flag is an override for accounts without a subscription.
        # It can be false on a paid account. Never infer entitlement from the plan name.
        payer = profile.get("isPaying")
        plan = profile.get("plan")
        override = plan.get("isPayingCustomer") if isinstance(plan,dict) else None
        if payer is not True and not (payer is None and override is True):
            raise Incomplete("More than 25 rows require confirming paying status via the account profile.")


def verify_run(api, result, cap, expected):
    run = api.status(result["runId"])
    options = run.get("options", {})
    counters = run.get("chargedEventCounts", {})
    if (run.get("id") != result["runId"] or run.get("actId") != ACTOR_ID or run.get("status") != "SUCCEEDED"
            or options.get("memoryMbytes") != 256 or options.get("restartOnError") is True
            or Decimal(str(options.get("maxTotalChargeUsd"))) != cap
            or not isinstance(counters,dict) or any(type(n) is not int or n<0 for n in counters.values())
            or counters.get("apify-actor-start") != 1 or counters.get("offer-audited", 0) != expected
            or any(value for name,value in counters.items() if name not in {"apify-actor-start","offer-audited"})):
        raise Incomplete("Run identity, applied cap, memory or event counts failed verification. Keep export on hold.")

def prepare(db):
    with db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("""CREATE TABLE IF NOT EXISTS make_merchant_receipts (
            scope TEXT NOT NULL, export_id TEXT NOT NULL, manifest TEXT NOT NULL,
            receipt TEXT, acknowledged INTEGER NOT NULL DEFAULT 0, proof TEXT,
            PRIMARY KEY(scope, export_id))""")
        if "proof" not in {row[1] for row in db.execute("PRAGMA table_info(make_merchant_receipts)")}:
            db.execute("ALTER TABLE make_merchant_receipts ADD COLUMN proof TEXT")


def get_row(db, scope, export_id):
    return db.execute(
        "SELECT * FROM make_merchant_receipts WHERE scope=? AND export_id=?", (scope, export_id)
    ).fetchone()


def budget_text(value):
    cap = Decimal(str(value))
    if not cap.is_finite() or not 0 < cap <= 10:
        raise Incomplete("Set an explicit budget greater than zero and at most 10 USD.")
    return format(cap.normalize(), "f")


def make_receipt(result, scope, export_id, keys):
    expected = len(keys)
    rows = result["rows"]
    summary = result["summary"]
    counts = [summary.get(k) for k in ("inputOffers", "uniqueOffers", "matched", "returned")]
    if any(type(n) is not int or n != expected for n in counts) or len(rows) != expected:
        raise Incomplete("Keep export on hold. Delivered offer count differs from the export manifest.")
    if {row["id"] for row in rows} != keys:
        raise Incomplete("Keep export on hold. Delivered product IDs differ from the export manifest.")
    flagged = sum(row["status"] == "review" for row in rows)
    decision = "HOLD_EXPORT" if flagged else ("READY_FOR_REVIEW" if expected else "EMPTY_CATALOG")
    if decision != result["decision"]:
        raise Incomplete("Keep export on hold. Decision and rows disagree.")
    receipt = {
        "schema": "merchant-delivery-v1", "operationKey": fingerprint(["export", scope, export_id]),
        "runRef": fingerprint(["apify-run", result["runId"]]),
        "expected": expected, "delivered": len(rows), "flagged": flagged, "decision": decision,
    }
    return {**receipt, "receiptId": fingerprint(receipt)}


def audit(db, api, scope, export_id, payload, cap, expected, wait=120):
    if not scope or not export_id or len(scope)>160 or len(export_id)>160:
        raise Incomplete("Supply a stable scope and immutable export ID, up to 160 characters each.")
    if type(expected) is not int or not 0 <= expected <= 5000:
        raise Incomplete("Expected distinct offers must be a whole number from 0 to 5000.")
    keys = offer_keys(payload)
    if len(keys) != expected:
        raise Incomplete("Expected distinct offers differ from the inline export.")
    if "maxResults" in payload and (type(payload["maxResults"]) is not int or not max(1,expected) <= payload["maxResults"] <= 5000):
        raise Incomplete("Set maxResults from 1 to 5000 and high enough to deliver the whole export.")
    cap = budget_text(cap)
    amount = Decimal(cap)
    if amount < START_RATE + expected * OFFER_RATE:
        raise Incomplete("Budget cannot cover the complete export at the published price.")
    manifest = fingerprint([payload, cap, expected])
    previous = db.execute("SELECT state FROM operations WHERE flow='merchant' AND scope=? AND operation=?",
                          (scope,export_id)).fetchone()
    if previous is None:
        check_catalog_terms(api,expected,amount)
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = get_row(db, scope, export_id)
        if row is None:
            db.execute("INSERT INTO make_merchant_receipts(scope,export_id,manifest) VALUES(?,?,?)",
                       (scope, export_id, manifest))
        elif row["manifest"] != manifest:
            raise Incomplete("Export ID already refers to different input, budget or expected coverage.")
        elif row["receipt"] and row["proof"]==PROOF:
            return json.loads(row["receipt"])
    result = execute(db, api, "merchant", scope, export_id, payload, cap, wait)
    receipt = make_receipt(result, scope, export_id, keys)
    verify_run(api,result,amount,expected)
    with db:
        db.execute("UPDATE make_merchant_receipts SET receipt=?,proof=? WHERE scope=? AND export_id=?",
                   (encoded(receipt).decode(), PROOF, scope, export_id))
    return receipt


def send_receipt(receipt):
    url = os.environ.get("CUSTOMER_MAKE_WEBHOOK", "")
    key = os.environ.get("CUSTOMER_MAKE_WEBHOOK_KEY", "")
    if not re.fullmatch(r"https://hook(?:\.[a-z]{2}\d+)?\.make\.com/[A-Za-z0-9_-]{16,128}", url) or not key:
        raise Incomplete("Configure your regional Make HTTPS webhook and its private API key.")
    req = request.Request(url, data=encoded(receipt), headers={
        "Content-Type": "application/json", "x-make-apikey": key,
    })
    try:
        with verified_opener().open(req, timeout=30) as response:
            if response.status != 200 or response.headers.get_content_type() != "application/json":
                raise Incomplete("Make has not confirmed the receipt. Retry delivery only.")
            raw = response.read(2049)
            if len(raw) > 2048:
                raise Incomplete("Unexpected Make response size.")
            return json.loads(raw)
    except (OSError, ValueError, error.HTTPError):
        raise Incomplete("No valid Make response. Retry delivery only.") from None


def deliver(db, scope, export_id, send=send_receipt):
    row = get_row(db, scope, export_id)
    if not row or not row["receipt"] or row["proof"]!=PROOF:
        raise Incomplete("No verified receipt. Keep the export on hold.")
    receipt = json.loads(row["receipt"])
    if row["acknowledged"]:
        return "ALREADY_ACKNOWLEDGED"
    ack = send(receipt)
    if ack != {"decision": receipt["decision"], "receiptId": receipt["receiptId"]}:
        raise Incomplete("Missing matching journal acknowledgement. Retry delivery only.")
    with db:
        db.execute("UPDATE make_merchant_receipts SET acknowledged=1 WHERE scope=? AND export_id=?",
                   (scope, export_id))
    return "ACKNOWLEDGED"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("audit", "deliver"))
    p.add_argument("--workspace", required=True, type=Path)
    p.add_argument("--scope", required=True)
    p.add_argument("--export-id", required=True)
    p.add_argument("--input", type=Path)
    p.add_argument("--expected", type=int)
    p.add_argument("--max-usd")
    p.add_argument("--accept-cloud-run", action="store_true")
    p.add_argument("--send-to-make", action="store_true")
    args = p.parse_args()
    if not args.workspace.is_dir():
        raise Incomplete("Select an existing private workspace in the customer's environment.")
    if args.action == "audit" and not (args.input and args.max_usd and args.accept_cloud_run):
        raise Incomplete("The audit requires an input, an explicit budget and --accept-cloud-run.")
    if args.action == "deliver" and not args.send_to_make:
        raise Incomplete("Explicitly request delivery with --send-to-make.")
    db = open_journal(args.workspace/"workflow-state.sqlite")
    try:
        prepare(db)
        if args.action == "audit":
            with args.input.open("rb") as f:
                content = f.read(8_000_001)
            if len(content) > 8_000_000:
                raise Incomplete("Input exceeds 8 MB.")
            receipt = audit(db, MerchantAPI(os.environ.get("CUSTOMER_APIFY_TOKEN")), args.scope,
                            args.export_id, json.loads(content), args.max_usd, args.expected)
            print(receipt["decision"])
        if args.send_to_make:
            print(deliver(db, args.scope, args.export_id))
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except (Incomplete, InvalidOperation, ValueError, TypeError, OSError, KeyError, sqlite3.Error) as exc:
        sys.exit(str(exc) if isinstance(exc, Incomplete) else "Operation incomplete. Inspect the private journal.")
