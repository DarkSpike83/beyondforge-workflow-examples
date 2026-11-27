"""Verify the two offline sample ZIPs in this directory. Requires Python 3.8+."""
import csv
import hashlib
from io import TextIOWrapper
import json
from pathlib import Path
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent


def read_delivery(number):
    with (HERE / f"catalog-{number}.csv").open(encoding="utf-8", newline="") as file:
        catalog = {(r["sku"], int(r["position"])): r["url"] for r in csv.DictReader(file)}
    manifest = json.loads((HERE / f"manifest-{number}.json").read_bytes())
    if manifest["catalogId"] != "studio-blocks" or manifest["schemaVersion"] != 1:
        raise ValueError("Unexpected catalog or manifest schema")
    indexed = {(r["sku"], r["position"]): r for r in manifest["rows"]}
    if indexed.keys() != catalog.keys() or len(indexed) != len(manifest["rows"]):
        raise ValueError("Catalog positions differ from the manifest")
    archive_path = HERE / f"delivery-{number}.zip"
    with ZipFile(archive_path) as archive:
        with archive.open("manifest.json") as record:
            if json.load(TextIOWrapper(record, encoding="utf-8")) != manifest:
                raise ValueError("Embedded and saved manifests differ")
        expected = {"manifest.json"} | {r["fileName"] for r in indexed.values() if r["inArchive"]}
        if set(archive.namelist()) != expected or len(archive.namelist()) != len(expected):
            raise ValueError("Missing, unexpected or duplicate ZIP member")
        for row in indexed.values():
            if row["inArchive"]:
                body = archive.read(row["fileName"])
                if len(body) != row["bytes"] or hashlib.sha256(body).hexdigest() != row["sha256"]:
                    raise ValueError(f"Byte or SHA-256 mismatch for {row['fileName']}")
    print(f"Delivery {number} ZIP SHA-256: {hashlib.sha256(archive_path.read_bytes()).hexdigest()}")
    return catalog, indexed


def main():
    earlier_urls, previous = read_delivery(1)
    newer_urls, current = read_delivery(2)
    for key in sorted(current):
        old, new = previous.get(key), current[key]
        status = "new" if old is None else ("changed" if old["sha256"] != new["sha256"] else "unchanged")
        if status != new["status"] or (status != "unchanged") != new["inArchive"]:
            raise ValueError(f"Delta classification mismatch for {key}")
        print(f"{key[0]} position {key[1]}: {status}")
        if old and new["fileName"] != old["fileName"]:
            print(f"  After accepting the replacement, review the old path {old['fileName']}")
    if earlier_urls[("BOX-04", 1)] != newer_urls[("BOX-04", 1)]:
        raise ValueError("The stable-URL example changed its address")
    for sku, position in sorted(previous.keys() - current.keys()):
        print(f"{sku} position {position}: absent from this input; review before retiring")


if __name__ == "__main__":
    main()
