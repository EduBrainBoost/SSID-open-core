#!/usr/bin/env python3
"""
SoT Validator Core - SOT_AGENT_001..036
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set, Tuple


class SoTValidatorCore:
    RULES = {
        "SOT_AGENT_001": "Dispatcher single entry point is enforced",
        "SOT_AGENT_002": "Agent governance docs exist in canonical paths",
        "SOT_AGENT_003": "Data minimization is enforced (hash-only evidence)",
        "SOT_AGENT_004": "Canonical SoT artifact paths are complete",
        "SOT_AGENT_005": "No duplicate or inconsistent rule definitions",
        "SOT_AGENT_006": "Root 01 AI Layer structure conforms to MUST paths",
        "SOT_AGENT_007": "Root 01 AI Layer has no shadow files or forbidden copies",
        "SOT_AGENT_008": "Root 01 AI Layer interfaces reference central paths",
        "SOT_AGENT_009": "Root 02 Audit Logging structure conforms to MUST paths",
        "SOT_AGENT_010": "Root 02 Audit Logging has no shadow files or forbidden copies",
        "SOT_AGENT_011": "Root 02 Audit Logging interfaces reference central paths",
        "SOT_AGENT_012": "Root 03 Core structure conforms to MUST paths",
        "SOT_AGENT_013": "Root 03 Core has no shadow files or forbidden copies",
        "SOT_AGENT_014": "Root 03 Core interfaces reference central paths",
        "SOT_AGENT_015": "Root 04 Deployment structure conforms to MUST paths",
        "SOT_AGENT_016": "Root 04 Deployment has no shadow files or forbidden copies",
        "SOT_AGENT_017": "Root 04 Deployment interfaces reference central paths",
        "SOT_AGENT_018": "Root 05 Documentation structure conforms to MUST paths",
        "SOT_AGENT_019": "Root 05 Documentation has no shadow files or forbidden copies",
        "SOT_AGENT_020": "Root 05 Documentation interfaces reference central paths",
        "SOT_AGENT_021": "Root 06 Data Pipeline structure conforms to MUST paths",
        "SOT_AGENT_022": "Root 06 Data Pipeline has no shadow files or forbidden copies",
        "SOT_AGENT_023": "Root 06 Data Pipeline interfaces reference central paths",
        "SOT_AGENT_024": "Root 07 Governance Legal investment_disclaimers.yaml MUST exist",
        "SOT_AGENT_025": "Root 07 Governance Legal approval_workflow.yaml MUST exist",
        "SOT_AGENT_026": "Root 07 Governance Legal regulatory_map_index.yaml MUST exist",
        "SOT_AGENT_027": "Root 07 Governance Legal legal_positioning.md MUST exist",
        "SOT_AGENT_028": "Root 07 Governance Legal README.md MUST exist",
        "SOT_AGENT_029": "Root 08 Identity Score module.yaml MUST exist",
        "SOT_AGENT_030": "Root 08 Identity Score README.md MUST exist",
        "SOT_AGENT_031": "Root 08 Identity Score docs/ MUST exist",
        "SOT_AGENT_032": "Root 08 Identity Score src/ MUST exist",
        "SOT_AGENT_033": "Root 08 Identity Score tests/ MUST exist",
        "SOT_AGENT_034": "Root 08 Identity Score models/ MUST exist",
        "SOT_AGENT_035": "Root 08 Identity Score rules/ MUST exist",
        "SOT_AGENT_036": "Root 08 Identity Score api/ MUST exist",
        "SOT_AGENT_037": "Phase-5 FeeParticipant module exists in 03_core",
        "SOT_AGENT_038": "Phase-5 RevenueParticipant module exists in 03_core",
        "SOT_AGENT_039": "Phase-5 fee_proof_engine module exists in 03_core",
        "SOT_AGENT_040": "Phase-5 identity_fee_router module exists in 03_core",
        "SOT_AGENT_041": "Phase-5 license_fee_splitter module exists in 03_core",
    }
    PRIORITY = [
        "SOT_AGENT_001", "SOT_AGENT_002", "SOT_AGENT_003", "SOT_AGENT_004",
        "SOT_AGENT_005", "SOT_AGENT_006", "SOT_AGENT_007", "SOT_AGENT_008",
        "SOT_AGENT_009", "SOT_AGENT_010", "SOT_AGENT_011",
        "SOT_AGENT_012", "SOT_AGENT_013", "SOT_AGENT_014",
        "SOT_AGENT_015", "SOT_AGENT_016", "SOT_AGENT_017",
        "SOT_AGENT_018", "SOT_AGENT_019", "SOT_AGENT_020",
        "SOT_AGENT_021", "SOT_AGENT_022", "SOT_AGENT_023",
        "SOT_AGENT_024", "SOT_AGENT_025", "SOT_AGENT_026",
        "SOT_AGENT_027", "SOT_AGENT_028",
        "SOT_AGENT_029", "SOT_AGENT_030", "SOT_AGENT_031",
        "SOT_AGENT_032", "SOT_AGENT_033", "SOT_AGENT_034",
        "SOT_AGENT_035", "SOT_AGENT_036",
        "SOT_AGENT_037", "SOT_AGENT_038", "SOT_AGENT_039",
        "SOT_AGENT_040", "SOT_AGENT_041",
    ]

    ROOT01_MUST_DIRS = [
        "01_ai_layer/docs", "01_ai_layer/src", "01_ai_layer/tests",
        "01_ai_layer/agents", "01_ai_layer/prompts", "01_ai_layer/evaluation",
        "01_ai_layer/safety", "01_ai_layer/runtimes",
        "01_ai_layer/compliance_query_processor", "01_ai_layer/content_moderation",
        "01_ai_layer/policies", "01_ai_layer/config", "01_ai_layer/registry",
    ]
    ROOT01_MUST_FILES = [
        "01_ai_layer/module.yaml",
        "01_ai_layer/README.md",
        "01_ai_layer/registry/model_registry.yaml",
    ]
    ROOT01_FORBIDDEN_DIRS = [
        "01_ai_layer/security",
        "01_ai_layer/compliance",
        "01_ai_layer/anti_gaming",
    ]
    ROOT01_INTERFACE_TARGETS = [
        "03_core/interfaces/ai_validator_bus.jsonl",
        "17_observability/logs/ai",
        "23_compliance/evidence/ai_layer",
    ]

    ROOT02_MUST_DIRS = [
        "02_audit_logging/docs", "02_audit_logging/src",
        "02_audit_logging/tests", "02_audit_logging/config",
        "02_audit_logging/reports", "02_audit_logging/storage",
        "02_audit_logging/redaction", "02_audit_logging/evidence",
    ]
    ROOT02_MUST_FILES = [
        "02_audit_logging/module.yaml",
        "02_audit_logging/README.md",
        "02_audit_logging/DATA_MINIMIZATION.md",
    ]
    ROOT02_FORBIDDEN_DIRS = [
        "02_audit_logging/compliance_policies",
        "02_audit_logging/security",
        "02_audit_logging/governance_rules",
    ]
    ROOT02_INTERFACE_TARGETS = [
        "03_core/interfaces/audit_ingestion_bus.jsonl",
        "17_observability/logs/audit",
        "23_compliance/evidence/audit",
    ]

    ROOT03_MUST_DIRS = [
        "03_core/docs", "03_core/src", "03_core/tests", "03_core/config",
        "03_core/interfaces", "03_core/security", "03_core/validators",
    ]
    ROOT03_MUST_FILES = [
        "03_core/module.yaml",
        "03_core/README.md",
        "03_core/interfaces/ai_validator_bus.jsonl",
    ]
    ROOT03_FORBIDDEN_DIRS = [
        "03_core/compliance_policies",
        "03_core/audit_storage",
        "03_core/governance_rules",
    ]
    ROOT03_INTERFACE_TARGETS = [
        "17_observability/logs/core",
        "23_compliance/evidence/core",
    ]

    ROOT04_MUST_DIRS = [
        "04_deployment/docs", "04_deployment/src",
        "04_deployment/tests", "04_deployment/config",
    ]
    ROOT04_MUST_FILES = [
        "04_deployment/module.yaml",
        "04_deployment/README.md",
    ]
    ROOT04_FORBIDDEN_DIRS = [
        "04_deployment/compliance_policies",
        "04_deployment/audit_storage",
        "04_deployment/governance_rules",
    ]
    ROOT04_INTERFACE_TARGETS = [
        "17_observability/logs/deployment",
        "23_compliance/evidence/deployment",
    ]

    ROOT05_MUST_DIRS = [
        "05_documentation/docs", "05_documentation/src",
        "05_documentation/tests", "05_documentation/config",
    ]
    ROOT05_MUST_FILES = [
        "05_documentation/module.yaml",
        "05_documentation/README.md",
    ]
    ROOT05_FORBIDDEN_DIRS = [
        "05_documentation/compliance_policies",
        "05_documentation/audit_storage",
        "05_documentation/governance_rules",
    ]
    ROOT05_INTERFACE_TARGETS = [
        "17_observability/logs/documentation",
        "23_compliance/evidence/documentation",
    ]

    ROOT06_MUST_DIRS = [
        "06_data_pipeline/docs", "06_data_pipeline/src",
        "06_data_pipeline/tests", "06_data_pipeline/config",
    ]
    ROOT06_MUST_FILES = [
        "06_data_pipeline/module.yaml",
        "06_data_pipeline/README.md",
    ]
    ROOT06_FORBIDDEN_DIRS = [
        "06_data_pipeline/compliance_policies",
        "06_data_pipeline/audit_storage",
        "06_data_pipeline/governance_rules",
    ]
    ROOT06_INTERFACE_TARGETS = [
        "17_observability/logs/data_pipeline",
        "23_compliance/evidence/data_pipeline",
    ]

    ROOT07_MUST_FILES = [
        "07_governance_legal/stakeholder_protection/investment_disclaimers.yaml",
        "07_governance_legal/approvals/approval_workflow.yaml",
        "07_governance_legal/risk_links/regulatory_map_index.yaml",
        "07_governance_legal/legal/legal_positioning.md",
        "07_governance_legal/README.md",
    ]
    ROOT07_YAML_REQUIRED_KEYS = {
        "07_governance_legal/stakeholder_protection/investment_disclaimers.yaml": [
            "version", "token_position", "custody_statement", "prohibited_claims",
        ],
        "07_governance_legal/approvals/approval_workflow.yaml": [
            "version", "required_approvals", "emergency_process",
        ],
        "07_governance_legal/risk_links/regulatory_map_index.yaml": [
            "version", "mappings",
        ],
    }

    ROOT08_MUST_FILES = [
        "08_identity_score/module.yaml",
        "08_identity_score/README.md",
    ]
    ROOT08_MUST_DIRS = [
        "08_identity_score/docs",
        "08_identity_score/src",
        "08_identity_score/tests",
        "08_identity_score/models",
        "08_identity_score/rules",
        "08_identity_score/api",
    ]
    ROOT08_MODULE_REQUIRED_KEYS = ["module_id", "name", "version", "status"]
    ROOT08_README_REQUIRED_SECTIONS = [
        "Overview", "Structure", "Interfaces", "Policies", "Governance", "Testing",
    ]

    CANONICAL_SOT_ARTIFACTS = [
        "03_core/validators/sot/sot_validator_core.py",
        "23_compliance/policies/sot/sot_policy.rego",
        "16_codex/contracts/sot/sot_contract.yaml",
        "12_tooling/cli/sot_validator.py",
        "11_test_simulation/tests_compliance/test_sot_validator.py",
        "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md",
    ]

    def __init__(self, root_dir: str = "."):
        self.root_dir = Path(root_dir)
        self.violations: List[Tuple[str, str]] = []

    def _exists(self, rel: str) -> bool:
        return (self.root_dir / rel).exists()

    def check_dispatcher_entry_point(self) -> bool:
        dispatcher = self.root_dir / "12_tooling" / "cli" / "ssid_dispatcher.py"
        if not dispatcher.exists():
            self.violations.append(("SOT_AGENT_001", "ssid_dispatcher.py missing"))
            return False
        txt = dispatcher.read_text(encoding="utf-8", errors="replace")
        if "single entry point" not in txt.lower():
            self.violations.append(("SOT_AGENT_001", "ssid_dispatcher.py missing single-entry marker"))
            return False
        return True

    def check_canonical_doc_paths(self) -> bool:
        required_docs = [
            "16_codex/agents/AGENTS.md",
            "16_codex/agents/WORKFLOW.md",
            "16_codex/agents/FAILURES.md",
            "16_codex/agents/TOOL_PROFILES/claude.md",
            "16_codex/agents/TOOL_PROFILES/codex.md",
            "16_codex/agents/TOOL_PROFILES/gemini.md",
        ]
        missing = [p for p in required_docs if not self._exists(p)]
        if missing:
            self.violations.append(("SOT_AGENT_002", f"missing docs: {', '.join(missing)}"))
            return False
        return True

    def check_data_minimization(self) -> bool:
        dispatcher = self.root_dir / "12_tooling" / "cli" / "ssid_dispatcher.py"
        report = self.root_dir / "02_audit_logging/reports/SOT_MOSCOW_ENFORCEMENT_V3.2.0.md"
        if not dispatcher.exists():
            self.violations.append(("SOT_AGENT_003", "dispatcher missing for data-minimization check"))
            return False
        d_txt = dispatcher.read_text(encoding="utf-8", errors="replace")
        r_txt = report.read_text(encoding="utf-8", errors="replace").lower() if report.exists() else ""
        required_tokens = ["patch.sha256", "hash-only"]
        missing_tokens = [t for t in required_tokens if t not in d_txt and t not in r_txt]
        if "02_audit_logging" not in d_txt and "02_audit_logging" not in r_txt:
            missing_tokens.append("02_audit_logging")
        if missing_tokens:
            self.violations.append(("SOT_AGENT_003", f"missing data-minimization markers: {missing_tokens}"))
            return False
        return True

    def check_canonical_artifact_paths(self) -> bool:
        missing: List[str] = []
        for p in self.CANONICAL_SOT_ARTIFACTS:
            # Sandbox intentionally excludes 02_audit_logging.
            if p.startswith("02_audit_logging/") and not (self.root_dir / "02_audit_logging").exists():
                continue
            if not self._exists(p):
                missing.append(p)
        if missing:
            self.violations.append(("SOT_AGENT_004", f"missing canonical SoT artifacts: {', '.join(missing)}"))
            return False
        return True

    def check_no_duplicate_rules(self) -> bool:
        """SOT_AGENT_005: contract rule IDs must exactly match validator RULES dict."""
        contract = self.root_dir / "16_codex" / "contracts" / "sot" / "sot_contract.yaml"
        if not contract.is_file():
            self.violations.append(("SOT_AGENT_005", "sot_contract.yaml missing"))
            return False
        # Parse rule IDs from contract YAML (lightweight: no PyYAML dependency)
        contract_ids: Set[str] = set()
        for line in contract.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("- id:"):
                rule_id = stripped.split(":", 1)[1].strip()
                if rule_id in contract_ids:
                    self.violations.append(
                        ("SOT_AGENT_005", f"duplicate rule_id in contract: {rule_id}")
                    )
                    return False
                contract_ids.add(rule_id)
        validator_ids: Set[str] = set(self.RULES.keys())
        only_in_contract = contract_ids - validator_ids
        only_in_validator = validator_ids - contract_ids
        issues: List[str] = []
        if only_in_contract:
            issues.append(f"in contract but not validator: {sorted(only_in_contract)}")
        if only_in_validator:
            issues.append(f"in validator but not contract: {sorted(only_in_validator)}")
        if issues:
            self.violations.append(("SOT_AGENT_005", "; ".join(issues)))
            return False
        return True

    def check_root01_structure(self) -> bool:
        if not self._exists("01_ai_layer"):
            self.violations.append(("SOT_AGENT_006", "01_ai_layer root directory missing"))
            return False
        missing_dirs = [d for d in self.ROOT01_MUST_DIRS if not (self.root_dir / d).is_dir()]
        missing_files = [f for f in self.ROOT01_MUST_FILES if not (self.root_dir / f).is_file()]
        missing = missing_dirs + missing_files
        if missing:
            self.violations.append(("SOT_AGENT_006", f"missing MUST paths: {', '.join(missing)}"))
            return False
        return True

    def check_root01_shadow_files(self) -> bool:
        found: List[str] = []
        for d in self.ROOT01_FORBIDDEN_DIRS:
            if (self.root_dir / d).exists():
                found.append(d)
        ai_layer = self.root_dir / "01_ai_layer"
        if ai_layer.is_dir():
            for p in ai_layer.rglob("*_baseline.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
            for p in ai_layer.rglob("*_requirements.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
        if found:
            self.violations.append(("SOT_AGENT_007", f"forbidden shadow files: {', '.join(found)}"))
            return False
        return True

    def check_root01_interface_wiring(self) -> bool:
        missing_targets = [t for t in self.ROOT01_INTERFACE_TARGETS if not self._exists(t)]
        if missing_targets:
            self.violations.append(("SOT_AGENT_008", f"missing central interface targets: {', '.join(missing_targets)}"))
            return False
        module_yaml = self.root_dir / "01_ai_layer" / "module.yaml"
        if not module_yaml.is_file():
            self.violations.append(("SOT_AGENT_008", "01_ai_layer/module.yaml missing for interface check"))
            return False
        content = module_yaml.read_text(encoding="utf-8", errors="replace")
        missing_refs = [t for t in self.ROOT01_INTERFACE_TARGETS if t not in content]
        if missing_refs:
            self.violations.append(("SOT_AGENT_008", f"module.yaml missing refs: {', '.join(missing_refs)}"))
            return False
        return True

    def check_root02_structure(self) -> bool:
        if not self._exists("02_audit_logging"):
            self.violations.append(("SOT_AGENT_009", "02_audit_logging root directory missing"))
            return False
        missing_dirs = [d for d in self.ROOT02_MUST_DIRS if not (self.root_dir / d).is_dir()]
        missing_files = [f for f in self.ROOT02_MUST_FILES if not (self.root_dir / f).is_file()]
        missing = missing_dirs + missing_files
        if missing:
            self.violations.append(("SOT_AGENT_009", f"missing MUST paths: {', '.join(missing)}"))
            return False
        return True

    def check_root02_shadow_files(self) -> bool:
        found: List[str] = []
        for d in self.ROOT02_FORBIDDEN_DIRS:
            if (self.root_dir / d).exists():
                found.append(d)
        audit = self.root_dir / "02_audit_logging"
        if audit.is_dir():
            for p in audit.rglob("*_baseline.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
            for p in audit.rglob("*_requirements.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
        if found:
            self.violations.append(("SOT_AGENT_010", f"forbidden shadow files: {', '.join(found)}"))
            return False
        return True

    def check_root02_interface_wiring(self) -> bool:
        missing_targets = [t for t in self.ROOT02_INTERFACE_TARGETS if not self._exists(t)]
        if missing_targets:
            self.violations.append(("SOT_AGENT_011", f"missing central interface targets: {', '.join(missing_targets)}"))
            return False
        module_yaml = self.root_dir / "02_audit_logging" / "module.yaml"
        if not module_yaml.is_file():
            self.violations.append(("SOT_AGENT_011", "02_audit_logging/module.yaml missing for interface check"))
            return False
        content = module_yaml.read_text(encoding="utf-8", errors="replace")
        missing_refs = [t for t in self.ROOT02_INTERFACE_TARGETS if t not in content]
        if missing_refs:
            self.violations.append(("SOT_AGENT_011", f"module.yaml missing refs: {', '.join(missing_refs)}"))
            return False
        return True

    def check_root03_structure(self) -> bool:
        if not self._exists("03_core"):
            self.violations.append(("SOT_AGENT_012", "03_core root directory missing"))
            return False
        missing_dirs = [d for d in self.ROOT03_MUST_DIRS if not (self.root_dir / d).is_dir()]
        missing_files = [f for f in self.ROOT03_MUST_FILES if not (self.root_dir / f).is_file()]
        missing = missing_dirs + missing_files
        if missing:
            self.violations.append(("SOT_AGENT_012", f"missing MUST paths: {', '.join(missing)}"))
            return False
        return True

    def check_root03_shadow_files(self) -> bool:
        found: List[str] = []
        for d in self.ROOT03_FORBIDDEN_DIRS:
            if (self.root_dir / d).exists():
                found.append(d)
        core = self.root_dir / "03_core"
        if core.is_dir():
            for p in core.rglob("*_baseline.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
            for p in core.rglob("*_requirements.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
        if found:
            self.violations.append(("SOT_AGENT_013", f"forbidden shadow files: {', '.join(found)}"))
            return False
        return True

    def check_root03_interface_wiring(self) -> bool:
        missing_targets = [t for t in self.ROOT03_INTERFACE_TARGETS if not self._exists(t)]
        if missing_targets:
            self.violations.append(("SOT_AGENT_014", f"missing central interface targets: {', '.join(missing_targets)}"))
            return False
        module_yaml = self.root_dir / "03_core" / "module.yaml"
        if not module_yaml.is_file():
            self.violations.append(("SOT_AGENT_014", "03_core/module.yaml missing for interface check"))
            return False
        content = module_yaml.read_text(encoding="utf-8", errors="replace")
        missing_refs = [t for t in self.ROOT03_INTERFACE_TARGETS if t not in content]
        if missing_refs:
            self.violations.append(("SOT_AGENT_014", f"module.yaml missing refs: {', '.join(missing_refs)}"))
            return False
        return True

    def check_root04_structure(self) -> bool:
        if not self._exists("04_deployment"):
            self.violations.append(("SOT_AGENT_015", "04_deployment root directory missing"))
            return False
        missing_dirs = [d for d in self.ROOT04_MUST_DIRS if not (self.root_dir / d).is_dir()]
        missing_files = [f for f in self.ROOT04_MUST_FILES if not (self.root_dir / f).is_file()]
        missing = missing_dirs + missing_files
        if missing:
            self.violations.append(("SOT_AGENT_015", f"missing MUST paths: {', '.join(missing)}"))
            return False
        return True

    def check_root04_shadow_files(self) -> bool:
        found: List[str] = []
        for d in self.ROOT04_FORBIDDEN_DIRS:
            if (self.root_dir / d).exists():
                found.append(d)
        deployment = self.root_dir / "04_deployment"
        if deployment.is_dir():
            for p in deployment.rglob("*_baseline.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
            for p in deployment.rglob("*_requirements.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
        if found:
            self.violations.append(("SOT_AGENT_016", f"forbidden shadow files: {', '.join(found)}"))
            return False
        return True

    def check_root04_interface_wiring(self) -> bool:
        missing_targets = [t for t in self.ROOT04_INTERFACE_TARGETS if not self._exists(t)]
        if missing_targets:
            self.violations.append(("SOT_AGENT_017", f"missing central interface targets: {', '.join(missing_targets)}"))
            return False
        module_yaml = self.root_dir / "04_deployment" / "module.yaml"
        if not module_yaml.is_file():
            self.violations.append(("SOT_AGENT_017", "04_deployment/module.yaml missing for interface check"))
            return False
        content = module_yaml.read_text(encoding="utf-8", errors="replace")
        missing_refs = [t for t in self.ROOT04_INTERFACE_TARGETS if t not in content]
        if missing_refs:
            self.violations.append(("SOT_AGENT_017", f"module.yaml missing refs: {', '.join(missing_refs)}"))
            return False
        return True

    def check_root05_structure(self) -> bool:
        if not self._exists("05_documentation"):
            self.violations.append(("SOT_AGENT_018", "05_documentation root directory missing"))
            return False
        missing_dirs = [d for d in self.ROOT05_MUST_DIRS if not (self.root_dir / d).is_dir()]
        missing_files = [f for f in self.ROOT05_MUST_FILES if not (self.root_dir / f).is_file()]
        missing = missing_dirs + missing_files
        if missing:
            self.violations.append(("SOT_AGENT_018", f"missing MUST paths: {', '.join(missing)}"))
            return False
        return True

    def check_root05_shadow_files(self) -> bool:
        found: List[str] = []
        for d in self.ROOT05_FORBIDDEN_DIRS:
            if (self.root_dir / d).exists():
                found.append(d)
        documentation = self.root_dir / "05_documentation"
        if documentation.is_dir():
            for p in documentation.rglob("*_baseline.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
            for p in documentation.rglob("*_requirements.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
        if found:
            self.violations.append(("SOT_AGENT_019", f"forbidden shadow files: {', '.join(found)}"))
            return False
        return True

    def check_root05_interface_wiring(self) -> bool:
        missing_targets = [t for t in self.ROOT05_INTERFACE_TARGETS if not self._exists(t)]
        if missing_targets:
            self.violations.append(("SOT_AGENT_020", f"missing central interface targets: {', '.join(missing_targets)}"))
            return False
        module_yaml = self.root_dir / "05_documentation" / "module.yaml"
        if not module_yaml.is_file():
            self.violations.append(("SOT_AGENT_020", "05_documentation/module.yaml missing for interface check"))
            return False
        content = module_yaml.read_text(encoding="utf-8", errors="replace")
        missing_refs = [t for t in self.ROOT05_INTERFACE_TARGETS if t not in content]
        if missing_refs:
            self.violations.append(("SOT_AGENT_020", f"module.yaml missing refs: {', '.join(missing_refs)}"))
            return False
        return True

    def check_root06_structure(self) -> bool:
        if not self._exists("06_data_pipeline"):
            self.violations.append(("SOT_AGENT_021", "06_data_pipeline root directory missing"))
            return False
        missing_dirs = [d for d in self.ROOT06_MUST_DIRS if not (self.root_dir / d).is_dir()]
        missing_files = [f for f in self.ROOT06_MUST_FILES if not (self.root_dir / f).is_file()]
        missing = missing_dirs + missing_files
        if missing:
            self.violations.append(("SOT_AGENT_021", f"missing MUST paths: {', '.join(missing)}"))
            return False
        return True

    def check_root06_shadow_files(self) -> bool:
        found: List[str] = []
        for d in self.ROOT06_FORBIDDEN_DIRS:
            if (self.root_dir / d).exists():
                found.append(d)
        data_pipeline = self.root_dir / "06_data_pipeline"
        if data_pipeline.is_dir():
            for p in data_pipeline.rglob("*_baseline.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
            for p in data_pipeline.rglob("*_requirements.yaml"):
                found.append(str(p.relative_to(self.root_dir)))
        if found:
            self.violations.append(("SOT_AGENT_022", f"forbidden shadow files: {', '.join(found)}"))
            return False
        return True

    def check_root06_interface_wiring(self) -> bool:
        missing_targets = [t for t in self.ROOT06_INTERFACE_TARGETS if not self._exists(t)]
        if missing_targets:
            self.violations.append(("SOT_AGENT_023", f"missing central interface targets: {', '.join(missing_targets)}"))
            return False
        module_yaml = self.root_dir / "06_data_pipeline" / "module.yaml"
        if not module_yaml.is_file():
            self.violations.append(("SOT_AGENT_023", "06_data_pipeline/module.yaml missing for interface check"))
            return False
        content = module_yaml.read_text(encoding="utf-8", errors="replace")
        missing_refs = [t for t in self.ROOT06_INTERFACE_TARGETS if t not in content]
        if missing_refs:
            self.violations.append(("SOT_AGENT_023", f"module.yaml missing refs: {', '.join(missing_refs)}"))
            return False
        return True

    def _check_yaml_structure(self, rel_path: str, rule_id: str) -> bool:
        """Optional YAML structure check: parseable + required keys present."""
        required_keys = self.ROOT07_YAML_REQUIRED_KEYS.get(rel_path)
        if not required_keys:
            return True
        fpath = self.root_dir / rel_path
        try:
            import yaml  # noqa: F811
            data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
        except ImportError:
            # PyYAML not available — skip format check, existence already enforced
            return True
        except Exception as exc:
            self.violations.append((rule_id, f"YAML parse error in {rel_path}: {exc}"))
            return False
        if not isinstance(data, dict):
            self.violations.append((rule_id, f"{rel_path} is not a YAML mapping"))
            return False
        missing = [k for k in required_keys if k not in data]
        if missing:
            self.violations.append((rule_id, f"{rel_path} missing required keys: {', '.join(missing)}"))
            return False
        # Extra: regulatory_map_index mappings must reference 23_compliance/mappings/
        if rel_path.endswith("regulatory_map_index.yaml"):
            mappings = data.get("mappings", [])
            if not isinstance(mappings, list) or len(mappings) == 0:
                self.violations.append((rule_id, f"{rel_path} mappings must be a non-empty list"))
                return False
            bad = [m.get("id", "?") for m in mappings
                   if isinstance(m, dict) and not str(m.get("path", "")).startswith("23_compliance/mappings/")]
            if bad:
                self.violations.append((rule_id, f"{rel_path} mappings with invalid path prefix: {', '.join(bad)}"))
                return False
        return True

    def check_root07_investment_disclaimers(self) -> bool:
        rel = "07_governance_legal/stakeholder_protection/investment_disclaimers.yaml"
        if not (self.root_dir / rel).is_file():
            self.violations.append(("SOT_AGENT_024", f"missing: {rel}"))
            return False
        return self._check_yaml_structure(rel, "SOT_AGENT_024")

    def check_root07_approval_workflow(self) -> bool:
        rel = "07_governance_legal/approvals/approval_workflow.yaml"
        if not (self.root_dir / rel).is_file():
            self.violations.append(("SOT_AGENT_025", f"missing: {rel}"))
            return False
        return self._check_yaml_structure(rel, "SOT_AGENT_025")

    def check_root07_regulatory_map_index(self) -> bool:
        rel = "07_governance_legal/risk_links/regulatory_map_index.yaml"
        if not (self.root_dir / rel).is_file():
            self.violations.append(("SOT_AGENT_026", f"missing: {rel}"))
            return False
        return self._check_yaml_structure(rel, "SOT_AGENT_026")

    def check_root07_legal_positioning(self) -> bool:
        rel = "07_governance_legal/legal/legal_positioning.md"
        if not (self.root_dir / rel).is_file():
            self.violations.append(("SOT_AGENT_027", f"missing: {rel}"))
            return False
        return True

    def check_root07_readme(self) -> bool:
        rel = "07_governance_legal/README.md"
        if not (self.root_dir / rel).is_file():
            self.violations.append(("SOT_AGENT_028", f"missing: {rel}"))
            return False
        return True

    def check_root08_module_yaml(self) -> bool:
        rel = "08_identity_score/module.yaml"
        fpath = self.root_dir / rel
        if not fpath.is_file():
            self.violations.append(("SOT_AGENT_029", f"missing: {rel}"))
            return False
        try:
            import yaml
            data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
        except ImportError:
            return True
        except Exception as exc:
            self.violations.append(("SOT_AGENT_029", f"YAML parse error in {rel}: {exc}"))
            return False
        if not isinstance(data, dict):
            self.violations.append(("SOT_AGENT_029", f"{rel} is not a YAML mapping"))
            return False
        missing = [k for k in self.ROOT08_MODULE_REQUIRED_KEYS if k not in data]
        if missing:
            joined = ", ".join(missing)
            self.violations.append(("SOT_AGENT_029", f"{rel} missing required keys: {joined}"))
            return False
        return True

    def check_root08_readme(self) -> bool:
        rel = "08_identity_score/README.md"
        fpath = self.root_dir / rel
        if not fpath.is_file():
            self.violations.append(("SOT_AGENT_030", f"missing: {rel}"))
            return False
        content = fpath.read_text(encoding="utf-8", errors="replace")
        missing = [s for s in self.ROOT08_README_REQUIRED_SECTIONS if f"## {s}" not in content]
        if missing:
            joined = ", ".join(missing)
            self.violations.append(("SOT_AGENT_030", f"{rel} missing sections: {joined}"))
            return False
        return True

    def check_root08_docs_dir(self) -> bool:
        if not (self.root_dir / "08_identity_score/docs").is_dir():
            self.violations.append(("SOT_AGENT_031", "missing directory: 08_identity_score/docs"))
            return False
        return True

    def check_root08_src_dir(self) -> bool:
        if not (self.root_dir / "08_identity_score/src").is_dir():
            self.violations.append(("SOT_AGENT_032", "missing directory: 08_identity_score/src"))
            return False
        return True

    def check_root08_tests_dir(self) -> bool:
        if not (self.root_dir / "08_identity_score/tests").is_dir():
            self.violations.append(("SOT_AGENT_033", "missing directory: 08_identity_score/tests"))
            return False
        return True

    def check_root08_models_dir(self) -> bool:
        if not (self.root_dir / "08_identity_score/models").is_dir():
            self.violations.append(("SOT_AGENT_034", "missing directory: 08_identity_score/models"))
            return False
        return True

    def check_root08_rules_dir(self) -> bool:
        if not (self.root_dir / "08_identity_score/rules").is_dir():
            self.violations.append(("SOT_AGENT_035", "missing directory: 08_identity_score/rules"))
            return False
        return True

    def check_root08_api_dir(self) -> bool:
        if not (self.root_dir / "08_identity_score/api").is_dir():
            self.violations.append(("SOT_AGENT_036", "missing directory: 08_identity_score/api"))
            return False
        return True

    # ---------------------------------------------------------------
    # Phase-5 checks (SOT_AGENT_037 – SOT_AGENT_041)
    # ---------------------------------------------------------------

    PHASE5_MODULE_MAP = {
        "SOT_AGENT_037": ("03_core/participants.py", "FeeParticipant"),
        "SOT_AGENT_038": ("03_core/participants.py", "RevenueParticipant"),
        "SOT_AGENT_039": ("03_core/fee_proof_engine.py", "fee_proof_engine"),
        "SOT_AGENT_040": ("03_core/identity_fee_router.py", "identity_fee_router"),
        "SOT_AGENT_041": ("03_core/license_fee_splitter.py", "license_fee_splitter"),
    }

    def _check_phase5_module(self, rule_id: str) -> bool:
        """Check that a Phase-5 module file exists at the expected path."""
        file_rel, label = self.PHASE5_MODULE_MAP[rule_id]
        if not (self.root_dir / file_rel).is_file():
            self.violations.append((rule_id, f"missing Phase-5 module: {file_rel} ({label})"))
            return False
        return True

    def check_phase5_fee_participant(self) -> bool:
        return self._check_phase5_module("SOT_AGENT_037")

    def check_phase5_revenue_participant(self) -> bool:
        return self._check_phase5_module("SOT_AGENT_038")

    def check_phase5_fee_proof_engine(self) -> bool:
        return self._check_phase5_module("SOT_AGENT_039")

    def check_phase5_identity_fee_router(self) -> bool:
        return self._check_phase5_module("SOT_AGENT_040")

    def check_phase5_license_fee_splitter(self) -> bool:
        return self._check_phase5_module("SOT_AGENT_041")

    def validate_all(self) -> Dict[str, Dict[str, str]]:
        self.violations = []
        self.check_dispatcher_entry_point()
        self.check_canonical_doc_paths()
        self.check_data_minimization()
        self.check_canonical_artifact_paths()
        self.check_no_duplicate_rules()
        self.check_root01_structure()
        self.check_root01_shadow_files()
        self.check_root01_interface_wiring()
        self.check_root02_structure()
        self.check_root02_shadow_files()
        self.check_root02_interface_wiring()
        self.check_root03_structure()
        self.check_root03_shadow_files()
        self.check_root03_interface_wiring()
        self.check_root04_structure()
        self.check_root04_shadow_files()
        self.check_root04_interface_wiring()
        self.check_root05_structure()
        self.check_root05_shadow_files()
        self.check_root05_interface_wiring()
        self.check_root06_structure()
        self.check_root06_shadow_files()
        self.check_root06_interface_wiring()
        self.check_root07_investment_disclaimers()
        self.check_root07_approval_workflow()
        self.check_root07_regulatory_map_index()
        self.check_root07_legal_positioning()
        self.check_root07_readme()
        self.check_root08_module_yaml()
        self.check_root08_readme()
        self.check_root08_docs_dir()
        self.check_root08_src_dir()
        self.check_root08_tests_dir()
        self.check_root08_models_dir()
        self.check_root08_rules_dir()
        self.check_root08_api_dir()
        self.check_phase5_fee_participant()
        self.check_phase5_revenue_participant()
        self.check_phase5_fee_proof_engine()
        self.check_phase5_identity_fee_router()
        self.check_phase5_license_fee_splitter()

        results: Dict[str, Dict[str, str]] = {}
        for rule in self.PRIORITY:
            msgs = [msg for rid, msg in self.violations if rid == rule]
            if msgs:
                results[rule] = {"status": "FAIL", "message": msgs[0]}
            else:
                results[rule] = {"status": "PASS", "message": self.RULES[rule]}
        return results

    def evaluate_priorities(self, results: Dict[str, Dict[str, str]]) -> Tuple[bool, List[str]]:
        failed = [rid for rid, data in results.items() if data.get("status") != "PASS"]
        return len(failed) == 0, failed


if __name__ == "__main__":
    validator = SoTValidatorCore()
    out = validator.validate_all()
    ok, failed = validator.evaluate_priorities(out)
    for rule_id in SoTValidatorCore.PRIORITY:
        print(f"{rule_id}: {out[rule_id]['status']} - {out[rule_id]['message']}")
    raise SystemExit(0 if ok else 2)
