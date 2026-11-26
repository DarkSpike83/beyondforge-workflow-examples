"""Loopback-only contract fixture for the BeyondForge n8n examples. No external clients."""

import base64
import copy
import hashlib
import json
import secrets
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


def compact(value):
    return json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()


class Contract:
    def __init__(self):
        self.keys = {
            host: secrets.token_hex(20) for host in ("git", "apify", "git2", "apify2")
        }
        self.state = {}
        self.runs = {}
        self.posts = 0
        self.writes = 0
        self.sources = []
        self.golden = json.loads(
            Path(__file__)
            .with_name("synthetic-actor-results.json")
            .read_text(encoding="utf-8")
        )
        self.scenario = "normal"
        self.calls = []
        self.lock = threading.Lock()
        self.snapshots = {}
        self.tenants = {}
        self.cases = {}
        self.current = None
        self.observations = {}
        self.response_codes = []

    def finish_case(self):
        if self.current is None:
            return
        self.observations[self.current] = SimpleNamespace(
            state=copy.deepcopy(self.state),
            sources=copy.deepcopy(self.sources),
            posts=self.posts,
            calls=list(self.calls),
            before=self.before,
            attempts_before=self.attempts_before,
            codes=list(self.response_codes),
        )

    def select_case(self, case):
        if self.current == case:
            return
        self.finish_case()
        self.current = case
        scope, self.scenario = self.cases[case]
        self.before = self.posts
        self.attempts_before = sum(call[1] == "POST" for call in self.calls)
        self.response_codes = []
        if self.scenario == "resume":
            for run in self.runs.values():
                run["status"] = "SUCCEEDED"
        if self.scenario == "modified_baseline":
            prior = self.state["state/" + scope + ".json"]["baselineStore"]
            self.snapshots[prior]["CHECKPOINT"]["feedKey"] = "0" * 64
        print("Executing synthetic case", case, self.scenario, flush=True)

    def initial(self):
        return {"version": 1, "lastSequence": 0, "baselineStore": None, "pending": None}

    def content(self, path):
        obj = self.state.setdefault(path, self.initial())
        raw = compact(obj)
        return {
            "type": "file",
            "sha": hashlib.sha1(
                b"blob " + str(len(raw)).encode() + b"\0" + raw
            ).hexdigest(),
            "encoding": "base64",
            "content": base64.b64encode(raw).decode(),
        }

    def build_run(self, slug, payload):
        self.posts += 1
        self.sources.append(copy.deepcopy(payload))
        runid = f"testRun{self.posts}"
        fingerprint = hashlib.sha256(compact(payload)).hexdigest()
        delivered = copy.deepcopy(self.golden[fingerprint])
        event, charge = delivered["event"], delivered["charge"]
        rows, summary = delivered["rows"], delivered["summary"]
        report, checkpoint = delivered["report"], delivered["checkpoint"]
        ledger = {event: charge} if charge else {}
        if slug in ("merchant-feed-preflight", "rss-revision-ledger"):
            ledger["apify-actor-start"] = 1
        if self.scenario == "wrong_ledger":
            ledger["unexpected-event"] = 1
        if self.scenario == "partial":
            summary["outcome"] = "budget_limit"
        if self.scenario == "denied":
            summary["outcome"] = "plan_limit"
        rid = str(self.posts)
        run = {
            "id": runid,
            "status": "RUNNING" if self.scenario == "timeout" else "SUCCEEDED",
            "defaultDatasetId": "d" + rid,
            "defaultKeyValueStoreId": "s" + rid,
            "chargedEventCounts": ledger,
        }
        run["actId"] = {
            "merchant-feed-preflight": "kiyhZwamPiGAxKkcw",
            "rss-revision-ledger": "IkKwNzFXmvdbhkRSg",
            "migration-redirect-audit": "tZh0FR034Xgdebm3S",
            "supplier-catalog-reconciliation": "6LdV9Lku6qZCYYF5f",
        }[slug]
        self.runs[runid] = run
        self.snapshots["s" + rid] = {
            "RUN_SUMMARY": summary,
            "REPORT": report,
            "CHECKPOINT": checkpoint,
            "INPUT": payload,
        }
        self.snapshots["d" + rid] = rows
        return run

    def route(self, method, path, body, auth):
        parts = urlsplit(path).path.split("/")
        if parts[1:2] == ["select-case"] and method == "GET":
            if len(parts) != 3 or parts[2] not in self.cases:
                return 404, {"error": "Unknown fixture case"}
            self.select_case(parts[2])
            return 200, {"ready": True}
        if self.cases:
            case = parts.pop(1)
            if case == "shared":
                case = self.current
            if case not in self.cases:
                return 404, {"error": "Unknown fixture case"}
            self.select_case(case)
        marker = parts[1]
        if marker not in self.keys or auth != "Bearer " + self.keys[marker]:
            return 401, {"error": "fixture authentication rejected"}
        self.calls.append([marker, method, "/".join(parts[2:])])
        other = marker.endswith("2")
        owner = "fixture-other" if other else "fixture-owner"
        if marker in ("git", "git2"):
            if parts[2:5] != ["repos", owner, "fixture-state"]:
                return 403, {}
            if len(parts) == 5:
                return 200, {
                    "private": self.scenario != "public_repo",
                    "full_name": owner + "/fixture-state",
                }
            if parts[5] != "contents":
                return 404, {}
            key = ("other/" if other else "") + "/".join(parts[6:])
            prior = self.content(key)
            if method == "GET":
                return 200, prior
            if method == "PUT":
                if body["sha"] != prior["sha"] or self.scenario == "conflict":
                    return 409, {"message": "SHA conflict"}
                self.state[key] = json.loads(base64.b64decode(body["content"]))
                self.writes += 1
                return 200, {
                    "content": self.content(key),
                    "commit": {"sha": str(self.writes).zfill(40)},
                }
        if marker in ("apify", "apify2") and parts[2] == "v2":
            if parts[3] == "acts" and method == "POST":
                slug = parts[4].split("~")[-1]
                if self.scenario == "api_error":
                    return 503, {"error": {"type": "fixture-error"}}
                run = self.build_run(slug, body)
                for identifier in (
                    run["id"],
                    run["defaultDatasetId"],
                    run["defaultKeyValueStoreId"],
                ):
                    self.tenants[identifier] = marker
                if self.scenario == "transport":
                    time.sleep(0.45)
                return 201, {"data": run}
            if self.tenants.get(parts[4]) != marker:
                return 403, {"error": "Wrong fixture account"}
            if parts[3] == "actor-runs":
                run = copy.deepcopy(self.runs[parts[4]])
                if (
                    self.scenario == "delayed_ledger"
                    and "waitForFinish" in urlsplit(path).query
                ):
                    run["chargedEventCounts"] = {}
                return 200, {"data": run}
            if parts[3] == "datasets":
                return 200, self.snapshots[parts[4]]
            if parts[3] == "key-value-stores":
                value = self.snapshots.get(parts[4], {}).get(parts[6])
                return (
                    (404, {"error": "missing fixture record"})
                    if value is None
                    else (200, value)
                )
        return 404, {"error": "unknown fixture path"}


def start_fixture(api):
    class Handler(BaseHTTPRequestHandler):
        def serve(self):
            content = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            body = json.loads(content) if content else {}
            try:
                with api.lock:
                    status, result = api.route(
                        self.command, self.path, body, self.headers.get("Authorization")
                    )
                    api.response_codes.append(status)
            except (KeyError, ValueError, IndexError) as error:
                status, result = 500, {
                    "error": "bad fixture contract",
                    "detail": str(error),
                }
            raw = compact(result)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

        do_GET = serve
        do_PUT = serve
        do_POST = serve

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
