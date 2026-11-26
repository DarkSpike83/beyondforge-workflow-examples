"""Export a verified operation into a new file in the customer's private environment."""
import argparse
import json
import sqlite3
from pathlib import Path

from run_workflow import ACTORS


def export(workspace, flow, scope, operation, target, routing_only=False):
    if routing_only and flow != "migration":
        raise ValueError("Routing export is specific to the migration gate.")
    uri = (workspace / "workflow-state.sqlite").resolve().as_uri() + "?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        row = db.execute("SELECT result FROM operations WHERE flow=? AND scope=? AND operation=? AND state='done'",
                         (flow, scope, operation)).fetchone()
    finally:
        db.close()
    if not row:
        raise ValueError("A verified output is unavailable for this operation.")
    value = json.loads(row[0])
    if routing_only:
        value = {key: value[key] for key in ("decision", "runId", "summary", "overview")}
    with target.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("flow", choices=ACTORS)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--operation", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--routing-only", action="store_true")
    args = parser.parse_args()
    try:
        export(args.workspace, args.flow, args.scope, args.operation, args.output, args.routing_only)
    except (OSError, sqlite3.Error, ValueError):
        parser.exit(2, "Check the private directory, completed operation and unused output filename.\n")
