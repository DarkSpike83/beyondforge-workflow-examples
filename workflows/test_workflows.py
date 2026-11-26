"""Offline client contract tests with synthetic merchant, RSS and migration results."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from run_workflow import Apify, Incomplete, execute, fingerprint, open_journal
from export_result import export

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def example(name):
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


class Platform:
    def __init__(self):
        self.inputs = []
        self.records = {}
        self.dataset = []
        self.status_value = "SUCCEEDED"
        self.ledger_override = None

    def start(self, flow, payload, budget):
        self.inputs.append((flow, payload, budget))
        return "run" + str(len(self.inputs))

    def status(self, run_id):
        summary = self.records.get("RUN_SUMMARY",{})
        event = summary.get("event",summary.get("eventName"))
        count = summary.get("returned",summary.get("chargedEvents",0))
        ledger = {event:count} if event and count else {}
        if self.inputs and self.inputs[-1][0] in ("merchant","rss"):
            ledger["apify-actor-start"] = 1
        return {"id": run_id, "status": self.status_value,
                "chargedEventCounts":ledger if self.ledger_override is None else self.ledger_override}

    def record(self, run, key):
        return self.records[key]

    def rows(self, run, expected):
        assert len(self.dataset) == expected
        return self.dataset

    def merchant(self):
        self.dataset = [{"id":"MUG-RED", "offerId":"MUG-RED", "status":"review", "distinctVersions":1,
                         "findings":[{"code":"SALE_PRICE", "action":"Review sale price."}]}]
        self.records = {"RUN_SUMMARY":{"outcome":"complete", "returned":1, "matched":1,
                                       "event":"offer-audited","inputOffers":1,"uniqueOffers":1}}

    def rss(self, edited):
        self.dataset = ([{"id":"c"*64, "change":"edited", "changedFields":["title"],
                          "title":"Updated deadline", "link":""}] if edited else [])
        self.records = {"RUN_SUMMARY":{"outcome":"complete", "returned":len(self.dataset),
                                       "matched":len(self.dataset), "checkpointReady":True,"entries":1,"event":"feed-change",
                                       "unchanged":1-len(self.dataset),"previousOnly":0},
                        "CHECKPOINT":{"version":1,"feedKey":"b"*64,
                                      "entries":{"c"*64:{k:"a"*64 for k in ("title","link","content","published","updated")}}}}

    def migration(self, mode="audit", flagged=1):
        findings = ["temporary-redirect"] if flagged else []
        trace = {"source":"https://old.example/help","expected":"https://new.example/support","findings":findings}
        if mode == "audit":
            trace.update(hops=[{"status":302 if flagged else 301,"to":"https://new.example/support"}],
                         finalStatus=200,finalUrl="https://new.example/support")
        report = {"kind":"migration-redirect-audit", "flaggedUrls":flagged, "schemaVersion":1,
                  "demoCase":"regression-recovery" if mode == "preview" else None,"comparison":None,
                  "findingCounts":{"temporary-redirect":1} if flagged else {},
                  "outcome":"findings" if flagged else "clean", "mappedUrls":1, "fullyTracedUrls":1,
                  "outputMode":mode,"results":[trace]}
        self.dataset = [{**{key:value for key,value in report.items() if key != "results"},
                         "reportSha256":fingerprint(report),"reportKey":"REPORT"}]
        self.records = {"RUN_SUMMARY":{"outcome":"complete","deliveredReports":1, "outputMode":mode,
                                       "chargedEvents":int(mode == "audit"),
                                       "eventName":"migration-audited" if mode == "audit" else None,
                                       "reportSha256":fingerprint(report)},"REPORT":report}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.db = open_journal(":memory:")
        self.addCleanup(self.db.close)
        self.api = Platform()

    def call(self, flow, fixture, op="snapshot1", scope="catalog-a"):
        return execute(self.db, self.api, flow, scope, op, example(fixture), "0.02", wait=0)

    def test_merchant_stops_export_and_reuses_operation(self):
        self.api.merchant()
        result = self.call("merchant", "merchant-offers.json")
        self.assertEqual(result["decision"], "HOLD_EXPORT")
        self.assertEqual(self.call("merchant", "merchant-offers.json"), result)
        self.assertEqual(len(self.api.inputs), 1)

    def test_empty_merchant_never_signs_off(self):
        self.api.dataset = []
        self.api.records["RUN_SUMMARY"] = {"outcome":"complete","returned":0,"matched":0,
                                            "event":"offer-audited","inputOffers":0,"uniqueOffers":0}
        self.assertEqual(self.call("merchant","merchant-offers.json")["decision"],"EMPTY_CATALOG")

    def test_rss_edit_then_no_change_uses_checkpoint(self):
        self.api.rss(True)
        self.assertEqual(self.call("rss","rss-edit.json")["rows"][0]["changedFields"], ["title"])
        self.api.rss(False)
        result = self.call("rss","rss-next.json","snapshot2")
        self.assertEqual(result["decision"], "UNCHANGED")
        self.assertIn("baseline", self.api.inputs[-1][1])
        self.call("rss","rss-next.json","snapshot2","second-feed")
        self.assertNotIn("baseline", self.api.inputs[-1][1])

    def test_partial_preserves_old_checkpoint(self):
        self.api.rss(False)
        self.call("rss","rss-next.json")
        before = self.db.execute("SELECT value FROM checkpoints").fetchone()[0]
        self.api.records["RUN_SUMMARY"]["outcome"] = "budget_limit"
        with self.assertRaises(Incomplete): self.call("rss","rss-next.json","snapshot2")
        self.assertEqual(self.db.execute("SELECT value FROM checkpoints").fetchone()[0],before)

    def test_migration_audit_and_preview_are_distinct(self):
        for mode, count, decision in [("audit",1,"HOLD_RELEASE"),("audit",0,"READY_FOR_SIGN_OFF"),
                                      ("preview",0,"DEMO_ONLY")]:
            self.api.migration(mode,count)
            name = "migration-preview.json" if mode=="preview" else "migration-custom.json"
            self.assertEqual(self.call("migration",name,decision)["decision"],decision)

    def test_modified_report_is_rejected(self):
        self.api.migration()
        self.api.records["REPORT"]["flaggedUrls"] = 0
        with self.assertRaises(Incomplete): self.call("migration","migration-custom.json")

    def test_duplicate_or_unrequested_commercial_event_blocks_delivery(self):
        self.api.migration()
        self.api.ledger_override = {"migration-audited":2}
        with self.assertRaises(Incomplete): self.call("migration","migration-custom.json")
        self.api.rss(False)
        self.api.ledger_override = {"apify-actor-start":1,"comparison-receipt":1}
        with self.assertRaises(Incomplete): self.call("rss","rss-next.json")
        self.assertIsNone(self.db.execute("SELECT value FROM checkpoints").fetchone())

    def test_signed_empty_traces_are_rejected(self):
        self.api.migration("audit",0)
        self.api.records["REPORT"]["results"] = []
        digest = fingerprint(self.api.records["REPORT"])
        self.api.records["RUN_SUMMARY"]["reportSha256"] = self.api.dataset[0]["reportSha256"] = digest
        with self.assertRaises(Incomplete): self.call("migration","migration-custom.json")

    def test_bad_checkpoint_cannot_replace_feed_state(self):
        self.api.rss(True)
        self.api.records["CHECKPOINT"]["entries"] = {}
        with self.assertRaises(Incomplete): self.call("rss","rss-edit.json")
        self.assertIsNone(self.db.execute("SELECT value FROM checkpoints").fetchone())

    def test_feed_window_and_valid_empty_are_distinct(self):
        self.api.rss(False)
        self.api.records["RUN_SUMMARY"].update(entries=0,unchanged=0,previousOnly=1)
        self.api.records["CHECKPOINT"]["entries"] = {}
        self.assertEqual(self.call("rss","rss-next.json")["decision"],"FEED_WINDOW_CHANGED")
        self.api.records["RUN_SUMMARY"]["previousOnly"] = 0
        self.assertEqual(self.call("rss","rss-next.json","next")["decision"],"EMPTY_FEED")

    def test_ambiguous_start_blocks_replay_and_next_observation(self):
        self.api.merchant()
        with patch.object(self.api,"start",side_effect=Incomplete("response lost")) as submit:
            for op in ["one","one","two"]:
                with self.assertRaises(Incomplete): self.call("merchant","merchant-offers.json",op)
            self.assertEqual(submit.call_count,1)

    def test_pending_poll_resumes_without_second_start(self):
        self.api.merchant()
        self.api.status_value = "RUNNING"
        with self.assertRaises(Incomplete): self.call("merchant","merchant-offers.json")
        self.api.status_value = "SUCCEEDED"
        self.assertEqual(self.call("merchant","merchant-offers.json")["decision"],"HOLD_EXPORT")
        self.assertEqual(len(self.api.inputs),1)

    def test_input_change_on_same_key_blocks(self):
        self.api.rss(False)
        self.call("rss","rss-next.json")
        with self.assertRaises(Incomplete): self.call("rss","rss-edit.json")
        self.assertEqual(len(self.api.inputs),1)

    def test_terminal_failure_requires_review(self):
        self.api.status_value = "FAILED"
        for attempt in range(2):
            with self.assertRaises(Incomplete): self.call("rss","rss-next.json")
        self.assertEqual(len(self.api.inputs),1)

    def test_pagination_and_guard(self):
        api = Apify("offline-placeholder")
        with patch.object(api,"request",side_effect=[[{}]*100,[{}]*5,[]]) as req:
            self.assertEqual(len(api.rows({"defaultDatasetId":"synthetic"},105)),105)
            self.assertIn("offset=100",req.call_args_list[1].args[0])
        with patch.object(api,"request",side_effect=[[]]):
            with self.assertRaises(Incomplete): api.rows({"defaultDatasetId":"synthetic"},2)

    def test_request_envelope_and_budget(self):
        api = Apify("offline-placeholder")
        with patch.object(api,"request",return_value={"data":{"id":"synthetic"}}) as req:
            api.start("merchant",{"offers":[]},"0.02")
            self.assertEqual(req.call_args.args[0],"acts/beyondforge~merchant-feed-preflight/runs?maxTotalChargeUsd=0.02&restartOnError=false")
            self.assertEqual(req.call_args.args[1],{"offers":[]})

    def test_persistent_reopen_and_redacted_export(self):
        folder = Path.cwd() / (".workflow-test-" + uuid4().hex)
        folder.mkdir()
        self.addCleanup(folder.rmdir)
        journal = folder / "workflow-state.sqlite"
        self.addCleanup(journal.unlink, missing_ok=True)
        output = folder / "route.json"
        self.addCleanup(output.unlink, missing_ok=True)
        self.api.migration("preview",0)
        db = open_journal(journal)
        try:
            execute(db,self.api,"migration","site","release",example("migration-preview.json"),"0")
        finally:
            db.close()
        export(folder,"migration","site","release",output,True)
        value = json.loads(output.read_text(encoding="utf-8"))
        self.assertNotIn("report",value)
        self.assertEqual(value["decision"],"DEMO_ONLY")
        with self.assertRaises(FileExistsError): export(folder,"migration","site","release",output,True)


if __name__ == "__main__":
    unittest.main()
