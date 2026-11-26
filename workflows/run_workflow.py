"""Customer-side integration examples for three public BeyondForge Actors. Python 3.10+."""
import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path


ACTORS = {
    "merchant": "merchant-feed-preflight",
    "rss": "rss-revision-ledger",
    "migration": "migration-redirect-audit",
}
TERMINAL_ERRORS = {"FAILED", "TIMED-OUT", "ABORTED"}


class Incomplete(Exception):
    """Operator attention required. Never restart a billable run automatically."""


def encoded(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]+", value):
        raise Incomplete("Missing or invalid Apify resource identifier.")
    return value


def valid_digest(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def checked_events(flow, run, event, count):
    ledger = run.get("chargedEventCounts")
    if not isinstance(ledger,dict) or any(type(n) is not int or n < 0 for n in ledger.values()):
        raise Incomplete("Platform event counters unavailable. Resume this operation after settlement.")
    business = {k:v for k,v in ledger.items() if v and not (flow in ("merchant","rss") and k == "apify-actor-start")}
    if business != ({event:count} if count else {}):
        raise Incomplete("Commercial event counts differ from the verified delivery. Inspect this run.")


def checked_traces(report, overview, mode):
    fields = ("kind", "schemaVersion", "demoCase", "outcome", "outputMode", "mappedUrls",
              "fullyTracedUrls", "flaggedUrls", "findingCounts", "comparison")
    if any(k not in report or k not in overview or report[k] != overview[k] for k in fields):
        raise Incomplete("Dataset overview and report disagree.")
    traces = report.get("results")
    expected = report["mappedUrls"] if mode == "audit" else min(3, report["mappedUrls"])
    if (not isinstance(traces, list) or len(traces) != expected or
            len({t["source"] for t in traces}) != expected or
            any(not t.get("source") or not t.get("expected") or not isinstance(t.get("findings"),list)
                for t in traces)):
        raise Incomplete("Missing or duplicated report traces.")
    if mode == "audit":
        if (any(not isinstance(t.get("hops"),list) or "finalStatus" not in t or "finalUrl" not in t for t in traces)
                or sum(bool(t["findings"]) for t in traces) != report["flaggedUrls"]
                or dict(Counter(f for t in traces for f in t["findings"])) != report["findingCounts"]):
            raise Incomplete("Detailed migration findings disagree with the overview.")


def checked_checkpoint(summary, rows, checkpoint):
    entries = checkpoint.get("entries")
    field_names = {"title","link","content","published","updated"}
    if (checkpoint.get("version") != 1 or not isinstance(entries,dict)
            or not valid_digest(checkpoint.get("feedKey")) or len(entries) != summary.get("entries")
            or summary.get("unchanged") != len(entries) - len(rows)
            or type(summary.get("previousOnly")) is not int or summary["previousOnly"] < 0):
        raise Incomplete("Checkpoint and feed summary disagree.")
    if (any(not valid_digest(key) or not isinstance(fields,dict) or set(fields) != field_names
            or not all(valid_digest(d) for d in fields.values()) for key,fields in entries.items())
            or any(row.get("id") not in entries for row in rows)):
        raise Incomplete("Checkpoint hashes or delivered entry identities are invalid.")


class SameEndpoint(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Incomplete("The official API redirected. Review the operation before continuing.")


class Apify:
    def __init__(self, token):
        if not token:
            raise Incomplete("Set CUSTOMER_APIFY_TOKEN in your own runtime secret store.")
        self.opener = urllib.request.build_opener(SameEndpoint)
        self.headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}

    def request(self, path, payload=None):
        url = "https://api.apify.com/v2/" + path
        request = urllib.request.Request(url, headers=self.headers,
                                         data=None if payload is None else encoded(payload))
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read(12_000_001)
                if len(raw) > 12_000_000:
                    raise Incomplete("API response exceeded the local client limit.")
                return json.loads(raw)
        except urllib.error.HTTPError as error:
            raise Incomplete(f"Apify API returned HTTP {error.code}.") from None
        except (OSError, ValueError):
            raise Incomplete("No valid API response. Preserve the operation journal.") from None

    def start(self, flow, payload, budget):
        query = urllib.parse.urlencode({"maxTotalChargeUsd": budget, "restartOnError": "false"})
        return self.request(f"acts/beyondforge~{ACTORS[flow]}/runs?{query}", payload)["data"]["id"]

    def status(self, run_id):
        return self.request("actor-runs/" + identifier(run_id))["data"]

    def record(self, run, key):
        store = identifier(run["defaultKeyValueStoreId"])
        return self.request(f"key-value-stores/{store}/records/{key}")

    def rows(self, run, expected):
        data_id = identifier(run["defaultDatasetId"])
        if type(expected) is not int or not 0 <= expected <= 5000:
            raise Incomplete("Unexpected dataset row count.")
        records = []
        while len(records) < expected:
            page = self.request(f"datasets/{data_id}/items?format=json&offset={len(records)}&limit=100")
            if not isinstance(page, list) or not page or len(records) + len(page) > expected:
                raise Incomplete("Dataset changed or a page was missing.")
            records.extend(page)
        extra = self.request(f"datasets/{data_id}/items?format=json&offset={expected}&limit=1")
        if extra != []:
            raise Incomplete("Dataset contains unexpected rows.")
        return records


def checked_output(api, flow, run, summary, payload):
    if summary.get("outcome") != "complete":
        raise Incomplete("Actor reports an incomplete delivery. Inspect RUN_SUMMARY and charges.")
    checkpoint = None
    if flow == "migration":
        rows = api.rows(run, 1)
        report = api.record(run, "REPORT")
        expected_mode = "audit" if "redirectMap" in payload else "preview"
        expected_events = int(expected_mode == "audit")
        if (summary.get("deliveredReports") != 1 or fingerprint(report) != summary.get("reportSha256")
                or rows[0].get("reportSha256") != summary["reportSha256"]
                or report.get("kind") != "migration-redirect-audit"
                or type(report.get("mappedUrls")) is not int or report["mappedUrls"] < 1
                or report.get("mappedUrls") != report.get("fullyTracedUrls")
                or type(report.get("flaggedUrls")) is not int or not 0 <= report["flaggedUrls"] <= report["mappedUrls"]
                or (report["flaggedUrls"] == 0) != (report.get("outcome") == "clean")
                or report.get("outcome") not in ("clean", "findings")
                or report.get("outputMode") != expected_mode or summary.get("outputMode") != expected_mode
                or summary.get("chargedEvents") != expected_events
                or summary.get("eventName") != ("migration-audited" if expected_events else None)):
            raise Incomplete("Coverage, mode or report fingerprint failed verification.")
        checked_traces(report, rows[0], expected_mode)
        checked_events(flow, run, "migration-audited", expected_events)
        if report["outputMode"] == "preview":
            decision = "DEMO_ONLY"
        else:
            decision = "HOLD_RELEASE" if report["flaggedUrls"] else "READY_FOR_SIGN_OFF"
        return {"decision": decision, "overview": rows[0], "report": report}, None

    if type(summary.get("matched")) is not int or summary.get("returned") != summary["matched"]:
        raise Incomplete("Summary counts do not describe a complete dataset.")
    rows = api.rows(run, summary["returned"])
    if len({row["id"] for row in rows}) != len(rows):
        raise Incomplete("Duplicate result identity. Inspect the source run.")
    if flow == "merchant":
        if (summary.get("uniqueOffers") != len(rows) or type(summary.get("inputOffers")) is not int
                or summary["inputOffers"] < len(rows) or summary.get("event") != "offer-audited"):
            raise Incomplete("Catalog totals or event type disagree with the delivered rows.")
        if any(row.get("status") not in ("review", "passed_checks")
               or not isinstance(row.get("findings"), list)
               or bool(row["findings"]) != (row["status"] == "review") for row in rows):
            raise Incomplete("Unrecognized audit status.")
        if not rows:
            decision = "EMPTY_CATALOG"
        else:
            decision = "HOLD_EXPORT" if any(r["status"] == "review" for r in rows) else "READY_FOR_REVIEW"
    else:
        if summary.get("checkpointReady") is not True:
            raise Incomplete("No complete checkpoint. Keep the previous baseline.")
        checkpoint = api.record(run, "CHECKPOINT")
        checked_checkpoint(summary, rows, checkpoint)
        if any(row.get("change") not in ("edited", "new") for row in rows):
            raise Incomplete("Unrecognized feed change type.")
        if summary.get("event") != "feed-change":
            raise Incomplete("Unexpected RSS event type.")
        if rows:
            decision = "REVIEW_CHANGES"
        elif summary["previousOnly"]:
            decision = "FEED_WINDOW_CHANGED"
        else:
            decision = "UNCHANGED" if summary["entries"] else "EMPTY_FEED"
    checked_events(flow, run, summary["event"], len(rows))
    return {"decision": decision, "rows": rows}, checkpoint


def open_journal(path):
    db = sqlite3.connect(path, timeout=10)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS operations (
          flow TEXT, scope TEXT, operation TEXT, signature TEXT NOT NULL, state TEXT NOT NULL,
          run_id TEXT, result TEXT, PRIMARY KEY (flow, scope, operation));
        CREATE UNIQUE INDEX IF NOT EXISTS active_scope ON operations(flow,scope)
          WHERE state IN ('submitting','started');
        CREATE TABLE IF NOT EXISTS checkpoints (
          scope TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    return db


def execute(db, api, flow, scope, operation, payload, budget, wait=120):
    if not isinstance(payload, dict):
        raise Incomplete("Provide an Actor input object.")
    if flow == "migration" and payload.get("billDemoReport") not in (None, False):
        raise Incomplete("This workflow only supports unbilled synthetic previews.")
    if flow == "rss" and ({"baseline", "completionReceipt"} & payload.keys()):
        raise Incomplete("This workflow manages the baseline and leaves paid receipts disabled.")
    signature = fingerprint([payload, budget])
    key = (flow, scope, operation)
    with db:
        db.execute("BEGIN IMMEDIATE")
        op = db.execute("SELECT * FROM operations WHERE flow=? AND scope=? AND operation=?", key).fetchone()
        if op:
            if op["signature"] != signature:
                raise Incomplete("Operation already exists with different input or budget.")
            if op["state"] == "done":
                return json.loads(op["result"])
            if op["state"] != "started":
                raise Incomplete("Review the prior submission and charges before retrying.")
            run_id = op["run_id"]
        else:
            if db.execute("SELECT 1 FROM operations WHERE flow=? AND scope=? AND state IN ('submitting','started')",
                          (flow, scope)).fetchone():
                raise Incomplete("An earlier operation in this scope still requires reconciliation.")
            if flow == "rss":
                previous = db.execute("SELECT value FROM checkpoints WHERE scope=?", (scope,)).fetchone()
                if previous:
                    if "previousXml" in payload:
                        raise Incomplete("With an established baseline, omit previousXml.")
                    payload = {**payload, "baseline": json.loads(previous[0])}
            db.execute("INSERT INTO operations(flow,scope,operation,signature,state) VALUES (?,?,?,?,'submitting')",
                       (*key, signature))
            run_id = None
    if run_id is None:
        run_id = identifier(api.start(flow, payload, budget))
        with db:
            db.execute("UPDATE operations SET state='started',run_id=? WHERE flow=? AND scope=? AND operation=?",
                       (run_id, *key))
    deadline = time.monotonic() + wait
    while True:
        run = api.status(run_id)
        if run.get("id") != run_id:
            raise Incomplete("Unexpected run identity.")
        if run["status"] == "SUCCEEDED":
            break
        if run["status"] in TERMINAL_ERRORS:
            with db:
                db.execute("UPDATE operations SET state='failed' WHERE flow=? AND scope=? AND operation=?", key)
            raise Incomplete(f"Run {run_id} ended {run['status']}. Inspect delivery and charges.")
        if time.monotonic() >= deadline:
            raise Incomplete(f"Run {run_id} is pending. Repeat the same operation to resume reading.")
        time.sleep(2)
    summary = api.record(run, "RUN_SUMMARY")
    if summary.get("outcome") in {"budget_limit","result_limit","free_limit","invalid_input","source_error"}:
        with db:
            db.execute("UPDATE operations SET state='incomplete' WHERE flow=? AND scope=? AND operation=?", key)
        raise Incomplete(f"Run {run_id} ended with {summary['outcome']}. Inspect any partial deliveries.")
    result, checkpoint = checked_output(api, flow, run, summary, payload)
    result.update(runId=run_id, summary=summary)
    with db:
        changed = db.execute("UPDATE operations SET state='done',result=? WHERE flow=? AND scope=? AND operation=? AND state='started'",
                             (encoded(result).decode(), *key))
        if changed.rowcount and checkpoint is not None:
            db.execute("INSERT OR REPLACE INTO checkpoints VALUES (?,?)", (scope, encoded(checkpoint).decode()))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=ACTORS)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--scope", required=True, help="Stable customer-private feed/site alias")
    parser.add_argument("--operation", required=True, help="Unique observation or completed export ID")
    parser.add_argument("--workspace", required=True, type=Path, help="Existing private customer directory")
    parser.add_argument("--max-usd", required=True, help="Explicit per-run maximum commercial charge")
    parser.add_argument("--accept-cloud-run", action="store_true", help="Permit one real run with your account")
    args = parser.parse_args()
    cap = Decimal(args.max_usd)
    if not cap.is_finite() or not 0 < cap <= 10 or not args.accept_cloud_run:
        raise Incomplete("Real runs need --accept-cloud-run and a positive cap up to 10 USD.")
    if not args.workspace.is_dir():
        raise Incomplete("Create a private workspace in your own environment first.")
    if args.input.stat().st_size > 8_000_000:
        raise Incomplete("Input exceeds 8 MB.")
    api = Apify(os.environ.get("CUSTOMER_APIFY_TOKEN"))
    db = open_journal(args.workspace / "workflow-state.sqlite")
    try:
        result = execute(db, api, args.flow, args.scope, args.operation,
                         json.loads(args.input.read_text(encoding="utf-8-sig")), format(cap.normalize(), "f"))
    finally:
        db.close()
    # stdout contains decisions only. Read full records inside the customer's private workspace.
    print(json.dumps({"decision": result["decision"], "runId": result["runId"]}))


if __name__ == "__main__":
    try:
        main()
    except (Incomplete, InvalidOperation, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(str(exc) if isinstance(exc, Incomplete) else "Workflow failed. Inspect the private input and journal.",
              file=sys.stderr)
        sys.exit(2)
