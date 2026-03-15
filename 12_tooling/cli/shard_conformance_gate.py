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
import importlib
import json
import re
import sys
from datetime import datetime, timezone
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
REQUIRED_SCHEMA_FILES = [
    "inputs.schema.json",
    "outputs.schema.json",
    "events.schema.json",
]
VALID_FIXTURE_NAME = "fixture_valid.json"
INVALID_FIXTURE_NAME = "fixture_invalid.json"


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
    schemas = [cd / name for name in REQUIRED_SCHEMA_FILES if (cd / name).exists()]
    missing = [name for name in REQUIRED_SCHEMA_FILES if not (cd / name).exists()]
    if missing:
        return False, [], [f"Missing required schemas in {sd.name}/contracts/: {', '.join(missing)}"]
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
    vf = [fd / VALID_FIXTURE_NAME]
    if not vf[0].exists():
        return False, [f"Missing {VALID_FIXTURE_NAME}"]
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
    ivf = [fd / INVALID_FIXTURE_NAME]
    if not ivf[0].exists():
        return False, [f"Missing {INVALID_FIXTURE_NAME}"]
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


def _check_manifest_contract_refs(sd):
    manifest_path = sd / "manifest.yaml"
    chart_path = sd / "chart.yaml"
    if not manifest_path.exists():
        return False, ["manifest.yaml missing"]
    if not chart_path.exists():
        return False, ["chart.yaml missing"]
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        chart = yaml.safe_load(chart_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return False, [f"YAML parse failure: {exc}"]
    def _normalize_contract_path(value: str) -> str:
        parts = Path(value).as_posix().split("/")
        return "/".join(parts[-2:]) if len(parts) >= 2 else parts[-1]

    manifest_contracts = {_normalize_contract_path(value) for value in (manifest.get("contracts", []) or [])}
    chart_contracts = {_normalize_contract_path(value) for value in (chart.get("contracts", {}).get("paths", []) or [])}
    if not manifest_contracts:
        return False, ["manifest.yaml has no contracts entries"]
    if chart_contracts and not chart_contracts.issubset(manifest_contracts):
        return False, ["manifest/contracts mismatch with chart/contracts"]
    if not manifest.get("evidence_outputs"):
        return False, ["manifest.yaml missing evidence_outputs"]
    return True, []


def _check_readme(sd):
    if (sd / "README.md").exists() or (sd / "RUNBOOK.md").exists():
        return True, []
    return False, ["README.md or RUNBOOK.md missing"]


def _check_runtime_capability(root_name, sd, schemas):
    runtime_index = sd / "runtime" / "index.yaml"
    if not runtime_index.exists():
        return True, []
    try:
        runtime_spec = yaml.safe_load(runtime_index.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return False, [f"runtime capability descriptor unreadable: {exc}"]
    module_name = runtime_spec.get("module")
    factory_name = runtime_spec.get("factory")
    shard_id = runtime_spec.get("shard_id")
    valid_input = runtime_spec.get("valid_input")
    if not all([module_name, factory_name, shard_id, valid_input]):
        return False, ["runtime capability descriptor incomplete"]
    source_dirs = [PROJECT_ROOT / "03_core" / "src", PROJECT_ROOT / root_name / "src"]
    for source_dir in source_dirs:
        if str(source_dir) not in sys.path:
            sys.path.insert(0, str(source_dir))
    try:
        module = importlib.import_module(module_name)
        factory = getattr(module, factory_name)
        repo_root = sd.parents[2]
        payload_path = (sd / "runtime" / valid_input).resolve()
        payload = _load_json(payload_path)
        runtime = factory(repo_root)
        result, evidence = runtime.run(shard_id, payload)
        jsonschema.validate(result, schemas[1])
        if not Path(evidence.audit_event).exists():
            return False, [f"runtime capability audit missing: {evidence.audit_event}"]
    except Exception as exc:
        return False, [f"runtime capability failed: {exc}"]
    return True, []


def _check_cross_root_runtime_capability(sd):
    repo_root = sd.parents[2]
    runtime_index = sd / "runtime" / "index.yaml"
    if not runtime_index.exists():
        return True, []
    try:
        runtime_spec = yaml.safe_load(runtime_index.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return False, [f"cross-root runtime capability descriptor unreadable: {exc}"]
    dependency_refs = runtime_spec.get("dependency_refs", []) or []
    if not dependency_refs:
        return True, []
    missing: list[str] = []
    for dependency_ref in dependency_refs:
        dep_root, dep_shard = str(dependency_ref).split("/", 1)
        dep_runtime = repo_root / dep_root / "shards" / dep_shard / "runtime" / "index.yaml"
        if not dep_runtime.is_file():
            missing.append(dependency_ref)
    if missing:
        return False, [f"cross-root runtime capability failed: missing dependencies {', '.join(missing)}"]
    return True, []


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
    if schemas:
        ok, v = _check_runtime_capability(root_name, sd, schemas)
        checks["runtime_capability"] = ok
        if root_name == "07_governance_legal":
            checks["security_capability"] = ok
        all_v.extend(v)
        if not ok:
            ec = 2
    else:
        checks["runtime_capability"] = False
        if root_name == "07_governance_legal":
            checks["security_capability"] = False
    ok, v = _check_cross_root_runtime_capability(sd)
    checks["dependency_capability"] = ok
    checks["cross_root_runtime_capability"] = ok
    if root_name == "07_governance_legal":
        checks["security_enforcement_capability"] = ok
        if not ok:
            all_v.append("security enforcement capability failed")
    all_v.extend(v)
    if not ok:
        ec = 2
    ok, v = _check_manifest_contract_refs(sd)
    checks["manifest_contract_consistent"] = ok
    all_v.extend(v)
    if not ok and ec == 0:
        ec = 1
    ok, v = _check_readme(sd)
    checks["documentation_present"] = ok
    all_v.extend(v)
    if not ok and ec == 0:
        ec = 1
    verdict = "PASS" if ec == 0 else ("ERROR" if ec == 2 else "FAIL")
    return {
        "root_id": root_name,
        "shard": sd.name,
        "verdict": verdict,
        "exit_code": ec,
        "checks": checks,
        "violations": all_v,
        "verified_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _resolve_shard_dirs(root_name: str, single_shard: str | None, all_shards: bool) -> tuple[list[Path], int | None]:
    rd = PROJECT_ROOT / root_name
    if not rd.is_dir():
        print(f"ERROR: Root directory not found: {rd}")
        return [], 2
    if all_shards:
        sb = rd / "shards"
        if not sb.is_dir():
            print(f"ERROR: No shards/ in {root_name}")
            return [], 2
        return sorted(d for d in sb.iterdir() if d.is_dir()), None
    sd = rd / "shards" / str(single_shard)
    if not sd.is_dir():
        print(f"ERROR: Shard directory not found: {sd}")
        return [], 2
    return [sd], None


def _summarize_results(results: list[dict]) -> dict:
    overall = "PASS"
    worst = 0
    for result in results:
        worst = max(worst, result["exit_code"])
    if worst == 2:
        overall = "ERROR"
    elif worst == 1:
        overall = "FAIL"
    return {
        "overall_verdict": overall,
        "shard_count": len(results),
        "results": results,
    }


def main():
    ap = argparse.ArgumentParser(prog="shard_conformance_gate.py",
        description="Gate: validate contracts, schemas, PII denial, and conformance fixtures.")
    root_group = ap.add_mutually_exclusive_group(required=True)
    root_group.add_argument("--root", help="Root dirname (e.g. 03_core)")
    root_group.add_argument("--all-roots", action="store_true", help="Check all canonical roots")
    sg = ap.add_mutually_exclusive_group(required=True)
    sg.add_argument("--shard", type=str, help="Single shard name")
    sg.add_argument("--all-shards", action="store_true", help="Check all shards with contracts/")
    ap.add_argument("--report", type=str, help="Write JSON report to path")
    args = ap.parse_args()

    roots = [args.root] if args.root else sorted(
        p.name for p in PROJECT_ROOT.iterdir() if p.is_dir() and p.name[:2].isdigit() and "_" in p.name
    )
    all_results: list[dict] = []
    for root_name in roots:
        shard_dirs, exit_code = _resolve_shard_dirs(root_name, args.shard, args.all_shards)
        if exit_code is not None:
            return exit_code
        if not shard_dirs:
            continue
        for sd in shard_dirs:
            all_results.append(_check_shard(root_name, sd))

    report = {
        "gate": "shard_conformance_gate",
        "root": args.root if args.root else "ALL_ROOTS",
        **_summarize_results(all_results),
    }
    if args.report:
        Path(args.report).write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"REPORT: {args.report}")
    for r in all_results:
        if r["verdict"] != "PASS":
            for v in r["violations"]:
                verd = r["verdict"]
                sname = r["shard"]
                root_name = r.get("root_id", args.root if args.root else "unknown_root")
                print(f"{verd}: {root_name}/shards/{sname} -- {v}")
        else:
            sname = r["shard"]
            root_name = r.get("root_id", args.root if args.root else "unknown_root")
            print(f"PASS: {root_name}/shards/{sname}")
    print(f"\n{report['overall_verdict']}: {len(all_results)} shards checked")
    return 0 if report["overall_verdict"] == "PASS" else (2 if report["overall_verdict"] == "ERROR" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
