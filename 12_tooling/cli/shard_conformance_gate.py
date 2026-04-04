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
    for schema, sp in zip(schemas, schema_paths, strict=False):
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


def _load_canonical_consumption_policy():
    """Dynamically load CanonicalConsumptionPolicy from 03_core/validators/runtime/."""
    import importlib.util

    module_path = PROJECT_ROOT / "03_core" / "validators" / "runtime" / "canonical_runtime_consumption.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("canonical_runtime_consumption", module_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "CanonicalConsumptionPolicy", None)


def _load_bypass_detector():
    """Dynamically load RuntimeBypassDetector from 03_core/validators/runtime/."""
    import importlib.util

    module_path = PROJECT_ROOT / "03_core" / "validators" / "runtime" / "runtime_bypass_detector.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("runtime_bypass_detector", module_path)
    if spec is None or spec.loader is None:
        return None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "RuntimeBypassDetector", None)


def _check_canonical_runtime_consumption(root_name, shard_dirs):
    """Run canonical runtime consumption checks on shards with runtime/index.yaml.

    Returns (passed, failed, findings_count, details).
    """
    PolicyCls = _load_canonical_consumption_policy()  # noqa: N806
    DetectorCls = _load_bypass_detector()  # noqa: N806

    if PolicyCls is None:
        print("WARNING: canonical_runtime_consumption.py not found, skipping consumption checks")
        return 0, 0, 0, []

    policy = PolicyCls(PROJECT_ROOT)
    detector = DetectorCls(PROJECT_ROOT) if DetectorCls else None

    passed, failed, total_findings = 0, 0, 0
    details = []

    for sd in shard_dirs:
        runtime_idx = sd / "runtime" / "index.yaml"
        if not runtime_idx.exists():
            continue

        shard_name = sd.name
        result = policy.validate_consumer(root_name, shard_name)

        bypass_findings = []
        if detector:
            bypass_findings = detector.scan_shard(root_name, shard_name)

        finding_count = len(result.findings) + len(bypass_findings)
        total_findings += finding_count

        if result.status == "pass" and not bypass_findings:
            passed += 1
            print(f"  PASS: {root_name}/shards/{shard_name} canonical consumption")
        else:
            failed += 1
            for f in result.findings:
                print(f"  FAIL: {root_name}/shards/{shard_name} -- {f.finding_code}: {f.detail}")
            for bf in bypass_findings:
                print(f"  FAIL: {root_name}/shards/{shard_name} -- BYPASS:{bf.pattern_type}: {bf.detail}")

        details.append(
            {
                "shard": shard_name,
                "status": "fail" if (result.status == "fail" or bypass_findings) else "pass",
                "consumption_findings": [f.to_dict() for f in result.findings],
                "bypass_findings": [bf.to_dict() for bf in bypass_findings],
            }
        )

    return passed, failed, total_findings, details


def main():
    ap = argparse.ArgumentParser(
        prog="shard_conformance_gate.py",
        description="Gate: validate contracts, schemas, PII denial, and conformance fixtures.",
    )
    ap.add_argument("--root", required=True, help="Root dirname (e.g. 03_core)")
    sg = ap.add_mutually_exclusive_group(required=True)
    sg.add_argument("--shard", type=str, help="Single shard name")
    sg.add_argument("--all-shards", action="store_true", help="Check all shards with contracts/")
    ap.add_argument("--report", type=str, help="Write JSON report to path")
    ap.add_argument(
        "--verify-canonical-runtime-consumption",
        action="store_true",
        help="Verify canonical runtime consumption patterns (WAVE_06)",
    )
    ap.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Fail on registry drift (implies --verify-canonical-runtime-consumption)",
    )
    args = ap.parse_args()
    if args.fail_on_drift:
        args.verify_canonical_runtime_consumption = True
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

    # --- WAVE_06: canonical runtime consumption checks ---
    consumption_report = {}
    if args.verify_canonical_runtime_consumption:
        print("\n--- Canonical Runtime Consumption (WAVE_06) ---")
        c_passed, c_failed, c_findings, c_details = _check_canonical_runtime_consumption(
            args.root,
            shard_dirs,
        )
        consumption_report = {
            "passed": c_passed,
            "failed": c_failed,
            "findings_count": c_findings,
            "details": c_details,
        }
        if c_failed > 0:
            if args.fail_on_drift:
                worst = max(worst, 1)
                print(f"FAIL: {c_failed} shard(s) with canonical consumption violations")
            else:
                print(f"WARN: {c_failed} shard(s) with canonical consumption violations (non-blocking)")
        if c_passed > 0:
            print(f"PASS: {c_passed} shard(s) canonical consumption OK")
        if c_passed == 0 and c_failed == 0:
            print("INFO: No shards with runtime/index.yaml found for consumption checks")

    overall = "PASS" if worst == 0 else ("ERROR" if worst == 2 else "FAIL")
    report = {
        "gate": "shard_conformance_gate",
        "root": args.root,
        "overall_verdict": overall,
        "shard_count": len(results),
        "results": results,
    }
    if consumption_report:
        report["canonical_runtime_consumption"] = consumption_report
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
