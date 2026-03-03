#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import datetime as dt
import difflib
import fnmatch
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import yaml

EXIT_HARD_FAIL = 24

REPO_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = REPO_ROOT / "02_audit_logging" / "reports"
EVIDENCE_TASKS_DIR = REPO_ROOT / "02_audit_logging" / "evidence" / "tasks"
REGISTRY_DIR = REPO_ROOT / "24_meta_orchestration" / "registry"
PREPROCESSING_DIR = REPO_ROOT / "24_meta_orchestration" / "pipelines" / "preprocessing"
ROOT_EXCEPTIONS_FILE = (
    REPO_ROOT / "23_compliance" / "exceptions" / "root_level_exceptions.yaml"
)

SOT_INPUT_FILES = [
    REPO_ROOT / "16_codex" / "ssid_master_definition_corrected_v1.1.1.md",
    REPO_ROOT / "16_codex" / "SSID_structure_level3_part1_MAX.md",
    REPO_ROOT / "16_codex" / "SSID_structure_level3_part2_MAX.md",
    REPO_ROOT / "16_codex" / "SSID_structure_level3_part3_MAX.md",
    REPO_ROOT / "16_codex" / "SSID_structure_gebuehren_abo_modelle.md",
    REPO_ROOT
    / "16_codex"
    / "SSID_structure_gebuehren_abo_modelle_ROOTS_16_21_ADDENDUM.md",
]

ROOTS_24 = [
    "01_ai_layer",
    "02_audit_logging",
    "03_core",
    "04_deployment",
    "05_documentation",
    "06_data_pipeline",
    "07_governance_legal",
    "08_identity_score",
    "09_meta_identity",
    "10_interoperability",
    "11_test_simulation",
    "12_tooling",
    "13_ui_layer",
    "14_zero_time_auth",
    "15_infra",
    "16_codex",
    "17_observability",
    "18_data_layer",
    "19_adapters",
    "20_foundation",
    "21_post_quantum_crypto",
    "22_datasets",
    "23_compliance",
    "24_meta_orchestration",
]

ALLOWED_EXTENSIONS_DEFAULT = [
    ".py",
    ".yaml",
    ".md",
    ".svg",
    ".json",
    ".csv",
    ".pdf",
    ".zip",
]

ALLOWED_FILENAMES_DEFAULT = {
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    "LICENSE",
    "NOTICE",
}

ALLOWED_PATH_GLOBS_DEFAULT = [
    ".github/workflows/*.yml",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
]


def utc_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def ts_slug(ts: str) -> str:
    return ts.replace("-", "").replace(":", "")


def sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: Dict[str, Any], dry_run: bool = False) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    rendered_bytes = rendered.encode("utf-8")
    if path.exists():
        existing_bytes = path.read_bytes()
        if existing_bytes == rendered_bytes:
            return False
    if dry_run:
        return True
    path.write_bytes(rendered_bytes)
    return True


def move_to_worm(source_path: Path, reason: str) -> Path | None:
    """Move a file or directory to the WORM archive instead of deleting."""
    if not source_path.exists():
        return None

    ts = utc_now()
    worm_dir = (
        REPO_ROOT / "02_audit_logging" / "storage" / "worm" / reason / ts_slug(ts)
    )
    worm_dir.mkdir(parents=True, exist_ok=True)

    target_path = worm_dir / source_path.name

    shutil.move(str(source_path), str(target_path))
    return target_path


def load_root_exceptions() -> Tuple[List[str], List[str]]:
    data = yaml.safe_load(ROOT_EXCEPTIONS_FILE.read_text(encoding="utf-8")) or {}
    dirs = data.get("allowed_directories", []) or []
    files = data.get("allowed_files", []) or []
    return sorted(set(dirs)), sorted(set(files))


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def is_preflight_allowed(rel_path: str) -> bool:
    p = Path(rel_path)
    ext = p.suffix
    name = p.name
    if ext in set(ALLOWED_EXTENSIONS_DEFAULT):
        return True
    if name in ALLOWED_FILENAMES_DEFAULT:
        return True
    if any(
        fnmatch.fnmatch(rel_path, pattern) for pattern in ALLOWED_PATH_GLOBS_DEFAULT
    ):
        return True
    return False


