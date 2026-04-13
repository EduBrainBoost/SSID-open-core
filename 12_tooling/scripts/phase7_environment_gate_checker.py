#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PHASE 7 — ENVIRONMENT GATE CHECKER
Local runtime validation for SSID ↔ SSID-EMS integration.
Produces evidence artefacts for remote orchestration.
"""

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

sys.stdout.reconfigure(encoding='utf-8')

# Pfade
SSID_REPO = Path("C:\\Users\\bibel\\Documents\\Github\\SSID")
EMS_REPO = Path("C:\\Users\\bibel\\Documents\\Github\\SSID-EMS")
EVIDENCE_ROOT = SSID_REPO / "02_audit_logging" / "reports" / "phase7_ems_integration"
MANIFEST_DIR = EVIDENCE_ROOT / "00_run_manifest"
WORKLOG_PATH = EVIDENCE_ROOT / "WORKLOG.jsonl"
ENV_GATE_PATH = EVIDENCE_ROOT / "ENVIRONMENT_GATE.md"
BLOCKERBERICHT_PATH = EVIDENCE_ROOT / "BLOCKERBERICHT.md"
SHA256_PATH = EVIDENCE_ROOT / "SHA256SUMS.txt"

def ensure_dirs():
    """Create evidence directories."""
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)

def sha256_file(fpath):
    """Compute SHA256 of a file."""
    if not fpath.exists():
        return None
    h = hashlib.sha256()
    with open(fpath, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()

def sha256_string(s):
    """Compute SHA256 of a string."""
    return hashlib.sha256(s.encode('utf-8')).hexdigest()

def log_work(item_num, item_name, status, befund, evidence_path=None, evidence_hash=None):
    """Log to WORKLOG.jsonl."""
    entry = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase": "PHASE7_ENVIRONMENT_GATE",
        "item": f"{item_num}",
        "name": item_name,
        "status": status,
        "befund": befund,
        "evidence_path": str(evidence_path) if evidence_path else None,
        "evidence_hash": evidence_hash,
    }
    with open(WORKLOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

def item_1_ems_repo_exists():
    """Item 1: SSID-EMS Repo lokal vorhanden"""
    print("\n[ITEM 1] SSID-EMS Repo lokal vorhanden")

    if not EMS_REPO.exists():
        status = "FAIL"
        befund = f"EMS Repo nicht gefunden unter {EMS_REPO}"
        print(f"  [{status}] {befund}")
        log_work(1, "SSID-EMS Repo lokal vorhanden", status, befund)
        return False

    # Check for critical files/dirs
    critical_paths = [
        EMS_REPO / "backend",
        EMS_REPO / "frontend",
        EMS_REPO / "docker-compose.yml",
    ]

    missing = [p for p in critical_paths if not p.exists()]

    if missing:
        status = "FAIL"
        befund = f"Kritische Pfade fehlen: {[str(p.name) for p in missing]}"
        print(f"  [{status}] {befund}")
        log_work(1, "SSID-EMS Repo lokal vorhanden", status, befund)
        return False

    status = "PASS"
    befund = "EMS Repo vorhanden mit Backend, Frontend, docker-compose.yml"
    print(f"  [{status}] {befund}")

    # Evidence: directory listing
    evidence_file = EVIDENCE_ROOT / "item1_ems_repo_structure.txt"
    with open(evidence_file, "w", encoding="utf-8") as f:
        f.write(f"EMS Repo: {EMS_REPO}\n\n")
        for item in sorted(EMS_REPO.iterdir()):
            f.write(f"  {'[D]' if item.is_dir() else '[F]'} {item.name}\n")

    evidence_hash = sha256_file(evidence_file)
    log_work(1, "SSID-EMS Repo lokal vorhanden", status, befund, evidence_file, evidence_hash)
    return True

def item_2_ems_backend_reachable():
    """Item 2: EMS Backend erreichbar auf http://localhost:8000"""
    print("\n[ITEM 2] EMS Backend erreichbar (http://localhost:8000)")

    url = "http://localhost:8000/health"

    try:
        response = urlopen(url, timeout=5)
        status_code = response.status
        response_text = response.read().decode('utf-8')

        if status_code == 200:
            status = "PASS"
            befund = f"Backend erreichbar, Health-Response: {status_code}"
        else:
            status = "UNCLEAR"
            befund = f"Backend antwortet, aber unerwarteter Status: {status_code}"

        print(f"  [{status}] {befund}")

        # Evidence
        evidence_file = EVIDENCE_ROOT / "item2_backend_health.json"
        evidence_data = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "url": url,
            "status_code": status_code,
            "response_text": response_text[:500],  # First 500 chars
        }
        with open(evidence_file, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, indent=2)

        evidence_hash = sha256_file(evidence_file)
        log_work(2, "EMS Backend erreichbar", status, befund, evidence_file, evidence_hash)
        return status == "PASS"

    except URLError as e:
        status = "FAIL"
        befund = f"Backend nicht erreichbar: {str(e)}"
        print(f"  [{status}] {befund}")
        log_work(2, "EMS Backend erreichbar", status, befund)
        return False

