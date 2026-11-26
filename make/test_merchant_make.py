"""Offline conformance tests. The blueprint interpreter covers only its declared filters."""
from concurrent.futures import ThreadPoolExecutor
import json
from copy import deepcopy
from math import floor
from pathlib import Path
import re
import ssl
from uuid import uuid4
import threading
import unittest
from unittest.mock import Mock, patch

import merchant_make as integration
from run_workflow import Incomplete, open_journal


DIR = Path(__file__).resolve().parent
BLUEPRINT = json.loads((DIR / "merchant-feed-validation.blueprint.json").read_text())
OFFER = json.loads((DIR / "sample-offers.json").read_text())


class FixtureAPI:
    def __init__(self):
        self.starts = 0
        self.row = {"id": "id:MUG-RED", "status": "review", "findings": ["SALE_PRICE"]}
        self.items = [self.row]
        self.status_name = "SUCCEEDED"
        self.outcome = "complete"
        self.events = 1
        self.start_events = 1
        self.cap = "0.01"
        self.memory = 256
        self.profile = {"isPaying":False,"plan":{"id":"FREE","isPayingCustomer":False}}
        self.public_reads=[]
        self.actor = {"id": integration.ACTOR_ID, "name":"merchant-feed-preflight",
                      "username":"beyondforge", "isPublic":True, "pricingInfos":[{
                      "pricingModel":"PAY_PER_EVENT", "startedAt":"2026-01-01T00:00:00Z",
                      "pricingPerEvent":{"actorChargeEvents":{"apify-actor-start":{"eventPriceUsd":.00005},
                                                            "offer-audited":{"eventPriceUsd":.0009}}}}]}

    def request(self,path,payload=None):
        self.public_reads.append(path)
        if path==integration.ACTOR_PATH:
            return {"data":self.actor}
        if path=="users/me":
            return {"data":self.profile}
        raise AssertionError("Unexpected offline fixture request: "+path)

    def start(self, flow, payload, budget):
        self.starts += 1
        self.cap=budget
        return "SYNTHETICRUN"

    def status(self, run_id):
        return {"id": run_id, "actId":integration.ACTOR_ID,"status": self.status_name,
                "options":{"memoryMbytes":self.memory,"maxTotalChargeUsd":self.cap,"restartOnError":False},
                "chargedEventCounts": {"apify-actor-start": self.start_events, "offer-audited": self.events}}

    def record(self, run, key):
        count = len(self.items)
        return {"outcome": self.outcome, "matched": count, "returned": count,
                "uniqueOffers": count, "inputOffers": count, "event": "offer-audited"}

    def rows(self, run, expected):
        return self.items


def filter_value(raw, receipt):
    if not raw.startswith("{{"):
        return raw
    text = raw[2:-2]
    digest_length = re.fullmatch(r'length\(replace\(1\.(receiptId|operationKey|runRef); "/\[\^a-f0-9\]/g"; emptystring\)\)', text)
    if digest_length:
        return len(re.sub(r"[^a-f0-9]", "", receipt[digest_length[1]]))
    if text.startswith("length(1."):
        return len(receipt[text[9:-1]])
    if text.startswith("floor(1."):
        return floor(receipt[text[8:-1]])
    if text.endswith(" + 1"):
        return receipt[text[2:-4]] + 1
    return receipt[text.removeprefix("1.")]