def iter_files() -> Iterable[Path]:
    for p in REPO_ROOT.rglob("*"):
        if ".git" in p.parts:
            continue
        if "__pycache__" in p.parts:
            continue
        if ".venv" in p.parts:
            continue
        if ".pytest_cache" in p.parts:
            continue
        if p.is_file():
            if p.suffix == ".pyc":
                continue
            yield p


def root_scan() -> List[Dict[str, Any]]:
    allowed_dirs, allowed_files = load_root_exceptions()
    out: List[Dict[str, Any]] = []
    for item in sorted(REPO_ROOT.iterdir(), key=lambda x: x.name):
        if item.name == ".git":
            continue
        is_module = item.is_dir() and re.match(r"^\d{2}_.+", item.name) is not None
        status = "violation"
        reason = "not_allowed"
        if is_module:
            status = "allowed"
            reason = "root_module"
        elif item.is_dir() and item.name in allowed_dirs:
            status = "allowed"
            reason = "root_exception_directory"
        elif item.is_file() and item.name in allowed_files:
            status = "allowed"
            reason = "root_exception_file"
        out.append(
            {
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "status": status,
                "reason": reason,
            }
        )
    return out


def extract_paths_from_sot(file_path: Path) -> List[str]:
    if not file_path.exists():
        return []
    text = file_path.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(r"(?<![A-Za-z0-9_./-])(?:\d{2}_[A-Za-z0-9_./-]+)")
    found = [m.group(0).strip().strip("`\"'") for m in pattern.finditer(text)]
    out: List[str] = []
    for p in found:
        p = p.rstrip(".,:;)")
        if "/" not in p:
            continue
        if p.startswith("http://") or p.startswith("https://"):
            continue
        if p and p not in out:
            out.append(p)
    return out


def duplicate_guard() -> Tuple[bool, List[str]]:
    issues: List[str] = []

    contract = REPO_ROOT / "16_codex" / "contracts" / "sot" / "sot_contract.yaml"
    if contract.exists():
        txt = contract.read_text(encoding="utf-8")
        ids = re.findall(r"\brule_id\s*:\s*['\"]?([A-Za-z0-9_.:-]+)['\"]?", txt)
        duplicates = sorted({v for v in ids if ids.count(v) > 1})
        if duplicates:
            issues.append(f"duplicate rule_id in sot_contract.yaml: {duplicates}")

    py = REPO_ROOT / "03_core" / "validators" / "sot" / "sot_validator_core.py"
    if py.exists():
        tree = ast.parse(py.read_text(encoding="utf-8"))
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        duplicates = sorted({f for f in funcs if funcs.count(f) > 1})
        if duplicates:
            issues.append(
                f"duplicate function names in sot_validator_core.py: {duplicates}"
            )

    rego = REPO_ROOT / "23_compliance" / "policies" / "sot" / "sot_policy.rego"
    if rego.exists():
        txt = rego.read_text(encoding="utf-8")
        names = re.findall(r"(?m)^([A-Za-z0-9_]+)\[", txt)
        names = [n for n in names if n != "package"]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            issues.append(f"duplicate rego rule names in sot_policy.rego: {duplicates}")

    cli = REPO_ROOT / "12_tooling" / "cli" / "sot_validator.py"
    if cli.exists():
        txt = cli.read_text(encoding="utf-8")
        flags = re.findall(r"add_argument\(\s*['\"](--[A-Za-z0-9_-]+)['\"]", txt)
        duplicates = sorted({f for f in flags if flags.count(f) > 1})
        if duplicates:
            issues.append(f"duplicate CLI flags in sot_validator.py: {duplicates}")

    test = (
        REPO_ROOT / "11_test_simulation" / "tests_compliance" / "test_sot_validator.py"
    )
    if test.exists():
        tree = ast.parse(test.read_text(encoding="utf-8"))
        funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
        duplicates = sorted({f for f in funcs if funcs.count(f) > 1})
        if duplicates:
            issues.append(
                f"duplicate test names in test_sot_validator.py: {duplicates}"
            )

    return len(issues) == 0, issues