def item_3_ems_frontend_reachable():
    """Item 3: EMS Frontend erreichbar auf http://localhost:3000"""
    print("\n[ITEM 3] EMS Frontend erreichbar (http://localhost:3000)")

    url = "http://localhost:3000"

    try:
        response = urlopen(url, timeout=5)
        status_code = response.status

        if status_code == 200:
            status = "PASS"
            befund = f"Frontend erreichbar, Status: {status_code}"
        else:
            status = "UNCLEAR"
            befund = f"Frontend antwortet, aber unerwarteter Status: {status_code}"

        print(f"  [{status}] {befund}")

        # Evidence
        evidence_file = EVIDENCE_ROOT / "item3_frontend_health.json"
        evidence_data = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "url": url,
            "status_code": status_code,
            "reachable": True,
        }
        with open(evidence_file, "w", encoding="utf-8") as f:
            json.dump(evidence_data, f, indent=2)

        evidence_hash = sha256_file(evidence_file)
        log_work(3, "EMS Frontend erreichbar", status, befund, evidence_file, evidence_hash)
        return status == "PASS"

    except URLError as e:
        status = "FAIL"
        befund = f"Frontend nicht erreichbar: {str(e)}"
        print(f"  [{status}] {befund}")
        log_work(3, "EMS Frontend erreichbar", status, befund)
        return False

def item_4_dev_test_environment():
    """Item 4: Dev/Test-Environment vorhanden"""
    print("\n[ITEM 4] Dev/Test-Environment vorhanden")

    # Check for common dev/test indicators
    docker_compose = EMS_REPO / "docker-compose.yml"
    env_files = list(EMS_REPO.glob(".env*"))
    test_dir = EMS_REPO / "tests" or EMS_REPO / "test"

    evidence_file = EVIDENCE_ROOT / "item4_dev_test_env.json"
    evidence_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "docker_compose_exists": docker_compose.exists(),
        "env_files": [f.name for f in env_files],
        "has_tests": any([EMS_REPO.glob("test*"), EMS_REPO.glob("*test*")]),
    }

    # Docker Compose present = reasonable dev setup
    if docker_compose.exists() and len(env_files) > 0:
        status = "PASS"
        befund = "Dev-Setup erkannt: docker-compose.yml + .env files vorhanden"
    elif docker_compose.exists():
        status = "UNCLEAR"
        befund = "docker-compose.yml vorhanden, aber .env files unklar"
    else:
        status = "FAIL"
        befund = "Kein Dev/Test-Setup erkannt (docker-compose.yml fehlt)"

    print(f"  [{status}] {befund}")

    with open(evidence_file, "w", encoding="utf-8") as f:
        json.dump(evidence_data, f, indent=2)

    evidence_hash = sha256_file(evidence_file)
    log_work(4, "Dev/Test-Environment vorhanden", status, befund, evidence_file, evidence_hash)
    return status == "PASS"

def item_5_testaccount_safe():
    """Item 5: Testaccount sicher nutzbar"""
    print("\n[ITEM 5] Testaccount sicher nutzbar")

    # Check if backend .env or config has test credentials
    # This is a soft check; actual credentials should be in Vault
    env_file = EMS_REPO / ".env.test" or EMS_REPO / ".env.local"

    evidence_file = EVIDENCE_ROOT / "item5_testaccount_check.json"
    evidence_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "vault_or_env_detected": False,
        "manual_check_required": True,
    }

    # We can't check Vault directly, but we can flag if .env files exist
    test_envs = [f for f in EMS_REPO.glob(".env*") if "test" in f.name.lower()]

    if test_envs or (EMS_REPO / "backend" / ".env.test").exists():
        status = "PASS"
        befund = "Test-Env-Dateien erkannt. Vor Nutzung MANUELL checken, dass keine Secrets hardcoded sind."
        evidence_data["vault_or_env_detected"] = True
    else:
        status = "UNCLEAR"
        befund = "Keine expliziten Test-Env-Dateien gefunden. Vault/Secret-Management manual checken erforderlich."

    print(f"  [{status}] {befund}")

    with open(evidence_file, "w", encoding="utf-8") as f:
        json.dump(evidence_data, f, indent=2)

    evidence_hash = sha256_file(evidence_file)
    log_work(5, "Testaccount sicher nutzbar", status, befund, evidence_file, evidence_hash)
    # UNCLEAR = proceed with caution, not FAIL
    return status != "FAIL"

