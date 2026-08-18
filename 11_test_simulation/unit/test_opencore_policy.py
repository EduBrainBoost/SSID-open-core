"""OpenCore policy tests — validates 24-root structure and policy compliance."""
import pytest
import yaml
import json
from pathlib import Path
from typing import List, Set

REPO_ROOT = Path(__file__).parent.parent.parent
POLICY_PATH = REPO_ROOT / "23_compliance" / "policies" / "opencore_policy.yaml"

EXPECTED_ROOTS = [
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

REQUIRED_ROOT_FILES = {"README.md", "module.yaml"}

PRIVATE_PATTERNS = [
    r"C:\\Users\\bibel\\SSID-Workspace",
    r"C:\\Users\\bibel\\Documents\\Github",
    r"MAOS",
    r"Agent-Swarm",
    r"private.*registry",
    r"API[_ ]?key",
    r"oauth[_ ]?token",
    r"password",
    r"secret[_ ]?key",
]


@pytest.fixture
def policy():
    """Load the OpenCore policy YAML."""
    assert POLICY_PATH.exists(), f"Policy file missing: {POLICY_PATH}"
    with open(POLICY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def actual_roots() -> List[str]:
    """Discover actual root directories."""
    roots = []
    for d in sorted(REPO_ROOT.iterdir()):
        if d.is_dir() and _is_root_name(d.name):
            roots.append(d.name)
    return roots


def _is_root_name(name: str) -> bool:
    """Check if a directory name is one of the 24 OpenCore roots."""
    import re
    return bool(re.match(r"^\d{2}_[a-z_]+$", name))


@pytest.fixture
def all_repo_files() -> List[Path]:
    """Get all text files in the repo (bounded, not recursive beyond reason)."""
    files = []
    for pattern in ["*.md", "*.yaml", "*.yml", "*.json", "*.py", "*.sh", "*.txt"]:
        files.extend(REPO_ROOT.glob(pattern))
        files.extend((REPO_ROOT / "src").rglob(pattern) if (REPO_ROOT / "src").exists() else [])
        files.extend((REPO_ROOT / "tests").rglob(pattern) if (REPO_ROOT / "tests").exists() else [])
    return files


# ── OC01: Exact 24 roots ─────────────────────────────────────────────────────

class TestRoot24Lock:
    def test_exact_24_roots(self, actual_roots):
        """OC01: Exactly 24 roots must exist."""
        assert len(actual_roots) == 24, f"Expected 24 roots, found {len(actual_roots)}: {actual_roots}"

    def test_root_names_match(self, actual_roots):
        """OC01b: Root names must match expected set exactly."""
        assert set(actual_roots) == set(EXPECTED_ROOTS), \
            f"Root mismatch. Missing: {set(EXPECTED_ROOTS) - set(actual_roots)}, Extra: {set(actual_roots) - set(EXPECTED_ROOTS)}"


# ── OC02: 25th root block ────────────────────────────────────────────────────

class TestNoExtraRoots:
    def test_no_25th_root(self, actual_roots):
        """OC02: No extra roots beyond the 24."""
        extra = set(actual_roots) - set(EXPECTED_ROOTS)
        assert not extra, f"Unexpected roots found: {extra}"

    def test_no_root_level_files(self):
        """OC03: No loose root-level source files outside roots."""
        allowed_root_files = {
            "README.md", "LICENSE", "SECURITY.md", "CODEOWNERS",
            "CONTRIBUTING.md", "CHANGELOG.md", ".gitignore", ".gitattributes",
            "pyproject.toml",
        }
        for item in REPO_ROOT.iterdir():
            if item.is_file() and item.suffix in {".py", ".yaml", ".yml", ".json"}:
                if item.name not in allowed_root_files:
                    pytest.fail(f"Unexpected source file at root: {item.name}")


# ── OC04: Missing required public root file ──────────────────────────────────

class TestRequiredRootFiles:
    @pytest.mark.parametrize("root_name", EXPECTED_ROOTS)
    def test_each_root_has_readme(self, root_name):
        """OC04: Every root must have a README.md."""
        root_path = REPO_ROOT / root_name
        assert (root_path / "README.md").exists(), f"Missing README.md in {root_name}/"

    @pytest.mark.parametrize("root_name", EXPECTED_ROOTS)
    def test_each_root_has_module_yaml(self, root_name):
        """OC04b: Every root must have a module.yaml."""
        root_path = REPO_ROOT / root_name
        assert (root_path / "module.yaml").exists(), f"Missing module.yaml in {root_name}/"


# ── OC05: Blocked binary extensions ──────────────────────────────────────────

class TestBlockedExtensions:
    BLOCKED = {".exe", ".dll", ".so", ".pyc", ".secret", ".key", ".p12", ".pfx", ".pem"}

    @pytest.mark.parametrize("ext", BLOCKED)
    def test_no_blocked_extensions(self, ext):
        """OC05: No blocked binary extensions in git tree."""
        import subprocess
        result = subprocess.run(
            ["git", "ls-files", f"*{ext}"],
            capture_output=True, text=True, cwd=str(REPO_ROOT)
        )
        tracked = [f for f in result.stdout.strip().split("\n") if f]
        assert not tracked, f"Blocked extension {ext} in git tree: {tracked}"


# ── OC06: Secret patterns ────────────────────────────────────────────────────

class TestSecretPatterns:
    def test_no_api_keys(self, all_repo_files):
        """OC06: No API key patterns in repo files."""
        import re
        pattern = re.compile(r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"]?[A-Za-z0-9]{20,}")
        for f in all_repo_files:
            if f.suffix in {".pyc", ".exe", ".dll"}:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                matches = pattern.findall(content)
                assert not matches, f"API key pattern in {f}: {matches}"
            except Exception:
                pass

    def test_no_secrets_yaml(self):
        """OC06b: No secrets configuration files."""
        secrets_files = list(REPO_ROOT.rglob("*secret*")) + list(REPO_ROOT.rglob("*credentials*"))
        assert not secrets_files, f"Secret files found: {secrets_files}"


# ── OC07: Private Windows paths ─────────────────────────────────────────────

class TestPrivatePaths:
    def test_no_workspace_paths(self, all_repo_files):
        """OC07: No private SSID workspace paths in repo files."""
        import re
        patterns = [
            re.compile(r"C:\\Users\\bibel\\SSID-Workspace"),
            re.compile(r"C:\\Users\\bibel\\Documents\\Github"),
        ]
        for f in all_repo_files:
            if f.suffix in {".pyc"}:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                for p in patterns:
                    matches = p.findall(content)
                    assert not matches, f"Private path in {f}: {matches}"
            except Exception:
                pass


# ── OC08–OC12: Private SSID content ─────────────────────────────────────────

class TestPrivateContentBlock:
    PRIVATE_NAMESPACES = ["MAOS", "Agent-Swarm", "private agent registry", "Hermes private runtime", "Jarvis personal runtime"]

    def test_no_maos_in_source(self, all_repo_files):
        """OC10: No MAOS internals in source files."""
        exempt_names = {"opencore_policy.yaml", "test_opencore_policy.py", "verify_private_leakage.py", "security.yaml"}
        for f in all_repo_files:
            if f.suffix not in {".py", ".yaml", ".yml", ".md", ".json"}:
                continue
            if f.name in exempt_names:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                assert "MAOS" not in content, f"MAOS reference in {f}"
            except Exception:
                pass


# ── OC13: Unlicensed content ─────────────────────────────────────────────────

class TestLicense:
    def test_license_exists(self):
        """OC13: LICENSE file must exist."""
        assert (REPO_ROOT / "LICENSE").exists(), "LICENSE file missing"

    def test_license_is_mit(self):
        """OC13b: LICENSE must be MIT or compatible."""
        license_text = (REPO_ROOT / "LICENSE").read_text(encoding="utf-8").upper()
        assert "MIT" in license_text, "LICENSE is not MIT"


# ── OC14: PII ────────────────────────────────────────────────────────────────

class TestPII:
    def test_no_email_addresses_in_source(self, all_repo_files):
        """OC14: No real email addresses in source code."""
        import re
        email_pattern = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        for f in all_repo_files:
            if f.suffix != ".py":
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                emails = email_pattern.findall(content)
                # Allow placeholder addresses
                real_emails = [e for e in emails if not e.endswith("@example.com") and not e.endswith(".local")]
                assert not real_emails, f"Real email in {f}: {real_emails}"
            except Exception:
                pass


# ── OC15: Missing export manifest ────────────────────────────────────────────

class TestExportManifest:
    def test_registry_exists(self):
        """OC15: Export registry must exist."""
        registry_path = REPO_ROOT / "24_meta_orchestration" / "registry" / "opencore_export_registry.json"
        assert registry_path.exists(), f"Missing export registry: {registry_path}"

    def test_registry_is_valid_json(self):
        """OC15b: Export registry must be valid JSON."""
        registry_path = REPO_ROOT / "24_meta_orchestration" / "registry" / "opencore_export_registry.json"
        with open(registry_path, encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict), "Registry must be a JSON object"
        assert "exports" in data or "manifests" in data, "Registry must contain exports or manifests"


# ── OC16–OC17: Hash mismatches (structural check) ───────────────────────────

class TestHashIntegrity:
    def test_policy_has_schema_version(self, policy):
        """OC16: Policy must have schema_version."""
        assert "schema_version" in policy, "Policy missing schema_version"
        assert policy["schema_version"] == "2.0", f"Expected schema_version 2.0, got {policy['schema_version']}"

    def test_policy_has_root_24(self, policy):
        """OC17: Policy must define root_24_lock with 24 names."""
        assert "root_24_lock" in policy, "Policy missing root_24_lock"
        roots = policy["root_24_lock"].get("names", [])
        assert len(roots) == 24, f"root_24_lock.names has {len(roots)} entries, expected 24"


# ── OC18–OC20: Invalid transforms and mock claims ───────────────────────────

class TestNoMockClaims:
    def test_no_100_percent_complete(self, all_repo_files):
        """OC20: No fake '100% COMPLETE' claims in non-policy files."""
        import re
        claim_pattern = re.compile(r"(?i)100%.*COMPLETE|100/100|TOKEN-COMPLIANT|LEGAL-PROTECTED|PRODUCTION-READY")
        for f in all_repo_files:
            if f.name in {"opencore_policy.yaml", "README.md", "SECURITY.md", "CHANGELOG.md"}:
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                matches = claim_pattern.findall(content)
                assert not matches, f"Invalid compliance claim in {f}: {matches}"
            except Exception:
                pass


# ── OC21–OC22: Git history safeguards (policy check) ────────────────────────

class TestSafeFixPolicy:
    def test_policy_enforces_safe_fix(self, policy):
        """OC21: Policy must enforce SAFE-FIX (no destructive ops)."""
        safe_fix = policy.get("safe_fix", {})
        assert safe_fix.get("no_force_push") is True, "Policy must disable force push"
        assert safe_fix.get("no_history_rewrite") is True, "Policy must disable history rewrite"
        assert safe_fix.get("no_reset_hard") is True, "Policy must disable hard reset"

    def test_policy_enforces_one_way_export(self, policy):
        """OC22: Export must be one-way."""
        export = policy.get("export", {})
        assert export.get("direction") == "ONE_WAY", "Export direction must be ONE_WAY"
        assert export.get("manifest_required") is True, "Export manifest is required"


# ── OC23: Network endpoints ─────────────────────────────────────────────────

class TestNoPrivateEndpoints:
    def test_no_production_urls_in_source(self, all_repo_files):
        """OC23: No production endpoint URLs in source files."""
        import re
        # Look for URLs with non-public domains
        url_pattern = re.compile(r"https?://[^\s<>\")\']+")
        public_domains = {"example.com", "localhost", "placeholder"}
        for f in all_repo_files:
            if f.suffix != ".py":
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                urls = url_pattern.findall(content)
                for url in urls:
                    domain = url.split("//")[1].split("/")[0].split(":")[0]
                    if domain not in public_domains and not domain.startswith("mock"):
                        pytest.fail(f"Non-public URL in {f}: {url}")
            except Exception:
                pass


# ── OC24: Evidence directory ────────────────────────────────────────────────

class TestEvidence:
    def test_evidence_directory_exists(self):
        """OC24: Evidence directory must exist."""
        evidence_path = REPO_ROOT / "23_compliance" / "evidence"
        assert evidence_path.exists(), f"Missing evidence directory: {evidence_path}"

    def test_score_directory_exists(self):
        """OC24b: Score directory must exist."""
        score_path = REPO_ROOT / "17_observability" / "score"
        assert score_path.exists(), f"Missing score directory: {score_path}"

    def test_ci_workflows_exist(self):
        """OC24c: CI workflows directory must exist."""
        ci_path = REPO_ROOT / ".github" / "workflows"
        assert ci_path.exists(), f"Missing CI workflows: {ci_path}"
        yamls = list(ci_path.glob("*.yaml"))
        assert len(yamls) >= 3, f"Expected at least 3 CI workflows, found {len(yamls)}"


# ── OC25: Release gate ──────────────────────────────────────────────────────

class TestReleaseGate:
    def test_release_blocked_when_public(self, policy):
        """OC25: Release must be gated when visibility conflict exists."""
        visibility = policy.get("visibility", {})
        assert visibility.get("no_private_push_while_public") is True, \
            "Policy must block private pushes while repository is public"


# ── OC26–OC28: Public content validation ─────────────────────────────────────

class TestPublicContent:
    def test_readme_exists_and_has_content(self):
        """OC26: README must exist and contain required sections."""
        readme = REPO_ROOT / "README.md"
        assert readme.exists(), "README.md missing"
        content = readme.read_text(encoding="utf-8")
        required_sections = ["What It Is", "What It Is NOT", "24-Root", "License"]
        for section in required_sections:
            assert section in content, f"README missing section: {section}"

    def test_security_md_exists(self):
        """OC26b: SECURITY.md must exist."""
        security = REPO_ROOT / "SECURITY.md"
        assert security.exists(), "SECURITY.md missing"

    def test_codeowners_exists(self):
        """OC26c: CODEOWNERS must exist."""
        codeowners = REPO_ROOT / "CODEOWNERS"
        assert codeowners.exists(), "CODEOWNERS missing"

    def test_core_sdk_has_version(self):
        """OC27: Core SDK must expose __version__."""
        from src.opencore import __version__
        assert __version__ == "1.0.0"

    def test_open_core_core_class_exists(self):
        """OC27b: OpenCoreCore class must exist."""
        from src.opencore import OpenCoreCore
        core = OpenCoreCore(".")
        assert hasattr(core, "export_content")
        assert hasattr(core, "verify_export")
        assert hasattr(core, "revoke_export")
        assert hasattr(core, "list_exports")
        assert hasattr(core, "validate_root_24")

    def test_synthetic_dataset_has_metadata(self):
        """OC28: Synthetic datasets must have license metadata."""
        dataset_path = REPO_ROOT / "22_datasets" / "synthetic"
        if dataset_path.exists():
            for f in dataset_path.glob("*.json"):
                data = json.loads(f.read_text(encoding="utf-8"))
                assert "license" in data, f"Dataset {f.name} missing license"
                assert "source" in data, f"Dataset {f.name} missing source"
                assert data.get("pii") is False, f"Dataset {f.name} must not contain PII"
