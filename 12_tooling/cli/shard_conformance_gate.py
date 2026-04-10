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
import yaml

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


def _load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _repo_root_for_shard(sd: Path) -> Path:
    return sd.resolve().parents[2]


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


def _fixture_candidates(sd, token):
    fixtures_dir = sd / "conformance" / "fixtures"
    if not fixtures_dir.is_dir():
        return []
    return sorted(
        path
        for path in fixtures_dir.glob(f"*{token}*.json")
        if path.is_file()
    )


def _validate_against_any_schema(instance, schemas):
    errors = []
    for schema in schemas:
        try:
            jsonschema.validate(instance, schema)
            return True, []
        except jsonschema.ValidationError as exc:
            errors.append(exc.message)
    return False, errors


def _check_manifest_contract_consistency(sd, schema_paths):
    manifest_path = sd / "manifest.yaml"
    if not manifest_path.is_file():
        return False, [f"manifest.yaml missing in {sd.name}"]

    manifest = _load_yaml(manifest_path) or {}
    manifest_contracts = {
        Path(contract_path).as_posix()
        for contract_path in manifest.get("contracts", [])
        if isinstance(contract_path, str)
    }
    expected_contracts = {f"contracts/{path.name}" for path in schema_paths}

    missing_required = sorted(
        rel_path
        for rel_path in manifest_contracts
        if rel_path.startswith("contracts/") and not (sd / rel_path).is_file()
    )
    extra_actual = sorted(expected_contracts - manifest_contracts)
    if missing_required and not extra_actual:
        return False, [f"Missing required schemas: {missing_required}"]

    if manifest_contracts != expected_contracts:
        return False, [
            "manifest/contracts mismatch: "
            f"manifest={sorted(manifest_contracts)} actual={sorted(expected_contracts)}"
        ]

    return True, []


def _check_documentation_present(sd):
    return (sd / "README.md").is_file()


def _resolve_runtime(sd):
    runtime_path = sd / "runtime" / "index.yaml"
    if not runtime_path.is_file():
        return None, ["runtime/index.yaml missing"]
    runtime = _load_yaml(runtime_path) or {}
    if not isinstance(runtime, dict):
        return None, ["runtime/index.yaml is not a mapping"]
    return runtime, []


def _expected_runtime(root_name):
    if root_name == "03_core":
        return "wave03_reference", "Root03ReferenceWave"
    if root_name == "09_meta_identity":
        return "wave09_identity_services", "Root09IdentityServicesWave"
    if root_name == "07_governance_legal":
        return "wave07_security_enforcement", "Root07SecurityEnforcementWave"
    return None


def _check_runtime_capability(root_name, sd):
    runtime, violations = _resolve_runtime(sd)
    if runtime is None:
        return False, violations

    expected = _expected_runtime(root_name)
    if expected is None:
        return True, []

    expected_module, expected_factory = expected
    found_module = str(runtime.get("module", ""))
    found_factory = str(runtime.get("factory", ""))
    found_shard = str(runtime.get("shard_id", ""))

    issues = []
    if found_module != expected_module:
        issues.append(
            f"runtime capability mismatch: module={found_module!r} expected={expected_module!r}"
        )
    if found_factory != expected_factory:
        issues.append(
            f"runtime capability mismatch: factory={found_factory!r} expected={expected_factory!r}"
        )
    if found_shard != sd.name:
        issues.append(f"runtime capability mismatch: shard_id={found_shard!r} expected={sd.name!r}")

    for key in ("valid_input", "expected_output_schema"):
        rel = runtime.get(key)
        if not isinstance(rel, str) or not (sd / "runtime" / rel).resolve().exists():
            issues.append(f"runtime capability missing referenced file for {key}")

    return len(issues) == 0, issues


def _check_dependency_capability(sd):
    runtime, violations = _resolve_runtime(sd)
    if runtime is None:
        return False, violations

    repo_root = _repo_root_for_shard(sd)
    dependency_refs = runtime.get("dependency_refs", []) or []
    issues = []
    for dependency_ref in dependency_refs:
        if not isinstance(dependency_ref, str) or "/" not in dependency_ref:
            issues.append(f"cross-root runtime capability invalid dependency ref: {dependency_ref!r}")
            continue
        dep_root, dep_shard = dependency_ref.split("/", 1)
        dep_runtime = repo_root / dep_root / "shards" / dep_shard / "runtime" / "index.yaml"
        if not dep_runtime.is_file():
            issues.append(f"cross-root runtime capability missing dependency runtime: {dependency_ref}")

    return len(issues) == 0, issues


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
    if not (sd / "conformance" / "fixtures").is_dir():
        return False, ["conformance/fixtures/ directory missing"]
    vf = [path for path in _fixture_candidates(sd, "valid") if "invalid" not in path.name]
    if not vf:
        return False, ["No valid*.json fixtures found"]
    viols = []
    for f in vf:
        try:
            inst = _load_json(f)
            passed, errors = _validate_against_any_schema(inst, schemas)
            if not passed:
                viols.append(f"{f.name} failed validation: {errors[0]}")
        except jsonschema.ValidationError as e:
            viols.append(f"{f.name} failed validation: {e.message}")
        except json.JSONDecodeError as e:
            viols.append(f"{f.name} JSON parse error: {e}")
    return len(viols) == 0, viols


def _check_invalid_fixtures(sd, schemas):
    if not (sd / "conformance" / "fixtures").is_dir():
        return False, ["conformance/fixtures/ directory missing"]
    ivf = _fixture_candidates(sd, "invalid")
    if not ivf:
        return False, ["No invalid*.json fixtures found"]
    viols = []
    for f in ivf:
        try:
            inst = _load_json(f)
            passed, _errors = _validate_against_any_schema(inst, schemas)
            if passed:
                viols.append(f"{f.name} should fail validation but passed")
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
        ok, v = _check_manifest_contract_consistency(sd, sp)
        checks["manifest_contract_consistent"] = ok
        all_v.extend(v)
        if not ok:
            ec = max(ec, 2 if any("Missing required schemas" in item for item in v) else 1)

        ok, schemas, v = _check_schema_valid(sp)
        checks["schema_valid"] = ok
        all_v.extend(v)
        if not ok:
            ec = 2
    else:
        checks["manifest_contract_consistent"] = False
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

    checks["documentation_present"] = _check_documentation_present(sd)
    if not checks["documentation_present"] and ec == 0:
        ec = 1
        all_v.append("documentation missing: README.md")

    runtime_ok, runtime_v = _check_runtime_capability(root_name, sd)
    checks["runtime_capability"] = runtime_ok
    dependency_ok, dependency_v = _check_dependency_capability(sd)
    checks["dependency_capability"] = dependency_ok
    checks["cross_root_runtime_capability"] = runtime_ok and dependency_ok
    checks["security_capability"] = runtime_ok if root_name == "07_governance_legal" else False
    checks["security_enforcement_capability"] = (
        runtime_ok and dependency_ok if root_name == "07_governance_legal" else False
    )

    if root_name in {"03_core", "09_meta_identity", "07_governance_legal"}:
        all_v.extend(runtime_v)
        if not runtime_ok:
            ec = max(ec, 2)
    if root_name in {"09_meta_identity", "07_governance_legal"}:
        if root_name == "07_governance_legal":
            all_v.extend(
                violation.replace(
                    "cross-root runtime capability",
                    "security enforcement capability",
                )
                for violation in dependency_v
            )
        else:
            all_v.extend(dependency_v)
        if not dependency_ok:
            ec = max(ec, 2)

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