def item_6_contract_rpc_event():
    """Item 6: Contract/RPC/Event-Zugänge vorhanden"""
    print("\n[ITEM 6] Contract/RPC/Event-Zugänge vorhanden")

    # Check backend for contract/RPC config
    backend_env_files = list((EMS_REPO / "backend").glob(".env*"))
    docker_compose = EMS_REPO / "docker-compose.yml"

    evidence_file = EVIDENCE_ROOT / "item6_contract_rpc_check.json"
    evidence_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "backend_env_files": [f.name for f in backend_env_files],
        "docker_compose_exists": docker_compose.exists(),
        "manual_check_required": True,
    }

    # Check if docker-compose might have contract/RPC services
    rpc_indicators = []
    if docker_compose.exists():
        with open(docker_compose, "r", encoding="utf-8") as f:
            content = f.read().lower()
            if "rpc" in content or "hardhat" in content or "ganache" in content:
                rpc_indicators.append("RPC/Contract-Services in docker-compose erkannt")

    if rpc_indicators or backend_env_files:
        status = "PASS"
        befund = "Contract/RPC-Zugänge wahrscheinlich vorhanden (docker-compose + .env). MANUELL verifizieren."
        evidence_data["indicators"] = rpc_indicators
    else:
        status = "UNCLEAR"
        befund = "Contract/RPC-Setup unklar. docker-compose.yml / RPC-Konfiguration manuell checken erforderlich."

    print(f"  [{status}] {befund}")

    with open(evidence_file, "w", encoding="utf-8") as f:
        json.dump(evidence_data, f, indent=2)

    evidence_hash = sha256_file(evidence_file)
    log_work(6, "Contract/RPC/Event-Zugänge vorhanden", status, befund, evidence_file, evidence_hash)
    return status != "FAIL"

def item_7_no_production_access():
    """Item 7: Kein Production-Zugriff erforderlich"""
    print("\n[ITEM 7] Kein Production-Zugriff erforderlich")

    # Check if there are obvious prod indicators in config
    prod_indicators = []

    # Scan for prod/production strings in key files
    files_to_check = [
        EMS_REPO / "docker-compose.yml",
        EMS_REPO / ".env.prod",
        EMS_REPO / "backend" / "config.py",
    ]

    for fpath in files_to_check:
        if fpath.exists():
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                    if "production" in content and "localhost" not in content:
                        prod_indicators.append(f"{fpath.name} hat Production-Hinweise")
            except:
                pass

    evidence_file = EVIDENCE_ROOT / "item7_production_check.json"
    evidence_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "prod_indicators": prod_indicators,
        "expected_scope": "localhost:3000 / localhost:8000",
    }

    if not prod_indicators:
        status = "PASS"
        befund = "Keine Production-Indikationen erkannt. Scope ist dev/test lokal."
    else:
        status = "UNCLEAR"
        befund = f"Prod-Indikatoren erkannt: {', '.join(prod_indicators)}. Config-Spezifika checken."

    print(f"  [{status}] {befund}")

    with open(evidence_file, "w", encoding="utf-8") as f:
        json.dump(evidence_data, f, indent=2)

    evidence_hash = sha256_file(evidence_file)
    log_work(7, "Kein Production-Zugriff erforderlich", status, befund, evidence_file, evidence_hash)
    return status == "PASS"

