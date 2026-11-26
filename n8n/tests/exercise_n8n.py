"""Import and execute the templates on a private, disposable local n8n instance.
Requires an existing n8n Community Edition installation. Uses isolated synthetic
credentials for two organizations, loopback HTTP and the official local Server CLI.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socket
import sqlite3
import subprocess
import tempfile
import time

from fixture_api import Contract, compact, start_fixture

PUBLIC = Path(__file__).resolve().parent.parent
FLOWS = ("merchant", "supplier", "migration", "rss")


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def suite():
    # name, template, private stream alias, sequence, API behaviour, expected result
    return [
        (
            "preflight, finalized PPE counters",
            "merchant",
            "catalog-a",
            1,
            "delayed_ledger",
            "HOLD_EXPORT",
        ),
        ("replay", "merchant", "catalog-a", 1, "normal", "DUPLICATE_SKIP"),
        ("next clean", "merchant", "catalog-a", 2, "clean", "READY_FOR_REVIEW"),
        (
            "independent organization, identical scope",
            "merchant",
            "catalog-a",
            1,
            "other_org",
            "HOLD_EXPORT",
        ),
        (
            "reject cross-organization credential",
            "merchant",
            "credential",
            1,
            "wrong_auth",
            "error",
        ),
        (
            "private repo required",
            "merchant",
            "private-check",
            1,
            "public_repo",
            "error",
        ),
        ("CAS rejected", "merchant", "race-check", 1, "conflict", "error"),
        ("ambiguous POST", "merchant", "api-error", 1, "api_error", "error"),
        ("ambiguous replay", "merchant", "api-error", 1, "normal", "error"),
        (
            "transport timeout after acceptance",
            "merchant",
            "lost-response",
            1,
            "transport",
            "error",
        ),
        (
            "no repeat after lost response",
            "merchant",
            "lost-response",
            1,
            "normal",
            "error",
        ),
        ("partial", "merchant", "partial", 1, "partial", "error"),
        ("plan restriction", "merchant", "denied", 1, "denied", "error"),
        ("extra PPE", "merchant", "ledger", 1, "wrong_ledger", "error"),
        ("pending run", "merchant", "pending", 1, "timeout", "error"),
        ("resume pending", "merchant", "pending", 1, "resume", "HOLD_EXPORT"),
        ("supplier demo", "supplier", "supplier-demo", 1, "normal", "DEMO_ONLY"),
        (
            "supplier full",
            "supplier",
            "supplier-live",
            1,
            "full",
            "REVIEW_CATALOG_CHANGES",
        ),
        (
            "supplier next",
            "supplier",
            "supplier-live",
            2,
            "full",
            "REVIEW_CATALOG_CHANGES",
        ),
        ("migration demo", "migration", "migration-demo", 1, "normal", "DEMO_ONLY"),
        ("migration full", "migration", "migration-audit", 1, "full", "HOLD_RELEASE"),
        ("RSS edited", "rss", "feed-a", 1, "normal", "REVIEW_CHANGES"),
        ("RSS unchanged", "rss", "feed-a", 2, "normal", "UNCHANGED"),
        ("changed prior checkpoint", "rss", "feed-a", 3, "modified_baseline", "error"),
    ]


def fixture_copy(flow, scope, seq, mode, base_url, wid):
    data = json.loads(
        (PUBLIC / "workflows" / f"n8n-{flow}.json").read_text(encoding="utf-8")
    )
    assert data["active"] is False
    data.update(id=wid, name="Fixture " + wid)
    for node in data["nodes"]:
        params = node["parameters"]
        # n8n's CLI prefers Execute Workflow Trigger to Manual Trigger. These
        # fixtures drive the template's own manual sample entry without a caller.
        if node["type"] == "n8n-nodes-base.executeWorkflowTrigger":
            node["disabled"] = True
        if node["type"] == "n8n-nodes-base.httpRequest":
            expr = params["url"]
            host = next(
                (
                    h
                    for h in ("https://api.apify.com", "https://api.github.com")
                    if h in expr
                ),
                None,
            )
            if host is None:
                raise ValueError("Unrecognized outbound HTTP node")
            marker = "apify" if "apify" in host else "git"
            if mode == "other_org":
                marker += "2"
            params["url"] = expr.replace(host, base_url + "/" + marker)
            if mode == "wrong_auth" and marker == "git":
                marker = "git2"
            node["credentials"] = {
                "httpHeaderAuth": {
                    "id": "bf" + marker + "header",
                    "name": "Fixture " + marker,
                }
            }
            if mode == "transport" and params.get("method") == "POST":
                params["options"]["timeout"] = 100
        if node["name"] == "Configure connection":
            code = params["jsCode"].replace(
                "const enabled = false", "const enabled = true"
            )
            code = code.replace(
                "YOUR_OWNER",
                "fixture-other" if mode == "other_org" else "fixture-owner",
            ).replace("YOUR_PRIVATE_REPOSITORY", "fixture-state")
            code = re.sub(
                r"const scope = '[^']+';", "const scope = '" + scope + "';", code
            )
            if mode == "full":
                code = re.sub(r"const maxUsd = [\d.]+;", "const maxUsd = 3;", code)
            params["jsCode"] = code
        if node["name"] == "Sample observation":
            filename = (
                f"{flow}-custom-observation.json"
                if mode == "full"
                else f"{flow}-observation.json"
            )
            obs = json.loads(
                (PUBLIC / "fixtures" / filename).read_text(encoding="utf-8")
            )
            obs["sequence"] = seq
            if mode == "clean":
                obs["input"]["offers"][0]["sale_price"] = "12.50 USD"
            if seq > 1 and flow == "supplier":
                obs["input"].pop("baseline", None)
                obs["input"]["incoming"]["rows"][0]["price"] = "13.00"
            if seq > 1 and flow == "rss":
                obs["input"].pop("previousXml", None)
            params["jsCode"] = "return [{json:" + json.dumps(obs) + "}];"
    return data


def await_local_publication(node, entry, work, env, db_uri, workflow_id, version):
    """Let n8n's main-instance publication service apply the official CLI request."""

    def applied():
        with closing(sqlite3.connect(db_uri, uri=True)) as db:
            row = db.execute(
                "SELECT publishedVersionId FROM workflow_published_version WHERE workflowId=?",
                (workflow_id,),
            ).fetchone()
        return row is not None and row[0] == version

    if applied():
        return
    headless = dict(env, N8N_DISABLE_UI="true")
    with (work / "local-publisher.log").open("wb") as log:
        proc = subprocess.Popen(
            [str(node), str(entry), "start"],
            cwd=work,
            env=headless,
            stdout=log,
            stderr=log,
        )
        try:
            deadline = time.monotonic() + 600
            while not applied():
                if proc.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError(
                        "n8n main instance failed to apply local publication"
                    )
                time.sleep(1)
            print(
                "Local main instance applied the requested sub-workflow version",
                flush=True,
            )
        finally:
            if proc.poll() is None:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                    )
                else:
                    proc.terminate()
                proc.wait(timeout=20)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--node", required=True, type=Path)
    p.add_argument(
        "--n8n-entry",
        required=True,
        type=Path,
        help="Installed n8n/bin/n8n JavaScript entrypoint",
    )
    p.add_argument(
        "--scratch",
        required=True,
        type=Path,
        help="Existing empty/private scratch parent",
    )
    p.add_argument("--evidence", type=Path)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument(
        "--caller-only",
        action="store_true",
        help="Verify a native caller workflow invoking the same published local Merchant sub-workflow twice",
    )
    p.add_argument(
        "--diagnostic-stop",
        action="store_true",
        help="Stop after the first failed assertion",
    )
    args = p.parse_args()
    api = Contract()
    srv = start_fixture(api)
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        broker_port = probe.getsockname()[1]
    cases = suite()[: args.limit]
    if args.caller_only:
        cases = [
            (
                "caller returns correction",
                "merchant",
                "caller-catalog",
                1,
                "normal",
                "HOLD_EXPORT",
            ),
            (
                "caller returns approval",
                "merchant",
                "caller-catalog",
                2,
                "clean",
                "READY_FOR_REVIEW",
            ),
        ]
    obs = {
        "tests": [],
        "startedUtc": datetime.now(timezone.utc).isoformat(),
        "paidRuns": 0,
        "mode": "n8n local Server CLI, synthetic loopback APIs",
    }
    try:
        with tempfile.TemporaryDirectory(
            prefix="bf-fixture-", dir=args.scratch, ignore_cleanup_errors=True
        ) as tmp:
            work = Path(tmp)
            env = {
                k: v
                for k, v in os.environ.items()
                if k.upper()
                in {
                    "SYSTEMROOT",
                    "WINDIR",
                    "COMSPEC",
                    "PATH",
                    "PATHEXT",
                    "SYSTEMDRIVE",
                    "USERPROFILE",
                    "APPDATA",
                    "LOCALAPPDATA",
                    "LANG",
                }
            }
            env.update(
                PATH=str(args.node.resolve().parent) + os.pathsep + env.get("PATH", ""),
                TMP=tmp,
                TEMP=tmp,
                N8N_USER_FOLDER=tmp,
                N8N_ENCRYPTION_KEY=secrets.token_hex(32),
                N8N_LISTEN_ADDRESS="127.0.0.1",
                N8N_HOST="127.0.0.1",
                N8N_PORT="58671",
                N8N_RUNNERS_BROKER_LISTEN_ADDRESS="127.0.0.1",
                N8N_RUNNERS_BROKER_PORT=str(broker_port),
                N8N_RUNNERS_ENABLED="true",
                NODE_FUNCTION_ALLOW_BUILTIN="crypto",
                N8N_DIAGNOSTICS_ENABLED="false",
                N8N_VERSION_NOTIFICATIONS_ENABLED="false",
                N8N_TEMPLATES_ENABLED="false",
                N8N_PERSONALIZATION_ENABLED="false",
                N8N_COMMUNITY_PACKAGES_ENABLED="false",
                N8N_LICENSE_AUTO_RENEW_ENABLED="false",
                N8N_LOG_LEVEL="info",
                N8N_SECURE_COOKIE="true",
                N8N_SSRF_PROTECTION_IP_ADDRESS_ALLOWLIST="127.0.0.1/32",
                HTTP_PROXY="http://127.0.0.1:1",
                HTTPS_PROXY="http://127.0.0.1:1",
                NO_PROXY="localhost,127.0.0.1,::1",
                NODE_USE_ENV_PROXY="1",
            )

            def cli(*words):
                result = subprocess.Popen(
                    [str(args.node.resolve()), str(args.n8n_entry.resolve()), *words],
                    env=env,
                    cwd=work,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                )
                try:
                    stdout, stderr = result.communicate(
                        timeout=1200 if words[0] == "execute-batch" else 600
                    )
                except BaseException:
                    if result.poll() is None:
                        if os.name == "nt":
                            subprocess.run(
                                ["taskkill", "/PID", str(result.pid), "/T", "/F"],
                                capture_output=True,
                            )
                        else:
                            result.kill()
                        result.wait(timeout=10)
                    raise
                out = stdout + "\n" + stderr
                for k in [env["N8N_ENCRYPTION_KEY"], *api.keys.values()]:
                    out = out.replace(k, "<synthetic-redacted>")
                return result.returncode, out

            creds = [
                {
                    "id": "bf" + k + "header",
                    "name": "Fixture " + k,
                    "type": "httpHeaderAuth",
                    "data": {"name": "Authorization", "value": "Bearer " + v},
                }
                for k, v in api.keys.items()
            ]
            save(work / "creds.json", creds)
            code, msg = cli("import:credentials", "--input=" + str(work / "creds.json"))
            if code:
                raise RuntimeError("Credential import: " + msg[-1200:])
            (work / "creds.json").unlink()
            files = sorted((PUBLIC / "workflows").glob("n8n-*.json"))
            obs["originalSha256"] = {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files
            }
            obs["n8nVersion"] = json.loads(
                (args.n8n_entry.resolve().parents[1] / "package.json").read_text(
                    encoding="utf-8"
                )
            )["version"]
            originals = [json.loads(p.read_text(encoding="utf-8")) for p in files]
            if len(originals) != 4:
                raise RuntimeError("Expected four public workflow templates")
            workflows = []
            ids = []
            base = "http://127.0.0.1:" + str(srv.server_port)
            child_id = "bf16child00000001"
            if args.caller_only:
                child = fixture_copy(
                    "merchant",
                    "caller-catalog",
                    1,
                    "normal",
                    base + "/shared",
                    child_id,
                )
                for node in child["nodes"]:
                    if node["type"] == "n8n-nodes-base.executeWorkflowTrigger":
                        node.pop("disabled", None)
                workflows.append(child)
            for i, (_, flow, scope, seq, mode, _) in enumerate(cases):
                wid = "bf16case" + str(i + 1).zfill(8)
                ids.append(wid)
                api.cases[wid] = (scope, mode)
                variant = fixture_copy(flow, scope, seq, mode, base + "/" + wid, wid)
                if args.caller_only:
                    sample = next(
                        node
                        for node in variant["nodes"]
                        if node["name"] == "Sample observation"
                    )
                    trigger = next(
                        node
                        for node in variant["nodes"]
                        if node["type"] == "n8n-nodes-base.manualTrigger"
                    )
                    control = {
                        "id": "fixture-case",
                        "name": "Select synthetic case",
                        "type": "n8n-nodes-base.httpRequest",
                        "typeVersion": 4.2,
                        "position": [200, 0],
                        "parameters": {
                            "url": base + "/select-case/" + wid,
                            "options": {},
                        },
                    }
                    call = {
                        "id": "fixture-call",
                        "name": "Execute Merchant sub-workflow",
                        "type": "n8n-nodes-base.executeWorkflow",
                        "typeVersion": 1.3,
                        "position": [600, 0],
                        "parameters": {
                            "source": "database",
                            "workflowId": {
                                "__rl": True,
                                "value": child_id,
                                "mode": "id",
                            },
                            "mode": "once",
                            "options": {"waitForSubWorkflow": True},
                        },
                    }
                    nodes = [trigger, control, sample, call]
                    links = {
                        a["name"]: {
                            "main": [[{"node": b["name"], "type": "main", "index": 0}]]
                        }
                        for a, b in zip(nodes, nodes[1:])
                    }
                    variant = {
                        "id": wid,
                        "name": "Synthetic caller " + wid,
                        "active": False,
                        "settings": {"executionOrder": "v1"},
                        "nodes": nodes,
                        "connections": links,
                    }
                workflows.append(variant)
            save(work / "flows.json", originals + workflows)
            code, msg = cli("import:workflow", "--input=" + str(work / "flows.json"))
            if code:
                raise RuntimeError("Workflow import: " + msg[-1500:])
            obs["importedOriginalTemplates"] = len(originals)
            obs["importedFixtureVariants"] = len(ids)
            if args.caller_only:
                code, msg = cli("publish:workflow", "--id=" + child_id)
                uri = (work / ".n8n" / "database.sqlite").as_uri() + "?mode=ro"
                with closing(sqlite3.connect(uri, uri=True)) as db:
                    published = db.execute(
                        "SELECT activeVersionId FROM workflow_entity WHERE id=?",
                        (child_id,),
                    ).fetchone()
                if code or not published or not published[0]:
                    raise RuntimeError(
                        "Private local sub-workflow activation failed: " + msg[-1200:]
                    )
                await_local_publication(
                    args.node.resolve(),
                    args.n8n_entry.resolve(),
                    work,
                    env,
                    uri,
                    child_id,
                    published[0],
                )
                obs["entry"] = (
                    "Native Execute Sub-workflow -> Receive authorized export; a single sub-workflow published only in this loopback test database"
                )
            if args.evidence:
                save(args.evidence, obs)
            print(
                "Imported",
                len(originals),
                "originals and",
                len(ids),
                "isolated variants",
                flush=True,
            )
            snapshots = work / "snapshots"
            snapshots.mkdir()
            output = work / "batch.json"
            code, batch_log = cli(
                "execute-batch",
                "--ids=" + ",".join(ids),
                "--concurrency=1",
                "--retries=0",
                "--output=" + str(output),
                "--snapshot=" + str(snapshots),
            )
            if not output.exists():
                raise RuntimeError("No native execution report: " + batch_log[-2200:])
            native = {
                row["workflowId"]: row
                for row in json.loads(output.read_text(encoding="utf-8"))["executions"]
            }
            api.finish_case()
            for wid, (name, flow, scope, seq, mode, wanted) in zip(ids, cases):
                record = native[wid]
                engine_status = record["executionStatus"]
                msg = record.get("error", "")
                view = api.observations.get(wid)
                if not view:
                    raise RuntimeError(
                        name + " ended before the first fixture request: " + msg[:500]
                    )
                before, attempts_before = view.before, view.attempts_before
                snap = snapshots / (wid + "-snapshot.json")
                parsed = (
                    json.loads(snap.read_text(encoding="utf-8"))
                    if snap.exists()
                    else None
                )
                ok = False
                last = ""
                reason = ""
                error_details = ""
                route = None
                delivered = None
                if parsed:
                    doc = parsed
                    res = doc.get("data", {}).get(
                        "resultData", doc.get("resultData", {})
                    )
                    last = res.get("lastNodeExecuted", "")
                    error = res.get("error") or {}
                    reason = str(error.get("message", ""))[:240]
                    error_details = (
                        json.dumps(
                            {
                                k: error[k]
                                for k in (
                                    "message",
                                    "description",
                                    "httpCode",
                                    "messages",
                                    "code",
                                    "cause",
                                )
                                if k in error
                            }
                        ).lower()
                        if error
                        else ""
                    )
                    runs = res.get("runData", {}).get(last, [])
                    if runs and runs[-1].get("data"):
                        lanes = runs[-1]["data"].get("main", [])
                        active = [lane[0]["json"] for lane in lanes if lane]
                        if len(active) == 1:
                            delivered = active[0]
                            route = delivered.get("route")
                else:
                    reason, last = (msg.rsplit(" on node ", 1) + [""])[:2]
                    error_details = (
                        reason.lower()
                        + " "
                        + " ".join(
                            str(status) for status in view.codes if status >= 400
                        )
                    )
                st = view.state.get(
                    ("other/" if mode == "other_org" else "")
                    + "state/"
                    + scope
                    + ".json",
                    api.initial(),
                )
                if wanted == "error":
                    errs = {
                        "public_repo": "private",
                        "conflict": "409",
                        "api_error": "503",
                        "partial": "budget_limit",
                        "denied": "plan_limit",
                        "wrong_ledger": "paid event",
                        "timeout": "pending",
                        "normal": "unresolved",
                        "transport": "connection was aborted",
                        "wrong_auth": "401",
                        "modified_baseline": "Prior capture changed",
                    }
                    ok = (
                        engine_status in ("error", "warning")
                        and errs[mode].lower() in error_details
                        and st["lastSequence"] < seq
                    )
                else:
                    ok = engine_status == "success" and route == wanted
                verified_digest = None
                if ok and wanted not in ("error", "DUPLICATE_SKIP"):
                    reference = api.runs[delivered["runId"]]
                    rows = api.snapshots[reference["defaultDatasetId"]]
                    store = api.snapshots[reference["defaultKeyValueStoreId"]]
                    if flow == "merchant":
                        expected = {
                            "audited": len(rows),
                            "access": "free_compatible_inline",
                            "corrections": [
                                row for row in rows if row["status"] == "review"
                            ],
                        }
                    elif flow == "rss":
                        expected = {
                            "changes": rows,
                            "entries": store["RUN_SUMMARY"]["entries"],
                            "previousOnly": store["RUN_SUMMARY"]["previousOnly"],
                        }
                    else:
                        expected = store["REPORT"]
                    units = reference["chargedEventCounts"].get(delivered["event"], 0)
                    ok = (
                        delivered["result"] == expected
                        and delivered["verifiedUnits"] == units
                        and delivered["sequence"] == seq
                        and delivered["datasetId"] == reference["defaultDatasetId"]
                        and delivered["storeId"] == reference["defaultKeyValueStoreId"]
                    )
                    verified_digest = hashlib.sha256(
                        compact(delivered["result"])
                    ).hexdigest()
                attempts = (
                    sum(call[1] == "POST" for call in view.calls) - attempts_before
                )
                if name in (
                    "replay",
                    "ambiguous replay",
                    "resume pending",
                    "CAS rejected",
                    "private repo required",
                    "no repeat after lost response",
                    "reject cross-organization credential",
                    "changed prior checkpoint",
                ):
                    ok = ok and view.posts == before and attempts == 0
                if mode == "other_org":
                    ok = (
                        ok
                        and view.state["state/" + scope + ".json"]["lastSequence"] == 2
                        and st["lastSequence"] == 1
                    )
                if mode == "transport":
                    ok = ok and attempts == 1 and view.posts == before + 1
                if name == "RSS unchanged":
                    ok = ok and "baseline" in view.sources[-1]
                if name == "supplier next":
                    ok = (
                        ok
                        and view.sources[-1]["baseline"] == view.sources[-2]["incoming"]
                    )
                row = {
                    "name": name,
                    "passed": ok,
                    "engineStatus": engine_status,
                    "lastNode": last,
                    "route": route,
                    "starts": view.posts - before,
                    "startAttempts": attempts,
                    "stateSequence": st["lastSequence"],
                }
                if reason:
                    row["reason"] = reason
                if verified_digest:
                    row.update(
                        resultSha256=verified_digest,
                        verifiedUnits=delivered["verifiedUnits"],
                    )
                if not ok:
                    # Diagnostic summary only: no fixture secrets or raw inputs.
                    row["diagnostic"] = next(
                        (
                            l.strip()[:280]
                            for l in msg.splitlines()
                            if "error" in l.lower() and "license" not in l.lower()
                        ),
                        "No expected route or status",
                    )
                    print(
                        "Unexpected output:",
                        msg[-1800:] if not last else reason,
                        flush=True,
                    )
                obs["tests"].append(row)
                if args.evidence:
                    save(args.evidence, obs)
                print(name, ok, route, last, flush=True)
                if not ok and args.diagnostic_stop:
                    break
    finally:
        srv.shutdown()
        srv.server_close()
    obs["finishedUtc"] = datetime.now(timezone.utc).isoformat()
    if args.evidence:
        save(args.evidence, obs)
    if len(obs["tests"]) != len(cases) or not all(x["passed"] for x in obs["tests"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