def run_cmd(name: str, cmd: List[str]) -> Dict[str, Any]:
    p = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
    return {
        "name": name,
        "cmd": cmd,
        "returncode": p.returncode,
        "stdout_sha256": sha256_bytes(p.stdout.encode("utf-8", errors="replace")),
        "stderr_sha256": sha256_bytes(p.stderr.encode("utf-8", errors="replace")),
        "stdout_tail_20": "\n".join((p.stdout or "").splitlines()[-20:]),
    }


def phase0_inventory(ts: str) -> Dict[str, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    files_payload = []
    for p in sorted(iter_files()):
        files_payload.append(
            {
                "path": rel(p),
                "bytes": p.stat().st_size,
                "sha256": sha256_file(p),
            }
        )
    inventory_path = REPORTS_DIR / f"INVENTORY_{ts_slug(ts)}.json"
    write_json(inventory_path, {"generated_utc": ts, "files": files_payload})

    root_items = root_scan()
    root_path = REPORTS_DIR / f"ROOT_EXCEPTIONS_CHECK_{ts_slug(ts)}.json"
    write_json(
        root_path,
        {
            "generated_utc": ts,
            "exit_code_on_violation": EXIT_HARD_FAIL,
            "root_items": root_items,
            "violations": [i for i in root_items if i["status"] == "violation"],
        },
    )

    missing_roots = [r for r in ROOTS_24 if not (REPO_ROOT / r).exists()]
    actual_modules = sorted(
        [
            p.name
            for p in REPO_ROOT.iterdir()
            if p.is_dir() and re.match(r"^\d{2}_.+", p.name)
        ]
    )
    unexpected_modules = [m for m in actual_modules if m not in ROOTS_24]
    sot_diff_path = REPORTS_DIR / f"SOT_STRUCT_DIFF_{ts_slug(ts)}.json"
    write_json(
        sot_diff_path,
        {
            "generated_utc": ts,
            "required_roots": ROOTS_24,
            "actual_root_modules": actual_modules,
            "missing_root_modules": missing_roots,
            "unexpected_root_modules": unexpected_modules,
            "root_module_count_ok": len(actual_modules) == 24,
        },
    )

    allowed_ext = set(ALLOWED_EXTENSIONS_DEFAULT)
    disallowed = []
    for p in iter_files():
        rp = rel(p)
        if not is_preflight_allowed(rp):
            disallowed.append(rp)
    preflight_path = REPORTS_DIR / f"POLICY_PREFLIGHT_{ts_slug(ts)}.json"
    dup_ok, dup_issues = duplicate_guard()
    write_json(
        preflight_path,
        {
            "generated_utc": ts,
            "exit_code_on_violation": EXIT_HARD_FAIL,
            "allowed_extensions": sorted(allowed_ext),
            "allowed_filenames": sorted(ALLOWED_FILENAMES_DEFAULT),
            "allowed_path_globs": ALLOWED_PATH_GLOBS_DEFAULT,
            "disallowed_files": sorted(disallowed),
            "duplicate_guard": {
                "status": "PASS" if dup_ok else "FAIL",
                "issues": dup_issues,
            },
        },
    )

    return {
        "inventory": inventory_path,
        "root_check": root_path,
        "sot_diff": sot_diff_path,
        "policy_preflight": preflight_path,
    }


def phase1_compile_structure_spec(
    ts: str, pdf_requirements: List[Dict[str, str]], dry_run: bool = False
) -> Tuple[Path, bool]:
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    allowed_dirs, allowed_files = load_root_exceptions()

    missing_inputs = [p for p in SOT_INPUT_FILES if not p.exists()]
    if missing_inputs:
        print("ERROR: Missing required SoT inputs:", file=sys.stderr)
        for p in missing_inputs:
            print(f"- {rel(p)}", file=sys.stderr)
        raise SystemExit(EXIT_HARD_FAIL)

    extracted_paths: List[str] = []
    for f in SOT_INPUT_FILES:
        for p in extract_paths_from_sot(f):
            if p not in extracted_paths:
                extracted_paths.append(p)

    mandatory_paths = sorted(
        set(
            ROOTS_24
            + [
                "24_meta_orchestration/dispatcher/e2e_dispatcher.py",
                "12_tooling/cli/ssid_dispatcher.py",
                "12_tooling/cli/run_all_gates.py",
                "23_compliance/exceptions/root_level_exceptions.yaml",
            ]
        )
    )
    optional_paths = sorted(set(extracted_paths))

    spec = {
        "source_of_truth_inputs": [rel(p) for p in SOT_INPUT_FILES],
        "paths": {
            "must": mandatory_paths,
            "optional": optional_paths,
        },
        "root_exceptions": {
            "allowed_directories": allowed_dirs,
            "allowed_files": allowed_files,
            "module_count": 24,
            "exit_code_on_violation": EXIT_HARD_FAIL,
        },
        "forbidden_zones": [
            "24_meta_orchestration/registry/logs/",
        ],
        "file_format_rules": {
            "allowlist_extensions": ALLOWED_EXTENSIONS_DEFAULT,
            "allowlist_filenames": sorted(ALLOWED_FILENAMES_DEFAULT),
            "allowlist_path_globs": ALLOWED_PATH_GLOBS_DEFAULT,
        },
        "pdf_requirements": pdf_requirements,
    }
    out = REGISTRY_DIR / "structure_spec.json"
    wrote = write_json(out, spec, dry_run=dry_run)
    return out, wrote


def phase2_generate_move_plan(
    ts: str, structure_spec_path: Path, root_check_path: Path
) -> Path:
    PREPROCESSING_DIR.mkdir(parents=True, exist_ok=True)
    spec = json.loads(structure_spec_path.read_text(encoding="utf-8"))
    root_check = json.loads(root_check_path.read_text(encoding="utf-8"))

    moves: List[Dict[str, Any]] = []
    creates: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    root_violations = root_check.get("violations", [])

    for v in root_violations:
        name = v["name"]
        source = REPO_ROOT / name
        if name == "e2e_dispatcher.py":
            target = (
                REPO_ROOT / "24_meta_orchestration" / "dispatcher" / "e2e_dispatcher.py"
            )
            if target.exists():
                worm_target = (
                    REPO_ROOT
                    / "02_audit_logging"
                    / "storage"
                    / "worm"
                    / "root_level_violations"
                    / ts_slug(ts)
                    / name
                )
                moves.append(
                    {
                        "from": name,
                        "to": rel(worm_target),
                        "reason": "root violation; canonical dispatcher already exists",
                        "rule_ref": "ROOT-24-LOCK:A1",
                    }
                )
            else:
                moves.append(
                    {
                        "from": name,
                        "to": rel(target),
                        "reason": "root violation canonicalization",
                        "rule_ref": "ROOT-24-LOCK:A1",
                    }
                )
        elif source.exists():
            target = REPO_ROOT / "05_documentation" / "legacy_root_items" / name
            if target.exists():
                worm_target = (
                    REPO_ROOT
                    / "02_audit_logging"
                    / "storage"
                    / "worm"
                    / "root_level_violations"
                    / ts_slug(ts)
                    / name
                )
                moves.append(
                    {
                        "from": name,
                        "to": rel(worm_target),
                        "reason": "root violation; legacy target exists",
                        "rule_ref": "ROOT-24-LOCK:A1",
                    }
                )
            else:
                moves.append(
                    {
                        "from": name,
                        "to": rel(target),
                        "reason": "root violation relocation",
                        "rule_ref": "ROOT-24-LOCK:A1",
                    }
                )

    for p in spec.get("paths", {}).get("must", []):
        abs_path = REPO_ROOT / p
        if not abs_path.exists():
            creates.append(
                {
                    "path": p,
                    "type": "directory" if p.endswith("/") else "file",
                    "reason": "missing mandatory path from structure_spec",
                }
            )

    move_plan = {
        "generated_utc": ts,
        "moves": moves,
        "creates": creates,
        "conflicts": conflicts,
        "root_violations": root_violations,
        "hard_stop_on_conflicts": True,
        "exit_code_on_conflict": EXIT_HARD_FAIL,
    }
    out = PREPROCESSING_DIR / f"move_plan_{ts_slug(ts)}.json"
    write_json(out, move_plan)
    return out


def apply_move_plan(move_plan_path: Path, task_id: str) -> Path:
    plan = json.loads(move_plan_path.read_text(encoding="utf-8"))
    if plan.get("conflicts"):
        raise SystemExit(EXIT_HARD_FAIL)

    evidence_dir = EVIDENCE_TASKS_DIR / task_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    before: Dict[str, bytes] = {}
    after: Dict[str, bytes] = {}
    touched: List[str] = []

    for m in plan.get("moves", []):
        src = REPO_ROOT / m["from"]
        dst = REPO_ROOT / m["to"]
        if not src.exists():
            continue
        if src.is_file():
            before[rel(src)] = src.read_bytes()
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        touched.extend([m["from"], m["to"]])
        if dst.exists() and dst.is_file():
            after[rel(dst)] = dst.read_bytes()

    for c in plan.get("creates", []):
        p = REPO_ROOT / c["path"]
        if p.exists():
            continue
        if c["type"] == "directory":
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("", encoding="utf-8")
            after[rel(p)] = p.read_bytes()
        touched.append(c["path"])

    gate_results: List[Dict[str, Any]] = []
    gate_results.append(
        run_cmd(
            "write_gate.structure_guard",
            [sys.executable, "12_tooling/scripts/structure_guard.py"],
        )
    )
    dup_ok, dup_issues = duplicate_guard()
    gate_results.append(
        {
            "name": "write_gate.duplicate_guard",
            "cmd": ["internal:duplicate_guard"],
            "returncode": 0 if dup_ok else EXIT_HARD_FAIL,
            "issues": dup_issues,
        }
    )
    gate_results.append(
        run_cmd(
            "inventory.preflight_check",
            [
                sys.executable,
                "12_tooling/scripts/deterministic_repo_setup.py",
                "phase0",
            ],
        )
    )
    gate_results.append(
        run_cmd(
            "sot_gate",
            [sys.executable, "12_tooling/cli/sot_validator.py", "--verify-all"],
        )
    )
    gate_results.append(
        run_cmd(
            "qa_master_suite",
            [
                sys.executable,
                "02_audit_logging/archives/qa_master_suite/qa_master_suite.py",
                "--mode",
                "minimal",
            ],
        )
    )
    gate_results.append(
        run_cmd(
            "ci_gate_mirror",
            [sys.executable, "12_tooling/cli/run_all_gates.py"],
        )
    )

    failed = [g for g in gate_results if g.get("returncode") != 0]

    patch_lines: List[str] = []
    for p, old_bytes in sorted(before.items()):
        old_txt = old_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
        new_bytes = after.get(p, b"")
        new_txt = new_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
        patch_lines.extend(
            difflib.unified_diff(
                old_txt, new_txt, fromfile=f"a/{p}", tofile=f"b/{p}", lineterm=""
            )
        )

    for p, new_bytes in sorted(after.items()):
        if p in before:
            continue
        new_txt = new_bytes.decode("utf-8", errors="replace").splitlines(keepends=True)
        patch_lines.extend(
            difflib.unified_diff(
                [], new_txt, fromfile="/dev/null", tofile=f"b/{p}", lineterm=""
            )
        )

    (evidence_dir / "patch.diff").write_text(
        "\n".join(patch_lines) + "\n", encoding="utf-8"
    )

    hash_manifest: Dict[str, Any] = {"generated_utc": utc_now(), "files": []}
    for p in sorted(set(touched)):
        abs_path = REPO_ROOT / p
        if abs_path.exists() and abs_path.is_file():
            hash_manifest["files"].append({"path": p, "sha256": sha256_file(abs_path)})
    write_json(evidence_dir / "hash_manifest.json", hash_manifest)

    write_json(
        evidence_dir / "gate_status.json",
        {
            "generated_utc": utc_now(),
            "gates": gate_results,
            "result": "PASS" if not failed else "FAIL",
        },
    )

    write_json(
        evidence_dir / "manifest.json",
        {
            "generated_utc": utc_now(),
            "task_id": task_id,
            "tool": "12_tooling/scripts/deterministic_repo_setup.py",
            "allowlist_extensions": ALLOWED_EXTENSIONS_DEFAULT,
            "move_plan": rel(move_plan_path),
            "result": "PASS" if not failed else "FAIL",
        },
    )

    if failed:
        raise SystemExit(EXIT_HARD_FAIL)
    return evidence_dir


def parse_pdf_rules(raw: List[str]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for item in raw:
        if "::" in item:
            rule_id, requirement = item.split("::", 1)
        else:
            rule_id, requirement = item, item
        out.append({"rule_ref": rule_id.strip(), "requirement": requirement.strip()})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="deterministic_repo_setup.py")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser(
        "phase0", help="Generate read-only inventory and policy preflight artefacts."
    )

    p1 = sub.add_parser(
        "phase1", help="Compile machine-readable structure spec from SoT and PDF rules."
    )
    p1.add_argument("--pdf-rule", action="append", default=[], help="rule_ref::text")
    p1.add_argument(
        "--check",
        action="store_true",
        help="Only compare, do not write. Exit 1 if drift detected.",
    )
    p1.add_argument(
        "--apply",
        action="store_true",
        help="Write files if changed (default: check only)",
    )

    p2 = sub.add_parser(
        "phase2", help="Generate move plan from root violations and structure spec."
    )
    p2.add_argument(
        "--structure-spec", default="24_meta_orchestration/registry/structure_spec.json"
    )
    p2.add_argument(
        "--root-check",
        default="",
        help="Optional explicit ROOT_EXCEPTIONS_CHECK json path",
    )

    p3 = sub.add_parser(
        "phase3", help="Apply move plan and run hard-gates with evidence."
    )
    p3.add_argument("--move-plan", required=True)
    p3.add_argument("--task-id", required=True)

    sub.add_parser(
        "policy_gate", help="Run policy preflight and fail on policy violations."
    )

    sub.add_parser("all", help="Run phase0 -> phase1 -> phase2 (no apply)")

    args = ap.parse_args()
    ts = utc_now()

    if args.cmd == "phase0":
        artefacts = phase0_inventory(ts)
        print(json.dumps({k: rel(v) for k, v in artefacts.items()}, indent=2))
        return 0

    if args.cmd == "phase1":
        dry_run = not args.apply
        out, wrote = phase1_compile_structure_spec(
            ts, parse_pdf_rules(args.pdf_rule), dry_run=dry_run
        )
        print(rel(out))
        if dry_run and wrote:
            print(
                f"DRIFT: {rel(out)} would be modified. Run with --apply to write.",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.cmd == "phase2":
        root_check = (
            Path(args.root_check)
            if args.root_check
            else REPORTS_DIR / f"ROOT_EXCEPTIONS_CHECK_{ts_slug(ts)}.json"
        )
        if not root_check.exists():
            artefacts = phase0_inventory(ts)
            root_check = artefacts["root_check"]
        out = phase2_generate_move_plan(ts, REPO_ROOT / args.structure_spec, root_check)
        print(rel(out))
        if json.loads(out.read_text(encoding="utf-8")).get("conflicts"):
            return EXIT_HARD_FAIL
        return 0

    if args.cmd == "phase3":
        evidence_dir = apply_move_plan(REPO_ROOT / args.move_plan, args.task_id)
        print(rel(evidence_dir))
        return 0

    if args.cmd == "policy_gate":
        artefacts = phase0_inventory(ts)
        preflight = json.loads(
            artefacts["policy_preflight"].read_text(encoding="utf-8")
        )
        duplicate_status = preflight.get("duplicate_guard", {}).get("status")
        has_disallowed = len(preflight.get("disallowed_files", [])) > 0
        if duplicate_status != "PASS" or has_disallowed:
            return EXIT_HARD_FAIL
        return 0

    if args.cmd == "all":
        artefacts = phase0_inventory(ts)
        phase1_compile_structure_spec(ts, [])
        move_plan = phase2_generate_move_plan(
            ts, REGISTRY_DIR / "structure_spec.json", artefacts["root_check"]
        )
        print(rel(move_plan))
        if json.loads(move_plan.read_text(encoding="utf-8")).get("conflicts"):
            return EXIT_HARD_FAIL
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