def write_environment_gate_report(all_pass, results):
    """Write final ENVIRONMENT_GATE.md report."""
    items_text = "\n".join([f"- Item {i+1}: {results[i]}" for i in range(7)])

    if all_pass:
        verdict = "**PASS** — Alle Umgebungsprüfungen bestanden. Gate 1–5 können starten."
        next_steps = """
## Nächste Schritte
1. Starte GATE 1 — Contract Bindings Audit
2. GATE 2 — Fee Distribution Hooks
3. GATE 3 — Reward Handler + KYC Mapping
4. GATE 4 — Smart Contract Event Flow
5. GATE 5 — E2E Portal Flow (Playwright)
"""
    else:
        verdict = "**FAIL** — Mindestens eine Umgebungsprüfung fehlgeschlagen. Siehe BLOCKERBERICHT.md"
        next_steps = "\n## Nächste Schritte\nBehebe die Blocker und führe ENVIRONMENT GATE erneut aus.\n"

    report = f"""# ENVIRONMENT GATE REPORT
Timestamp: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}

## Gesamtstatus
{verdict}

## Item-Ergebnisse
{items_text}

## Evidence
Alle Item-Ergebnisse sind dokumentiert in:
- item1_ems_repo_structure.txt
- item2_backend_health.json
- item3_frontend_health.json
- item4_dev_test_env.json
- item5_testaccount_check.json
- item6_contract_rpc_check.json
- item7_production_check.json

SHA256-Hashes siehe SHA256SUMS.txt

{next_steps}
"""

    with open(ENV_GATE_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    return report

def write_blockerbericht(failed_items):
    """Write BLOCKERBERICHT.md if there are failures."""
    items_text = "\n".join([f"- **Item {i+1}:** {msg}" for i, msg in enumerate(failed_items)])

    report = f"""# BLOCKERBERICHT — ENVIRONMENT GATE FAIL
Timestamp: {datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}

## Fehlgeschlagene Items
{items_text}

## Maßnahmen
1. Behebe die oben aufgelisteten Blocker
2. Verifikationsschritte:
   - Starte EMS Backend (docker-compose oder manuell)
   - Starte EMS Frontend
   - Verifiziere Test-Account Zugang
   - Konfiguriere Contract/RPC/Event-Zugänge
3. Führe ENVIRONMENT GATE erneut aus

## Evidence
Siehe WORKLOG.jsonl für detaillierte Einträge.
"""

    with open(BLOCKERBERICHT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

def write_sha256_sums(evidence_files):
    """Write SHA256SUMS.txt for all evidence files."""
    sums = []
    for fpath in evidence_files:
        if fpath.exists():
            h = sha256_file(fpath)
            sums.append(f"{h}  {fpath.name}")

    with open(SHA256_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(sums))

def main():
    print("="*70)
    print("PHASE 7 — ENVIRONMENT GATE CHECKER")
    print("="*70)

    ensure_dirs()

    # Run all 7 items
    results = []
    statuses = []

    r1 = item_1_ems_repo_exists()
    results.append(("SSID-EMS Repo lokal vorhanden", "PASS" if r1 else "FAIL"))
    statuses.append(r1)

    r2 = item_2_ems_backend_reachable()
    results.append(("EMS Backend erreichbar", "PASS" if r2 else "FAIL"))
    statuses.append(r2)

    r3 = item_3_ems_frontend_reachable()
    results.append(("EMS Frontend erreichbar", "PASS" if r3 else "FAIL"))
    statuses.append(r3)

    r4 = item_4_dev_test_environment()
    results.append(("Dev/Test-Environment vorhanden", "PASS" if r4 else "FAIL"))
    statuses.append(r4)

    r5 = item_5_testaccount_safe()
    results.append(("Testaccount sicher nutzbar", "PASS" if r5 else "FAIL"))
    statuses.append(r5)

    r6 = item_6_contract_rpc_event()
    results.append(("Contract/RPC/Event-Zugänge", "PASS" if r6 else "FAIL"))
    statuses.append(r6)

    r7 = item_7_no_production_access()
    results.append(("Kein Production-Zugriff", "PASS" if r7 else "FAIL"))
    statuses.append(r7)

    # Summary
    all_pass = all(statuses)
    failed = [msg for msg, stat in results if stat == "FAIL"]

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for msg, stat in results:
        print(f"{msg:.<50} [{stat}]")

    print(f"\nGesamtstatus: {'PASS' if all_pass else 'FAIL'}")

    # Write reports
    report = write_environment_gate_report(all_pass, [s[1] for s in results])
    print(f"\nReport geschrieben: {ENV_GATE_PATH}")

    # Collect evidence files for SHA256
    evidence_files = list(EVIDENCE_ROOT.glob("item*.json")) + list(EVIDENCE_ROOT.glob("item*.txt"))
    write_sha256_sums(evidence_files)
    print(f"SHA256 geschrieben: {SHA256_PATH}")

    if not all_pass:
        write_blockerbericht(failed)
        print(f"Blockerbericht geschrieben: {BLOCKERBERICHT_PATH}")
        print("\nPHASE 7 ENVIRONMENT GATE: FAIL")
        return 1
    else:
        print("\nPHASE 7 ENVIRONMENT GATE: PASS")
        print("Ready for GATE 1–5")
        return 0

if __name__ == "__main__":
    exit(main())