def accepts_blueprint(receipt):
    def matches(clause):
        a, b = (filter_value(clause[k], receipt) for k in ("a", "b"))
        op = clause["o"]
        if op == "text:equal":
            return a == b
        a, b = float(a), float(b)
        if op == "number:equal":
            return a == b
        if op == "number:less":
            return a < b
        if op == "number:greater":
            return a > b
        raise AssertionError(op)
    try:
        return any(all(matches(c) for c in row) for row in BLUEPRINT["flow"][1]["filter"]["conditions"])
    except (ValueError, TypeError, KeyError):
        return False


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.path = DIR / ("test-" + uuid4().hex + ".sqlite")
        self.addCleanup(self.path.unlink, missing_ok=True)
        self.db = open_journal(self.path)
        self.addCleanup(self.db.close)
        integration.prepare(self.db)
        self.api = FixtureAPI()

    def audit(self, expected=1, **kwargs):
        return integration.audit(self.db, self.api, "EU", "E1", OFFER, "0.01", expected, **kwargs)

    def test_bad_price_holds_export_and_correlation(self):
        receipt = self.audit()
        self.assertEqual("HOLD_EXPORT", receipt["decision"])
        self.assertEqual(integration.fingerprint(["apify-run", "SYNTHETICRUN"]), receipt["runRef"])
        self.assertTrue(accepts_blueprint(receipt))
        self.assertEqual(set(receipt), {"schema","operationKey","runRef","expected","delivered","flagged","decision","receiptId"})
        self.assertNotIn("MUG-RED", str(receipt))

    def test_passed_and_empty(self):
        self.api.row.update(status="passed_checks", findings=[])
        self.assertEqual("READY_FOR_REVIEW", self.audit()["decision"])
        self.api.events, self.api.items = 0, []
        receipt = integration.audit(self.db, self.api, "EU", "E2", {"offers":[]}, "0.01", 0)
        self.assertEqual("EMPTY_CATALOG", receipt["decision"])
        self.assertTrue(accepts_blueprint(receipt))

    def test_missing_original_export_coverage(self):
        with self.assertRaises(Incomplete):
            self.audit(expected=2)
        self.assertIsNone(integration.get_row(self.db,"EU","E1"))
        self.assertEqual(self.api.starts,0)

    def test_partial_coverage_or_source_error(self):
        for index, outcome in enumerate(("source_error","budget_limit","free_limit","result_limit")):
            self.api.outcome = outcome
            with self.subTest(outcome=outcome), self.assertRaises(Incomplete):
                integration.audit(self.db,self.api,"EU",str(index),OFFER,"0.01",1)

    def test_paid_units_settle_only_for_verified_rows(self):
        self.api.events = 0
        with self.assertRaises(Incomplete):
            self.audit()
        self.api.events = 1
        self.assertTrue(accepts_blueprint(self.audit()))
        self.assertEqual(1,self.api.starts)

    def test_wrong_input_manifest_and_replay(self):
        r = self.audit()
        self.assertEqual(r,self.audit())
        with self.assertRaises(Incomplete):
            self.audit(2)
        with self.assertRaises(Incomplete):
            integration.audit(self.db,self.api,"EU","E1",OFFER,"0.02",1)
        self.assertEqual(self.api.starts,1)

    def test_post_timeout_will_not_repeat_actor(self):
        def no_reply(*unused):
            self.api.starts += 1
            raise TimeoutError("fixture only")
        with patch.object(self.api,"start",no_reply):
            with self.assertRaises(TimeoutError):
                self.audit()
        with self.assertRaises(Incomplete):
            self.audit()
        self.assertEqual(self.api.starts,1)

    def test_started_timeout_resumes_get_only(self):
        self.api.status_name = "RUNNING"
        with self.assertRaises(Incomplete):
            self.audit(wait=0)
        self.api.status_name = "SUCCEEDED"
        self.assertTrue(accepts_blueprint(self.audit()))
        self.assertEqual(self.api.starts,1)

    def test_reject_duplicate_dataset_identity(self):
        self.api.items = [self.api.row,self.api.row]
        self.api.events = 2
        payload={"offers":[{"id":"MUG-RED"},{"id":"MUG-BLUE"}]}
        with self.assertRaises(Incomplete):
            integration.audit(self.db,self.api,"EU","duplicate-output",payload,"0.01",2)
        self.assertEqual(1,self.api.starts)

    def test_concurrent_dispatch_claim(self):
        claimed, release = threading.Event(), threading.Event()
        def start(*unused):
            self.api.starts += 1
            claimed.set()
            if not release.wait(4):
                raise AssertionError("second worker did not release")
            return "SYNTHETICRUN"
        def run():
            db = open_journal(self.path)
            try:
                return integration.audit(db,self.api,"EU","E1",OFFER,"0.01",1)
            finally:
                db.close()
        with patch.object(self.api,"start",start), ThreadPoolExecutor(max_workers=1) as pool:
            worker = pool.submit(run)
            try:
                self.assertTrue(claimed.wait(4))
                with self.assertRaises(Incomplete):
                    self.audit()
            finally:
                release.set()
            self.assertTrue(accepts_blueprint(worker.result(4)))
        self.assertEqual(self.api.starts,1)

    def test_lost_webhook_ack_replays_receipt_only(self):
        receipt = self.audit()
        ledger = {}
        def store(r):
            self.assertTrue(accepts_blueprint(r))
            ledger[r["receiptId"]] = r
            return {k:r[k] for k in ("decision","receiptId")}
        def lose_ack(r):
            store(r)
            raise TimeoutError("ack lost")
        with self.assertRaises(TimeoutError):
            integration.deliver(self.db,"EU","E1",lose_ack)
        self.assertEqual(integration.deliver(self.db,"EU","E1",store),"ACKNOWLEDGED")
        self.assertEqual(integration.deliver(self.db,"EU","E1",lambda r: self.fail()),"ALREADY_ACKNOWLEDGED")
        self.assertEqual(ledger, {receipt["receiptId"]:receipt})
        self.assertEqual(self.api.starts,1)

    def test_default_make_200_or_wrong_receipt_is_not_delivery(self):
        self.audit()
        for wrong in ("Accepted", {}, {"receiptId":"wrong","decision":"HOLD_EXPORT"}):
            with self.subTest(wrong=wrong),self.assertRaises(Incomplete):
                integration.deliver(self.db,"EU","E1",lambda r:wrong)

    def test_missing_and_malformed_gate(self):
        receipt = self.audit()
        for wrong in ({"decision":"READY_FOR_REVIEW"}, {"flagged":2}, {"expected":1.5,"delivered":1.5},
                      {"schema":"other"}, {"expected":2},{"delivered":-1}, {"receiptId":""}):
            self.assertFalse(accepts_blueprint({**receipt,**wrong}))
        for key in receipt:
            self.assertFalse(accepts_blueprint({k:v for k,v in receipt.items() if k!=key}))
        for key in ("operationKey","receiptId","runRef"):
            self.assertFalse(accepts_blueprint({**receipt,key:"g"*64}))

    def test_exact_identity_and_cost_rejected(self):
        self.api.row.update(id="id:OTHER",status="passed_checks",findings=[])
        with self.assertRaises(Incomplete):
            self.audit()
        self.assertIsNone(integration.get_row(self.db,"EU","E1")["receipt"])
        prices=[{"id":"SKU-"+str(i)} for i in range(25)]
        with self.assertRaises(Incomplete):
            integration.audit(self.db,self.api,"store","too-cheap",{"offers":prices},"0.001",25)
        self.assertEqual(self.api.starts,1)

    def test_conflicting_ids_source_and_xml(self):
        rss='<rss xmlns:g="http://base.google.com/ns/1.0"><channel><title>Example</title><item><g:id> MUG-RED </g:id></item></channel></rss>'
        self.assertEqual(integration.offer_keys({"feedXml":rss}),{"id:MUG-RED"})
        record=integration.audit(self.db,self.api,"EU","known-xml",{"feedXml":rss},"0.01",1)
        self.assertEqual(record["decision"],"HOLD_EXPORT")
        for invalid in ({"offers":[{"id":" "}]},{"offers":[{"id":"a"},{"id":" a"}]},
                        {"feedUrl":"https://example.com/demo.xml","authorizedFetch":True},
                        {"feedXml":rss.replace("</item>","<id>other</id></item>")},
                        {"feedXml":"<!DOCTYPE rss>"+rss},{"feedXml":"<bad"},
                        {"feedXml":rss.replace("<item>","<entry>").replace("</item>","</entry>")},{}):
            with self.subTest(invalid=invalid),self.assertRaises(Incomplete):
                integration.audit(self.db,self.api,"EU","invalid",invalid,"0.01",1)
        self.assertEqual(self.api.starts,1)

    def test_pricing_and_plan_before_dispatch(self):
        original=deepcopy(self.api.actor)
        for attr, val in (("pricingModel","FREE"),("minimalMaxTotalChargeUsd",1),("isPPEPlatformUsagePaidByUser",True)):
            self.api.actor=deepcopy(original);self.api.actor["pricingInfos"][0][attr]=val
            with self.subTest(attr=attr),self.assertRaises(Incomplete):
                self.audit()
        self.api.actor=deepcopy(original)
        events=self.api.actor["pricingInfos"][0]["pricingPerEvent"]["actorChargeEvents"]
        events["offer-audited"]["eventPriceUsd"]=.001
        with self.assertRaises(Incomplete):
            self.audit()
        self.api.actor=original
        products=[{"id":"item-"+str(i)} for i in range(26)]
        with self.assertRaises(Incomplete):
            integration.audit(self.db,self.api,"EU","too-many",{"offers":products},"0.1",26)
        self.assertIn("users/me",self.api.public_reads)
        self.assertEqual(self.api.starts,0)
        self.api.profile={"isPaying":True,"plan":{"id":"Personal","isPayingCustomer":False}}
        self.api.items=[{"id":"id:"+x["id"],"status":"passed_checks","findings":[]} for x in products]
        self.api.events=26
        r=integration.audit(self.db,self.api,"EU","too-many",{"offers":products},"0.1",26)
        self.assertEqual("READY_FOR_REVIEW",r["decision"])
        self.assertEqual(self.api.starts,1)

    def test_documented_profile_shapes_and_opaque_plan(self):
        from decimal import Decimal
        for profile,allowed in (
            ({"isPaying":True,"plan":{"id":"Personal","isPayingCustomer":False}},True),
            ({"plan":{"isPayingCustomer":True}},True),
            ({"isPaying":False,"plan":{"isPayingCustomer":True}},False),
            ({"plan":{"isPayingCustomer":False}},False),
            ({"plan":{"id":"Personal"}},False),
            ({"isPaying":"true","plan":{"isPayingCustomer":True}},False),
            ({},False),
        ):
            self.api.profile=profile
            with self.subTest(profile=profile):
                if allowed:
                    integration.check_catalog_terms(self.api,26,Decimal("1"))
                else:
                    with self.assertRaises(Incomplete):
                        integration.check_catalog_terms(self.api,26,Decimal("1"))

    def test_active_public_terms_shapes_and_unknown_tiers(self):
        from decimal import Decimal
        terms=self.api.actor["pricingInfos"][0]
        # Exact shape confirmed by anonymous GET: these two optional properties were absent.
        self.assertNotIn("isPPEPlatformUsagePaidByUser",terms)
        self.assertNotIn("eventTieredPricingUsd",terms["pricingPerEvent"]["actorChargeEvents"]["offer-audited"])
        integration.check_catalog_terms(self.api,1,Decimal("0.01"))
        self.assertNotIn("users/me",self.api.public_reads)
        terms["isPPEPlatformUsagePaidByUser"]=False
        event=terms["pricingPerEvent"]["actorChargeEvents"]["offer-audited"]
        event["eventTieredPricingUsd"]=None
        integration.check_catalog_terms(self.api,1,Decimal("0.01"))
        event["eventTieredPricingUsd"]={"FREE":{"tieredEventPriceUsd":0.001}}
        with self.assertRaises(Incomplete):
            integration.check_catalog_terms(self.api,1,Decimal("0.01"))

    def test_charged_start_and_pinned_memory(self):
        self.api.start_events=2
        with self.assertRaises(Incomplete): self.audit()
        self.api.start_events=1;self.api.memory=1024
        with self.assertRaises(Incomplete): self.audit()
        self.api.memory=256;self.api.cap="0.1"
        with self.assertRaises(Incomplete): self.audit()
        self.api.cap="0.01"
        self.assertEqual(self.audit()["decision"],"HOLD_EXPORT")
        self.assertEqual(self.api.starts,1)

    def test_legacy_receipt_must_be_reverified(self):
        self.audit()
        with self.db:
            self.db.execute("UPDATE make_merchant_receipts SET proof=NULL")
        with self.assertRaises(Incomplete):
            integration.deliver(self.db,"EU","E1",lambda _:self.fail())
        self.assertEqual(self.audit()["decision"],"HOLD_EXPORT")
        self.assertEqual(self.api.starts,1)

    def test_start_url_fixed_once(self):
        client=integration.MerchantAPI("fixture-only")
        with patch.object(client,"request",return_value={"data":{"id":"SYNTHETIC"}}) as call:
            client.start("merchant",OFFER,"0.01")
        url, payload=call.call_args.args
        self.assertTrue(url.startswith(integration.ACTOR_PATH+"/runs?"))
        self.assertIn("memory=256",url);self.assertIn("maxTotalChargeUsd=0.01",url)
        self.assertIn("restartOnError=false",url);self.assertEqual(payload,OFFER)

    def test_inputs_and_destination_denied_before_post(self):
        with self.assertRaises(Incomplete):
            self.audit(expected=6)
        synthetic_path = "0" * 16
        for u in ("https://somewhere.example/test", f"http://hook.eu1.make.com/{synthetic_path}",
                  f"https://hook.eu1.make.com/{synthetic_path}?unexpected=query"):
            with patch.dict("os.environ",{"CUSTOMER_MAKE_WEBHOOK":u,"CUSTOMER_MAKE_WEBHOOK_KEY":"synthetic"}):
                with self.assertRaises(Incomplete):
                    integration.send_receipt({})
        self.assertEqual(self.api.starts,0)

    def test_windows_verifier_is_shared_with_apify_and_keeps_redirects_blocked(self):
        native = Mock()
        native.SSLContext.side_effect = ssl.SSLContext
        with patch.object(integration.sys, "platform", "win32"), patch.object(
            integration, "import_module", return_value=native
        ) as imported:
            client = integration.MerchantAPI("fixture-only")
            opener = integration.verified_opener()
        self.assertEqual(imported.call_count, 2)
        self.assertTrue(all(call.args == ("truststore",) for call in imported.call_args_list))
        self.assertTrue(all(call.args == (ssl.PROTOCOL_TLS_CLIENT,) for call in native.SSLContext.call_args_list))
        self.assertEqual(native.SSLContext.call_count, 2)
        for transport in (opener, client.opener):
            https, = [h for h in transport.handlers if isinstance(h, integration.request.HTTPSHandler)]
            self.assertTrue(https._context.check_hostname)
            self.assertEqual(https._context.verify_mode, ssl.CERT_REQUIRED)
            redirect, = [h for h in transport.handlers if isinstance(h, integration.request.HTTPRedirectHandler)]
            with self.assertRaises(Incomplete):
                redirect.redirect_request(None, None, 307, "", {}, "https://example.invalid/")

    def test_optional_native_package_and_portable_default(self):
        absent = ModuleNotFoundError("absent in fixture", name="truststore")
        for platform in ("win32", "linux", "darwin"):
            with self.subTest(platform=platform), patch.object(integration.sys, "platform", platform), patch.object(
                integration, "import_module", side_effect=absent
            ) as imported, patch.object(ssl, "create_default_context", wraps=ssl.create_default_context) as default:
                integration.verified_opener()
                self.assertEqual(imported.call_count, int(platform == "win32"))
                default.assert_called_once_with()

    @unittest.skipUnless(integration.sys.platform == "win32", "Windows runtime only")
    def test_installed_windows_verifier_without_network(self):
        try:
            import truststore
        except ModuleNotFoundError as exc:
            if exc.name != "truststore":
                raise
            self.skipTest("optional native verifier is not installed")
        opener = integration.verified_opener()
        handler, = [h for h in opener.handlers if isinstance(h, integration.request.HTTPSHandler)]
        self.assertIsInstance(handler._context, truststore.SSLContext)
        self.assertTrue(handler._context.check_hostname)
        self.assertEqual(handler._context.verify_mode, ssl.CERT_REQUIRED)

    def test_windows_refuses_broken_or_unverified_native_configuration(self):
        broken = ModuleNotFoundError("invalid in fixture", name="internal_missing_component")
        with patch.object(integration.sys, "platform", "win32"), patch.object(
            integration, "import_module", side_effect=broken
        ), self.assertRaises(Incomplete):
            integration.verified_opener()
        native = Mock()
        native.SSLContext.return_value.check_hostname = False
        with patch.object(integration.sys, "platform", "win32"), patch.object(
            integration, "import_module", return_value=native
        ), self.assertRaises(Incomplete):
            integration.verified_opener()

    def test_transport_failure_preserves_receipt_and_redacts_provider_details(self):
        receipt = self.audit()
        route = "https://hook.eu1.make.com/" + "X" * 20
        key = "offline-example-key"
        env = {"CUSTOMER_MAKE_WEBHOOK": route, "CUSTOMER_MAKE_WEBHOOK_KEY": key}
        for failure in (ssl.SSLCertVerificationError(key + route), TimeoutError(key + route)):
            with self.subTest(kind=type(failure).__name__), patch.dict("os.environ", env), patch.object(
                integration, "verified_opener"
            ) as opener:
                opener.return_value.open.side_effect = integration.error.URLError(failure)
                with self.assertRaises(Incomplete) as caught:
                    integration.deliver(self.db, "EU", "E1")
                self.assertEqual(str(caught.exception), "No valid Make response. Retry delivery only.")
                self.assertTrue(caught.exception.__suppress_context__)
                opener.return_value.open.assert_called_once()
                self.assertEqual(opener.return_value.open.call_args.kwargs, {"timeout": 30})
                row = integration.get_row(self.db, "EU", "E1")
                self.assertFalse(row["acknowledged"])
                self.assertEqual(json.loads(row["receipt"]), receipt)
                self.assertEqual(self.api.starts, 1)

    def test_blueprint_graph_and_customer_bindings(self):
        trigger, record, response = BLUEPRINT["flow"]
        self.assertEqual([node["module"] for node in BLUEPRINT["flow"]],
                         ["gateway:CustomWebHook","datastore:AddRecord","gateway:WebhookRespond"])
        self.assertNotIn("hook",trigger["parameters"])
        self.assertNotIn("datastore",record["parameters"])
        self.assertEqual(record["mapper"]["key"],"{{1.receiptId}}")
        self.assertTrue(record["mapper"]["overwrite"])
        self.assertIn("{{1.receiptId}}",response["mapper"]["body"])
        self.assertEqual(BLUEPRINT["metadata"]["scenario"]["confidential"],True)
        self.assertNotIn("https://",json.dumps(BLUEPRINT))


if __name__ == "__main__":
    unittest.main(verbosity=2)
