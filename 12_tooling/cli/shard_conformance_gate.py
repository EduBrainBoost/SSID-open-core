#!/usr/bin/env python3
"""TS014: Shard Conformance Gate - validates contracts, schemas, PII denial, and fixtures.

Exit codes: 0=PASS, 1=FAIL, 2=ERROR

Usage:
    shard_conformance_gate.py --root 03_core --shard 01_identitaet_personen
    shard_conformance_gate.py --root 03_core --all-shards
    shard_conformance_gate.py --root 03_core --all-shards --report report.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import jsonschema

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PII_DENY_PATTERNS = [
    re.compile(r"(?i)\b(ssn|social.?security)\b"),
    re.compile(r"(?i)\b(passport.?number)\b"),
    re.compile(r"(?i)\b(date.?of.?birth|dob)\b"),
    re.compile(r"(?i)\b(full.?name|first.?name|last.?name|surname)\b"),
    re.compile(r"(?i)\b(email.?address|e.?mail)\b"),
    re.compile(r"(?i)\b(phone.?number|mobile.?number|telefon)\b"),
    re.compile(r"(?i)\b(street.?address|postal.?address|home.?address)\b"),
    re.compile(r"(?i)\b(credit.?card|bank.?account|iban)\b"),
    re.compile(r"(?i)\b(national.?id|personalausweis|ausweisnummer)\b"),
    re.compile(r"(?i)\b(biometric|fingerprint|retina)\b"),
    re.compile(r"(?i)\b(geolocation|gps.?coord)\b"),
    re.compile(r"(?i)\b(ip.?address)\b"),
]
URL_DENY = re.compile(r"https?://[^\s\"\x27,}]+")


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _walk_pii(obj, path, viols):
    if not isinstance(obj, dict):
        return
    props = obj.get("properties", {})
    if isinstance(props, dict):
        for key in props:
            fp = f"{path}.{key}" if path else key
            for pat in PII_DENY_PATTERNS:
                if pat.search(key):
                    viols.append(f"PII key denied: {fp!r} matches {pat.pattern}")
                    break
            _walk_pii(props[key], fp, viols)
    for sk in ("items", "additionalProperties"):
        if sk in obj and isinstance(obj[sk], dict):
            _walk_pii(obj[sk], f"{path}[{sk}]", viols)


def _walk_url(obj, path, viols):
    if not isinstance(obj, dict):
        return
    for ck in ("default", "const"):
        val = obj.get(ck)
        if isinstance(val, str) and URL_DENY.search(val):
            viols.append(f"URL in {ck} at {path!r}: {val}")
    ev = obj.get("enum")
    if isinstance(ev, list):
        for item in ev:
            if isinstance(item, str) and URL_DENY.search(item):
                viols.append(f"URL in enum at {path!r}: {item}")
    for key, val in obj.items():
        if isinstance(val, dict):
            _walk_url(val, f"{path}.{key}" if path else key, viols)


def _check_contracts_exist(sd):
    cd = sd / "contracts"
    if not cd.is_dir():
        return False, [], [f"contracts/ directory missing in {sd.name}"]
    schemas = sorted(cd.glob("*.schema.json"))
    if not schemas:
        return False, [], [f"No *.schema.json files in {sd.name}/contracts/"]
    return True, schemas, []


def _check_schema_valid(schema_paths):
    loaded, viols = [], []
    for sp in schema_paths:
        try:
            schema = _load_json(sp)
            jsonschema.validators.validator_for(schema).check_schema(schema)
            loaded.append(schema)
        except json.JSONDecodeError as e:
            viols.append(f"JSON parse error in {sp.name}: {e}")
        except jsonschema.SchemaError as e:
            viols.append(f"Schema error in {sp.name}: {e.message}")
    return len(viols) == 0, loaded, viols


def _check_pii_denial(schemas, schema_paths):
    viols = []
    for schema, sp in zip(schemas, schema_paths):
        pv, uv = [], []
        _walk_pii(schema, "", pv)
        _walk_url(schema, "", uv)
        for v in pv:
            viols.append(f"{sp.name}: {v}")
        for v in uv:
            viols.append(f"{sp.name}: {v}")
    return viols


def _check_valid_fixtures(sd, schemas):
    fd = sd / "conformance" / "fixtures"
    if not fd.is_dir():
        return False, ["conformance/fixtures/ directory missing"]
    vf = sorted(fd.glob("valid*.json"))
    if not vf:
        return False, ["No valid*.json fixtures found"]
    viols = []
    schema = schemas[0]
    for f in vf:
        try:
            inst = _load_json(f)
            jsonschema.validate(inst, schema)
        except jsonschema.ValidationError as e:
            viols.append(f"{f.name} failed validation: {e.message}")
        except json.JSONDecodeError as e:
            viols.append(f"{f.name} JSON parse error: {e}")
    return len(viols) == 0, viols


def _check_invalid_fixtures(sd, schemas):
    fd = sd / "conformance" / "fixtures"
    if not fd.is_dir():
        return False, ["conformance/fixtures/ directory missing"]
    ivf = sorted(fd.glob("invalid*.json"))
    if not ivf:
        return False, ["No invalid*.json fixtures found"]
    viols = []
    schema = schemas[0]
    for f in ivf:
        try:
            inst = _load_json(f)
            jsonschema.validate(inst, schema)
            viols.append(f"{f.name} should fail validation but passed")
        except jsonschema.ValidationError:
            pass
        except json.JSONDecodeError as e:
            viols.append(f"{f.name} JSON parse error: {e}")
    return len(viols) == 0, viols


def _check_shard(root_name, sd):
    checks, all_v, ec = {}, [], 0
    ok, sp, v = _check_contracts_exist(sd)
    checks["contracts_exist"] = ok
    all_v.extend(v)
    if not ok:
        ec = 2
    if sp:
        ok, schemas, v = _check_schema_valid(sp)
        checks["schema_valid"] = ok
        all_v.extend(v)
        if not ok:
            ec = 2
    else:
        checks["schema_valid"] = False
        schemas = []
    if schemas:
        v = _check_pii_denial(schemas, sp)
        checks["pii_denial"] = len(v) == 0
        all_v.extend(v)
        if v and ec == 0:
            ec = 1
    else:
        checks["pii_denial"] = False
    if schemas:
        ok, v = _check_valid_fixtures(sd, schemas)
        checks["valid_fixtures_pass"] = ok
        all_v.extend(v)
        if not ok and ec == 0:
            ec = 1
    else:
        checks["valid_fixtures_pass"] = False
    if schemas:
        ok, v = _check_invalid_fixtures(sd, schemas)
        checks["invalid_fixtures_rejected"] = ok
        all_v.extend(v)
        if not ok and ec == 0:
            ec = 1
    else:
        checks["invalid_fixtures_rejected"] = False
    verdict = "PASS" if ec == 0 else ("ERROR" if ec == 2 else "FAIL")
    return {"shard": sd.name, "verdict": verdict, "exit_code": ec, "checks": checks, "violations": all_v}


def main():
    ap = argparse.ArgumentParser(prog="shard_conformance_gate.py",
        description="Gate: validate contracts, schemas, PII denial, and conformance fixtures.")
    ap.add_argument("--root", required=True, help="Root dirname (e.g. 03_core)")
    sg = ap.add_mutually_exclusive_group(required=True)
    sg.add_argument("--shard", type=str, help="Single shard name")
    sg.add_argument("--all-shards", action="store_true", help="Check all shards with contracts/")
    ap.add_argument("--report", type=str, help="Write JSON report to path")
    args = ap.parse_args()
    rd = PROJECT_ROOT / args.root
    if not rd.is_dir():
        print(f"ERROR: Root directory not found: {rd}")
        return 2
    if args.all_shards:
        sb = rd / "shards"
        if not sb.is_dir():
            print(f"ERROR: No shards/ in {args.root}")
            return 2
        shard_dirs = sorted(d for d in sb.iterdir() if d.is_dir() and (d / "contracts").is_dir())
    else:
        sd = rd / "shards" / args.shard
        if not sd.is_dir():
            print(f"ERROR: Shard directory not found: {sd}")
            return 2
        shard_dirs = [sd]
    if not shard_dirs:
        print(f"INFO: No shards with contracts/ found in {args.root}")
        return 0
    results, worst = [], 0
    for sd in shard_dirs:
        r = _check_shard(args.root, sd)
        results.append(r)
        worst = max(worst, r["exit_code"])
    overall = "PASS" if worst == 0 else ("ERROR" if worst == 2 else "FAIL")
    report = {"gate": "shard_conformance_gate", "root": args.root,
              "overall_verdict": overall, "shard_count": len(results), "results": results}
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"REPORT: {args.report}")
    for r in results:
        if r["verdict"] != "PASS":
            for v in r["violations"]:
                verd = r["verdict"]
                sname = r["shard"]
                print(f"{verd}: {args.root}/shards/{sname} -- {v}")
        else:
            sname = r["shard"]
            print(f"PASS: {args.root}/shards/{sname}")
    print(f"\n{overall}: {len(results)} shards checked")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
