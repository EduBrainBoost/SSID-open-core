HASH_START::B
  # Manifest: Name, Zweck, Owner-ID, Links
README.md      # 1-Pager Modulzweck
docs/          # Modulspezifische Docs
src/           # Quellartefakte
tests/         # Modulnahe Unit-Tests
```

## Zentralisierung (Anti-Duplikat)

| Funktion | Zentraler Pfad | Zweck |
|----------|----------------|-------|
| **Registry** | `24_meta_orchestration/registry/` | Kanonische Modulverwaltung |
| **Policies** | `23_compliance/policies/` | Struktur-Policies zentral |
| **Evidence** | `23_compliance/evidence/` | Audit-Evidence gesammelt |
| **Exceptions** | `23_compliance/exceptions/` | Struktur-Ausnahmen zentral |
| **Risk** | `07_governance_legal/risk/` | Risk Register zentral |
| **CI/CD** | `.github/workflows/` + `24_meta_orchestration/triggers/ci/` | Pipeline-Logik |

**VERBOTEN modulnah:** `registry/`, `policies/`, `risk/`, `evidence/`, `exceptions/`, `triggers/`, `ci/`, `cd/`

**Pfadkonvention:** Alle `path:`-Einträge sind als REPO-relative, modul-präfixierte Pfade zu schreiben (z. B. `23_compliance/jurisdictions/...` statt `jurisdictions/...`).

## Root-Level Exceptions Framework (Kanonisch)

### Canonical Root-Level Exceptions Definition
```yaml
# 23_compliance/exceptions/root_level_exceptions.yaml
version: "1.0"
date: "2025-09-15"
deprecated: false
classification: "PUBLIC - CI Guard Enforcement"

root_level_exceptions:
  description: "EINMALIGE, autoritäre Liste aller erlaubten Root-Level Items außerhalb der 24 Module"
  enforcement: "CI-Guard mit Exit Code 24 bei Violation"
  modification_policy: "Nur durch Compliance Committee + Technical Lead Approval"
  
allowed_directories:
  git_infrastructure:
    - ".git"           # Git repository metadata
    - ".github"        # GitHub workflows and templates
    - ".githooks"      # Git hooks directory
    
  development_environment:
    - ".venv"          # Python virtual environment
    - ".continue"      # Continue.dev AI coding assistant
    
  testing_artifacts:
    - ".pytest_cache"  # Pytest cache directory
    
  excluded_directories: []  # NO additional directories allowed
  
allowed_files:
  version_control:
    - ".gitattributes" # Git file attributes
    - ".gitignore"     # Git ignore patterns  
    - ".gitmodules"    # Git submodules configuration
    
  project_metadata:
    - "LICENSE"        # Project license file
    - "README.md"      # Project overview and documentation
    
  testing_configuration:
    - "pytest.ini"     # Pytest configuration
    
  excluded_files: []   # NO additional files allowed

guard_enforcement:
  ci_script: "12_tooling/scripts/structure_guard.sh"
  validation_function: "validate_root_exceptions"
  enforcement_level: "STRICT - Zero tolerance for unlisted items"
  bypass_mechanism: "NONE - No override capability"
  
  violation_handling:
    immediate_failure: true
    exit_code: 24
    quarantine_trigger: true
    escalation: "Compliance Committee notification"
    
guard_algorithm:
  step_1: "Scan root directory for all items"
  step_2: "Compare against allowed_directories + allowed_files"
  step_3: "Verify 24 module directories present"
  step_4: "FAIL if any unlisted item found"
  step_5: "Generate violation report for quarantine system"

modification_process:
  approval_required:
    - "Senior Compliance Officer"
    - "Technical Lead" 
    - "Legal Review (for licensing implications)"
    
  documentation_required:
    - "Business justification"
    - "Security impact assessment"
    - "CI/CD impact analysis"
    - "Audit trail documentation"
    
  change_procedure:
    step_1: "RFC (Request for Change) submission"
    step_2: "Multi-stakeholder review (5 business days)"
    step_3: "Approval/rejection decision"
    step_4: "If approved: Update YAML + CI tests"
    step_5: "Evidence logging in audit trail"

anti_gaming_measures:
  no_wildcards: "No wildcard patterns allowed"
  no_regex: "No regex patterns allowed"
  explicit_enumeration: "Every allowed item must be explicitly listed"
  case_sensitive: "Exact case matching required"
  no_symlinks: "Symbolic links not allowed"
  no_hidden_directories: "Only explicitly listed hidden directories allowed"

integration_points:
  structure_guard: "12_tooling/scripts/structure_guard.sh"
  ci_gates: "24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py"
  quarantine_system: "02_audit_logging/quarantine/singleton/quarantine_store/"
  compliance_policies: "23_compliance/policies/structure_policy.yaml"
  
audit_requirements:
  change_log: "All modifications logged in 02_audit_logging/storage/worm/immutable_store/"
  review_cycle: "Quarterly review of exceptions list"
  justification_retention: "7 years minimum"
  approval_trail: "Immutable approval documentation required"
```

### Root-Level Guard Implementation
```bash
# 12_tooling/scripts/structure_guard.sh - Root Exceptions Validation
validate_root_exceptions() {
    local EXCEPTIONS_FILE="23_compliance/exceptions/root_level_exceptions.yaml"
    
    # Get repository root and scan it
    local REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
    cd "$REPO_ROOT"
    local ROOT_SCAN=$(ls -A1)
    
    # Extract allowed items properly from YAML structure
    local ALLOWED_DIRS=$(yq -r '.root_level_exceptions.allowed_directories.*[]' "$EXCEPTIONS_FILE" 2>/dev/null || echo "")
    local ALLOWED_FILES=$(yq -r '.root_level_exceptions.allowed_files.*[]' "$EXCEPTIONS_FILE" 2>/dev/null || echo "")
    local ALLOWED_ITEMS=$(printf "%s\n%s\n" "$ALLOWED_DIRS" "$ALLOWED_FILES")
    
    # Verify exactly 24 modules present (with NN_ prefix)
    local MODULE_COUNT=$(ls -d [0-9][0-9]_* 2>/dev/null | wc -l | tr -d ' ')
    if [ "$MODULE_COUNT" -ne 24 ]; then
        echo "ERROR: Expected exactly 24 modules, found $MODULE_COUNT"
        exit 24
    fi
    
    # Check for unauthorized items
    for item in $ROOT_SCAN; do
        # Skip if it's a valid module (NN_*)
        if [[ "$item" =~ ^[0-9]{2}_.+$ ]]; then
            continue
        fi
        
        # Block any hidden directories/files not explicitly allowed
        if [[ "$item" == .* ]] && ! echo "$ALLOWED_ITEMS" | grep -qx "$item"; then
            echo "VIOLATION: Hidden item '$item' not allowed"
            exit 24
        fi
        
        # Block symlinks
        if [ -L "$item" ]; then
            echo "VIOLATION: Symlink '$item' not allowed"
            exit 24
        fi
        
        # Block any other unauthorized items
        if ! echo "$ALLOWED_ITEMS" | grep -qx "$item"; then
            echo "VIOLATION: Unauthorized root-level item '$item' - not in canonical exceptions list"
            echo "Triggering quarantine for: $item"
            # Trigger quarantine
            python 02_audit_logging/quarantine/processing/quarantine_processor.py \
                --trigger "root_level_violation" \
                --item "$item" \
                --severity "HIGH"
            exit 24
        fi
    done
    
    echo "✅ Root-level exceptions validation PASSED"
}
```

## Kritische Dateien (CI-Ready) - PFAD-NACHWEIS ERFORDERLICH

```bash
# Struktur-Guard (MUSS EXISTIEREN)
12_tooling/scripts/structure_guard.sh

# Pre-Commit Hook (MUSS EXISTIEREN)
12_tooling/hooks/pre_commit/structure_validation.sh

# Policies & Tests (MUSS EXISTIEREN)
23_compliance/policies/structure_policy.yaml
23_compliance/exceptions/structure_exceptions.yaml
23_compliance/exceptions/root_level_exceptions.yaml
23_compliance/tests/unit/test_structure_policy_vs_md.py

# CI-Gates (MUSS EXISTIEREN)
24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py

# Hinweis: Level-4-Kontrollen (Anti-Gaming/Reviews/Business) werden nicht durch `structure_lock_l3.py`,
# sondern durch folgende Gates/Scanner erzwungen:
# - 23_compliance/anti_gaming/* (Zirkularität, Badge-Integrität, Overfitting, Dependency-Graph)
# - 23_compliance/reviews/* (Review-Status, Business-Compliance)

# WORM Storage (MUSS EXISTIEREN)
02_audit_logging/storage/worm/immutable_store/

# Quarantine Framework (MUSS EXISTIEREN)
02_audit_logging/quarantine/quarantine_policy.yaml
02_audit_logging/quarantine/processing/quarantine_processor.py
02_audit_logging/quarantine/hash_ledger/quarantine_chain.json
23_compliance/evidence/malware_quarantine_hashes/quarantine_hash_ledger.json

# Anti-Gaming Controls (MUSS EXISTIEREN)
23_compliance/anti_gaming/circular_dependency_validator.py
23_compliance/anti_gaming/badge_integrity_checker.sh
23_compliance/anti_gaming/overfitting_detector.py
23_compliance/anti_gaming/dependency_graph_generator.py

# Governance & Maintenance (MUSS EXISTIEREN)
23_compliance/governance/maintainers_enterprise.yaml
23_compliance/governance/source_of_truth_enterprise.md
23_compliance/governance/community_guidelines_enterprise.md

# Token Framework (MUSS EXISTIEREN)
20_foundation/tokenomics/ssid_token_framework.yaml
20_foundation/tokenomics/utility_definitions.yaml
20_foundation/tokenomics/token_economics.yaml

# Internationalization (MUSS EXISTIEREN)
05_documentation/internationalization/language_strategy.yaml
05_documentation/internationalization/translation_quality.yaml

# Enterprise Adoption (MUSS EXISTIEREN)
23_compliance/enterprise_adoption/adoption_disclaimer.md
07_governance_legal/stakeholder_protection/investment_disclaimers.yaml
```

**100-Punkte-Requirement:** Alle kritischen Dateien müssen physisch vorhanden sein oder führen zu Penalty von -5 pro fehlender Datei.

## Governance & Maintainer Framework (Enterprise)

### Maintainer Definition & Backup Structure
```yaml
# 23_compliance/governance/maintainers_enterprise.yaml
version: "1.0"
date: "2025-09-15"
deprecated: false
classification: "CONFIDENTIAL - Internal Use Only"

maintainer_structure:
  primary_maintainers:
    - name: "Hans Müller"
      role: "Lead Compliance Officer"
      email: "hans.mueller@ssid.company"
      backup: "Maria Schmidt"
      areas: ["compliance_matrices", "regulatory_updates", "eu_mappings"]
      clearance_level: "CONFIDENTIAL"
      
    - name: "Anna Weber" 
      role: "Technical Lead"
      email: "anna.weber@ssid.company"
      backup: "Thomas Klein"
      areas: ["badge_logic", "anti_gaming_controls", "internal_audits"]
      clearance_level: "CONFIDENTIAL"

  backup_escalation:
    level_1: "Security Team Lead"
    level_2: "CTO"
    level_3: "CEO"
    level_4: "Board Compliance Committee"
    emergency_contact: "legal@ssid.company"
    external_counsel: "compliance-emergency@lawfirm.com"

  internal_review_maintainers:
    monthly_reviewer: "Compliance Team Lead"
    quarterly_reviewer: "Senior Compliance Officer + Legal"
    semi_annual_reviewer: "Executive Compliance Committee"
    
  external_reviewer_pool:
    - "Dr. Sarah Miller, Compliance Consulting LLC"
    - "Michael Brown, CPA, Audit Partners"
    - "Prof. Dr. Klaus Weber, Regulatory Consulting GmbH"
    
  review_coordinator: "Maria Schmidt"
  backup_coordinator: "Thomas Klein"

  vacation_coverage:
    minimum_coverage: 2
    notification_period: "2 weeks"
    handover_required: true
    documentation: "23_compliance/governance/handover_template.md"
    business_continuity: "Critical for regulatory deadlines"
```

### Source of Truth Documentation (Enterprise)
```markdown
# 23_compliance/governance/source_of_truth_enterprise.md

## Badge & Metrics Source References (Internal)

### Structure Compliance Badge
- **Source:** `12_tooling/scripts/structure_guard.sh:line_127`
- **Formula:** Line 89-95 in structure_guard.sh
- **Threshold:** Defined in `23_compliance/metrics/threshold_rationale_internal.yaml:line_8`
- **Dependencies:** `23_compliance/policies/structure_policy.yaml`
- **Internal Override:** Business-critical modules >= 95%

### Test Coverage Badge (Tiered)
- **Source:** `pytest.ini:coverage_threshold` + `.github/workflows/test.yml:line_45`
- **Formula:** pytest-cov standard calculation
- **Global Threshold:** 90% as defined in `23_compliance/metrics/threshold_rationale_internal.yaml:line_15`
- **Business-Critical:** >= 95% (enforcement via CI gate)
- **Compliance Modules:** >= 99% (regulatory requirement)
- **Dependencies:** All module `tests/` directories

### Compliance Coverage Badge (Internal)
- **Source:** `23_compliance/scripts/compliance_coverage_calculator.py:class_ComplianceCalculator`
- **Formula:** (Implemented Controls / Total Required Controls) * 100
- **Threshold:** >= 98% (internal standard)
- **Jurisdictional Minimum:** >= 95% per market
- **Dependencies:** All jurisdictional mapping YAMLs

### Anti-Gaming Controls (Enterprise)
- **Circular Dependencies:** `23_compliance/anti_gaming/circular_dependency_validator.py:class_EnterpriseValidator`
- **Badge Integrity:** `23_compliance/anti_gaming/badge_integrity_checker.sh:function_enterprise_verify`
- **Business Logic Gaming:** `23_compliance/anti_gaming/overfitting_detector.py:enterprise_sampling`
- **Dependency Graph:** `23_compliance/anti_gaming/dependency_graph_generator.py:export_enterprise_graph`
```

## Social & Ecosystem Compatibility Framework

### Diversity & Inclusion Standards
```yaml
# 23_compliance/social_ecosystem/diversity_inclusion_config.yaml
version: "1.0"
date: "2025-09-15"
deprecated: false
classification: "CONFIDENTIAL - Enterprise Social Responsibility"

international_standards:
  geographic_coverage:
    - region: "European Union"
      standards: ["GDPR", "AI Act", "eIDAS 2.0", "MiCA", "DORA"]
      localization: "23_compliance/regional/eu/"
      business_priority: "CRITICAL"
      
    - region: "United States"
      standards: ["SOC2", "CCPA", "FTC Guidelines", "SEC Regulations"]
      localization: "23_compliance/regional/us/"
      business_priority: "HIGH"
      
    - region: "Asia Pacific"
      standards: ["Singapore MAS", "Japan JVCEA", "Hong Kong SFC", "Australia ASIC"]
      localization: "23_compliance/regional/apac/"
      business_priority: "HIGH"
      
    - region: "Switzerland"
      standards: ["FINMA", "DLT Act", "Swiss Data Protection Act"]
      localization: "23_compliance/regional/ch/"
      business_priority: "MEDIUM"
      
    - region: "United Kingdom"
      standards: ["FCA Rules", "UK GDPR", "PCI DSS"]
      localization: "23_compliance/regional/uk/"
      business_priority: "HIGH"

accessibility_compliance:
  wcag_version: "2.1"
  baseline: "AA"
  aaa_scope: "critical_flows_only"
  screen_reader_compatible: true
  keyboard_navigation: true
  color_contrast_ratio: "4.5:1"
  language_support: ["en", "de", "fr", "es", "it", "ja", "ko", "zh"]
  rtl_language_support: true
  business_localization: "market_specific_requirements"
  wcag_aaa_note: "AAA compliance on selected critical flows only"
  
community_participation:
  open_contribution: true
  translation_program: true
  accessibility_review: "required"
  diverse_reviewer_pool: true
  enterprise_participation: "strategic_partnerships"
  
  marginalized_communities:
    support: true
    accessibility_fund: "enterprise_funded"
    translation_priority: ["indigenous_languages", "sign_languages"]
    outreach_programs: "23_compliance/social_ecosystem/outreach/"
    business_impact: "market_expansion_opportunities"
    
  economic_inclusion:
    low_income_access: true
    educational_discounts: true
    developing_nation_support: true
    internet_connectivity_alternatives: true
    enterprise_social_programs: "community_investment"

dao_governance_compatibility:
  governance_models:
    - "Traditional Corporate"
    - "DAO (Decentralized Autonomous Organization)"
    - "Hybrid (Corporate + DAO)"
    - "NGO/Non-Profit"
    - "Government/Public Sector"
    - "Academic Institution"
    - "Community Cooperative"
    - "Enterprise Consortium"
    
  voting_mechanisms:
    - "Token-based voting"
    - "Stake-weighted voting"
    - "Quadratic voting"
    - "Conviction voting"
    - "Reputation-based voting"
    - "Traditional board voting"
    - "Enterprise stakeholder voting"
    
  decision_frameworks:
    consensus_mechanisms: ["majority", "supermajority", "consensus", "rough_consensus"]
    quorum_requirements: "configurable"
    proposal_processes: "23_compliance/social_ecosystem/dao_proposals/"
    veto_rights: "configurable"
    business_stakeholder_rights: "protected"
    
unbanked_community_support:
  no_bank_account_required: true
  alternative_identity_verification: true
  offline_capability: "limited"
  sms_notifications: true
  ussd_support: "planned"
  agent_network_compatible: true
  enterprise_financial_inclusion: "market_expansion_strategy"
```

### ESG & Sustainability Integration
```yaml
# 23_compliance/social_ecosystem/esg_sustainability_config.yaml
version: "1.0"
date: "2025-09-15"
deprecated: false
classification: "CONFIDENTIAL - Enterprise ESG Strategy"

environmental_standards:
  carbon_footprint:
    tracking_enabled: true
    reporting_standard: "GHG Protocol"
    target: "carbon_neutral_2027"
    offset_program: "enterprise_verified"
    business_reporting: "annual_sustainability_report"
    
  energy_efficiency:
    green_hosting_preferred: true
    renewable_energy_target: "100%_by_2026"
    energy_monitoring: "24_meta_orchestration/monitoring/energy/"
    cost_optimization: "efficiency_roi_tracking"
    
  circular_economy:
    code_reusability_score: "track"
    resource_optimization: "continuous"
    waste_reduction: "digital_first"
    business_efficiency: "operational_cost_reduction"

social_responsibility:
  un_sdg_mapping:
    - sdg_1: "No Poverty - Financial inclusion features"
    - sdg_4: "Quality Education - Open educational resources" 
    - sdg_5: "Gender Equality - Inclusive design principles"
    - sdg_8: "Decent Work - Fair contributor compensation"
    - sdg_10: "Reduced Inequalities - Accessibility compliance"
    - sdg_16: "Peace, Justice, Strong Institutions - Transparent governance"
    - sdg_17: "Partnerships - Multi-stakeholder collaboration"
    
  social_impact_metrics:
    accessibility_score: "track"
    inclusion_index: "track"
    community_satisfaction: "survey_quarterly"
    contributor_diversity: "measure_report"
    business_value_creation: "community_driven_innovation"

governance_excellence:
  transparency_requirements:
    - "All governance decisions public (non-confidential)"
    - "Financial transparency (where legally required)"
    - "Stakeholder engagement records"
    - "Impact assessment reports"
    - "Enterprise accountability framework"
    
  ethics_framework:
    code_of_conduct: "23_compliance/social_ecosystem/ethics/code_of_conduct.md"
    conflict_of_interest: "23_compliance/social_ecosystem/ethics/conflict_policy.md"
    whistleblower_protection: "23_compliance/social_ecosystem/ethics/whistleblower.md"
    business_ethics: "enterprise_compliance_integration"
    
  stakeholder_engagement:
    user_council: "planned"
    developer_advisory: "active"
    regulatory_liaison: "active"
    community_feedback: "continuous"
    enterprise_advisory_board: "strategic_direction"
```

### Multi-Sector Compatibility Matrix
```yaml
# 23_compliance/social_ecosystem/sector_compatibility.yaml
version: "1.0"
date: "2025-09-15"
deprecated: false
classification: "CONFIDENTIAL - Enterprise Market Analysis"

sector_support:
  financial_services:
    regulations: ["MiCA", "PSD2", "Basel III", "SOX", "FINMA", "BaFin"]
    risk_level: "high"
    audit_frequency: "annual"
    specialized_controls: "21_post_quantum_crypto/financial/"
    business_opportunity: "high_value_market"
    revenue_potential: "significant"
    
  healthcare:
    regulations: ["HIPAA", "GDPR", "FDA 21 CFR Part 11", "ISO 13485", "MDR"]
    risk_level: "critical"
    audit_frequency: "biannual"
    specialized_controls: "20_foundation/security/healthcare/"
    business_opportunity: "emerging_market"
    revenue_potential: "moderate"
    
  government_public_sector:
    regulations: ["FedRAMP", "Authority to Operate", "NIST 800-53", "ISO 27001"]
    risk_level: "critical"
    audit_frequency: "annual"
    specialized_controls: "15_infra/security/government/"
    business_opportunity: "stable_contracts"
    revenue_potential: "high"
    
  education:
    regulations: ["FERPA", "COPPA", "GDPR", "Accessibility Standards"]
    risk_level: "medium"
    audit_frequency: "annual"
    specialized_controls: "13_ui_layer/accessibility/"
    business_opportunity: "social_impact"
    revenue_potential: "moderate"
    
  gaming_entertainment:
    regulations: ["ESRB", "Age Rating", "Gambling Regulations", "Consumer Protection"]
    risk_level: "medium"
    audit_frequency: "annual"
    specialized_controls: "01_ai_layer/content_moderation/"
    business_opportunity: "growth_market"
    revenue_potential: "high"
    
  iot_manufacturing:
    regulations: ["CE Marking", "FCC", "Cybersecurity Act", "Product Safety"]
    risk_level: "high"
    audit_frequency: "per_product"
    specialized_controls: "19_adapters/iot_security/"
    business_opportunity: "emerging_IoT"
    revenue_potential: "significant"

cross_sector_features:
  regulatory_change_notification: true
  sector_specific_templates: true
  compliance_gap_analysis: "automated"
  risk_assessment_tools: "07_governance_legal/risk_tools/"
  audit_preparation: "23_compliance/sector_audits/"
  business_development: "sector_specific_strategies"
```

## Module-Strukturen (MUST/OPTIONAL)

### Kern-Module
**01_ai_layer:** `agents/`, `prompts/`, `evaluation/`, `safety/`, `runtimes/`  
**03_core:** `domain/`, `services/`, `api/`, `schemas/`, `tokenomics/`  
**08_identity_score:** `models/`, `rules/`, `api/`  
**09_meta_identity:** `schemas/`, `resolvers/`, `profiles/`  
**14_zero_time_auth:** `wallet/`, `sso/`, `flows/`, `policies_local/`

### Compliance/Audit (Enhanced)
**02_audit_logging:** `ingest/`, `processors/`, `storage/`, `retention/`, `blockchain_anchors/`  
**23_compliance:** `policies/`, `evidence/`, `mappings/`, `exceptions/`, `tests/`, `anti_gaming/`, `reviews/`, `governance/`  
**24_meta_orchestration:** `triggers/ci/`, `registry/`, `pipelines/`

### Tech-Module
**04_deployment:** `ci/blueprints/`, `cd/strategies/`, `containers/`, `manifests/`  
**12_tooling:** `scripts/`, `linters/`, `generators/`, `hooks/`  
**15_infra:** `k8s/`, `terraform/`, `network/`, `secrets/`  
**17_observability:** `dashboards/`, `alerts/`, `otel/`, `score/`

### Data & Standards
**06_data_pipeline:** `ingestion/`, `preprocessing/`, `training/`, `eval/`, `deployment/`  
**10_interoperability:** `standards/`, `mappings/`, `connectors/`  
**18_data_layer:** `schemas/`, `repositories/`, `migrations/`, `adapters/`  
**22_datasets:** `raw/`, `interim/`, `processed/`, `external/`, `reference/`

### Support-Module
**05_documentation:** `architecture/`, `runbooks/`, `adr/`, `references/`  
**07_governance_legal:** `legal/`, `risk_links/`, `approvals/`  
**11_test_simulation:** `unit/`, `integration/`, `e2e/`, `fixtures/`  
**13_ui_layer:** `admin_frontend/`, `partner_dashboard/`, `public_frontend/`, `design_system/`  
**16_codex:** `playbooks/`, `patterns/`, `guides/`  
**19_adapters:** `web3/`, `payments/`, `messaging/`, `identity/`  
**20_foundation:** `utils/`, `security/`, `serialization/`, `config/`, `tokenomics/`  
**21_post_quantum_crypto:** `algorithms/`, `keystores/`, `adapters/`, `benchmarks/`

### Detaillierte Modul-Strukturerklärungen

#### 1. Kern-Module
**01_ai_layer:**
- `agents/` → Agenten-Frameworks, Policy- und Workflow-Automation
- `prompts/` → Prompt-Vorlagen, Prompt-Generatoren, Prompt-Katalog
- `evaluation/` → Evaluationslogik, Metriken, Prompt-Tests
- `safety/` → Safety-Checker, Blacklist, Toxicity-Filter
- `runtimes/` → KI-Ausführungsumgebungen (Container, Runner, Adapters)

**03_core:**
- `domain/` → Domain-Objekte, zentrale Datenmodelle
- `services/` → Kernservices, Backend-Services
- `api/` → API-Definitionen, OpenAPI, Endpunkte
- `schemas/` → Schemas (JSON, YAML), Datenvalidierung
- `tokenomics/` → Token-Modelle, Onchain-Schemata, Reward- und Fee-Logik

**08_identity_score:**
- `models/` → Score-Modelle, Bewertungs-Algorithmen
- `rules/` → Score-Regeln, Policy-Dateien
- `api/` → Score-API, Integrationsschnittstellen

**09_meta_identity:**
- `schemas/` → Identity-Schemas, Mapping
- `resolvers/` → Identifier-Resolver, DID-Resolver
- `profiles/` → Profile, Attributzuordnung, Identity-Templates

**14_zero_time_auth:**
- `wallet/` → Wallet-Module, Wallet-API, Key-Verwaltung
- `sso/` → Single-Sign-On-Mechanismen
- `flows/` → Authentifizierungsflows
- `policies_local/` → Lokale Auth-Policies

#### 2. Compliance/Audit (Enhanced)
**02_audit_logging:**
- `ingest/` → Ingest-Prozesse, Log-Intake
- `processors/` → Log-Processor, Pre-Processing
- `storage/` → Audit-Storage, WORM-Backends
- `retention/` → Aufbewahrung, Lösch-Policies
- `blockchain_anchors/` → Onchain-Anchoring, Immutable Proofs

**23_compliance:**
- `policies/` → Policy-Files (YAML, JSON)
- `evidence/` → Evidenzsammlung (Reports, Audit-Logs, Hashes)
- `mappings/` → Policy- und Law-Mappings (MiCA, eIDAS, etc.)
- `exceptions/` → Ausnahmen, Sonderregeln
- `tests/` → Compliance-Testfälle, Unit-Tests
- `anti_gaming/` → Anti-Gaming-Module, Betrugserkennung
- `reviews/` → Policy-Reviews, Review-Protokolle
- `governance/` → Compliance-Governance, Verantwortlichkeiten

**24_meta_orchestration:**
- `triggers/ci/` → CI-Trigger, Build-Hooks
- `registry/` → Registry, Logs, Strukturdaten
- `pipelines/` → Orchestrator-Pipelines, Automationslogik

#### 3. Tech-Module
**04_deployment:**
- `ci/blueprints/` → CI-Blueprints, Workflow-Vorlagen
- `cd/strategies/` → CD-Strategien, Release-Logik
- `containers/` → Container-Definitions, Dockerfiles
- `manifests/` → Deployment-Manifeste

**12_tooling:**
- `scripts/` → Python-/Bash-Skripte
- `linters/` → Linter-Configs, Custom-Linter
- `generators/` → Generatoren für Code, Templates
- `hooks/` → Git-/Pre-/Post-Hooks

**15_infra:**
- `k8s/` → Kubernetes-Konfigurationen
- `terraform/` → Terraform-Module
- `network/` → Netzwerkinfrastruktur
- `secrets/` → Secrets-Management (keine echten Secrets ins Repo!)

**17_observability:**
- `dashboards/` → Monitoring-Dashboards
- `alerts/` → Alert-Definitions
- `otel/` → OpenTelemetry-Konfiguration
- `score/` → Score-Visualisierung, Score-Reports

#### 4. Data & Standards
**06_data_pipeline:**
- `ingestion/` → Datenaufnahme
- `preprocessing/` → Vorverarbeitung
- `training/` → Trainingsdaten/-pipelines
- `eval/` → Evaluation
- `deployment/` → Auslieferung von ML/AI-Modellen

**10_interoperability:**
- `standards/` → Standards (z. B. OIDC, SAML)
- `mappings/` → Schnittstellen-/Standard-Mappings
- `connectors/` → Connectoren zu externen Systemen

**18_data_layer:**
- `schemas/` → Datenbankschemas
- `repositories/` → DB-Repositories, ORM
- `migrations/` → Migrationsdateien
- `adapters/` → Adapter zu externen Data-Sources

**22_datasets:**
- `raw/` → Rohdaten
- `interim/` → Zwischenstände
- `processed/` → Aufbereitete Datensätze
- `external/` → Externe Datensätze
- `reference/` → Referenzdatensätze

#### 5. Support-Module
**05_documentation:**
- `architecture/` → Architektur-Dokumentation
- `runbooks/` → Betriebs-/Incident-Runbooks
- `adr/` → Architecture Decision Records
- `references/` → Referenzen, externe Quellen

**07_governance_legal:**
- `legal/` → Legal Files, Verträge
- `risk_links/` → Risikoverknüpfungen
- `approvals/` → Approval-Dokumente

**11_test_simulation:**
- `unit/` → Unittests
- `integration/` → Integrationstests
- `e2e/` → End-to-End-Tests
- `fixtures/` → Testdaten, Fixtures

**13_ui_layer:**
- `admin_frontend/` → Admin-UI
- `partner_dashboard/` → Partner-Dashboard
- `public_frontend/` → Öffentliches UI
- `design_system/` → UI-Komponenten, Designsystem

**16_codex:**
- `playbooks/` → Playbooks, Schritt-für-Schritt-Anleitungen
- `patterns/` → Patterns, Best Practices
- `guides/` → Guides, How-Tos

**19_adapters:**
- `web3/` → Web3-Adapter
- `payments/` → Zahlungsadapter
- `messaging/` → Messaging-Adapter
- `identity/` → Identity-Adapter

**20_foundation:**
- `utils/` → Utilities, Helper
- `security/` → Security-Komponenten
- `serialization/` → Serialisierer
- `config/` → Config-Dateien
- `tokenomics/` → Tokenomics-Utilities

**21_post_quantum_crypto:**
- `algorithms/` → Post-Quantum-Krypto-Algorithmen
- `keystores/` → Key-Stores
- `adapters/` → PQC-Adapter
- `benchmarks/` → Benchmarks

### Modul-Zweck Übersicht

| Modul | Zweck / Aufgabe |
|-------|-----------------|
| **01_ai_layer** | KI/Agenten, Prompt- und Workflow-Logik, KI-Sicherheit |
| **02_audit_logging** | Audit-Logs, Retention, Onchain-Evidence |
| **03_core** | Hauptlogik, Domain-Services, APIs, Tokenomics |
| **04_deployment** | CI/CD, Deployments, Containerization |
| **05_documentation** | Doku, Architektur, ADRs, Runbooks |
| **06_data_pipeline** | Data Engineering, ML-Pipelines, Trainingsdaten |
| **07_governance_legal** | Legal, Compliance-Verknüpfung, Approvals |
| **08_identity_score** | Reputations-, Score- und Trustlogik |
| **09_meta_identity** | Identitäts-Mapping, DID/Resolver, Attributprofile |
| **10_interoperability** | Standards, externe Integrationen, Connectoren |
| **11_test_simulation** | Alle Testarten (Unit, Integration, e2e, Fixtures) |
| **12_tooling** | Tools, Scripts, Linter, Generatoren, Hooks |
| **13_ui_layer** | UI-Schichten: Admin, Partner, Public, Designsystem |
| **14_zero_time_auth** | Authentifizierung, Wallet, SSO, lokale Auth-Policies |
| **15_infra** | Infrastruktur: K8s, Terraform, Netz, Secrets |
| **16_codex** | Playbooks, Guides, Patterns |
| **17_observability** | Monitoring, Dashboards, Alerts, OTEL, Score |
| **18_data_layer** | DB-Schemas, Migrations, Repositories, Adapter |
| **19_adapters** | Adapters für Web3, Payment, Messaging, Identity |
| **20_foundation** | Utilities, Security, Serialization, Config, Tokenomics |
| **21_post_quantum_crypto** | Post-Quantum-Krypto, Algorithmen, Keystores, Adapter, Benchmarks |
| **22_datasets** | Roh-, Zwischen-, Referenz- und Externe Datensätze |
| **23_compliance** | Policies, Evidence, Mapping, Tests, Governance, Anti-Gaming, Reviews, Exceptions |
| **24_meta_orchestration** | Orchestrator, Pipelines, Registry, CI-Trigger |

## 100-Punkte-Scoring (Automatisch + Anti-Gaming Enhanced)

| Kategorie | Gewichtung | Penalty-Beispiele | Ziel |
|-----------|------------|-------------------|------|
| **Root-Konformität** | 40% | Extra Root: -3, Fehlend: -5 | Exakt 24 Root-Ordner |
| **MUST-Ordner** | 30% | Fehlende MUST: -2 | Alle Module-MUST vorhanden |
| **Naming** | 20% | Convention-Violations: -1 | snake_case, keine Umlaute |
| **Anti-Duplikat** | 10% | Verbotene Items: -10 | Keine modulnahen Policies |

### Badge Threshold Justification (Enhanced)
```yaml
# 23_compliance/metrics/threshold_rationale_internal.yaml
version: "1.1"
date: "2025-09-15"
deprecated: false
classification: "CONFIDENTIAL - Internal Standards"
last_review: "2025-09-15"
next_review: "2026-03-15"

thresholds:
  structure_compliance:
    threshold: ">= 95%"
    rationale: "Enterprise-Grade mit 5% Toleranz für Edge Cases und Transitionen"
    business_impact: "Kritisch für interne Audits und externe Compliance"
    internal_note: "Höhere Standards als Public-Version für interne Qualität"
    deprecated: false
    benchmark_source: "Internal enterprise compliance framework"
    
  test_coverage:
    threshold: ">= 90%"
    rationale: "Production-Standard mit 10% Toleranz für Legacy und Integration"
    business_impact: "Essential für Reliability und Enterprise-Einsatz"
    deprecated: false
    tiered_requirements:
      business_critical: ">= 95%"
      security_modules: ">= 98%"
      compliance_modules: ">= 99%"
    internal_exception: "Business-kritische Module: >= 95%"
    
  compliance_coverage:
    threshold: ">= 98%"
    rationale: "Höchste Standards für regulatorische Vollabdeckung"
    business_impact: "Kritisch für Marktzulassungen und Audits"
    deprecated: false
    jurisdictional_requirements:
      eu_markets: ">= 99%"
      apac_markets: ">= 97%"
      americas_markets: ">= 96%"
      emerging_markets: ">= 95%"
    jurisdictions: "Alle definierten Märkte müssen >= 95% erreichen"
    
  review_cycle:
    requirement: "Internal 3 months + External 6 months"
    rationale: "Höhere Review-Frequenz für Enterprise-Risiko-Management"
    cost_benefit: "Höherer Aufwand aber maximaler Compliance-Schutz"
    deprecated: false
    escalation_trigger: "Review overdue by 15 days (stricter than public)"
```

**Compliance-Level:**  
- **100 = COMPLIANT** (Produktiv)  
- **90+ = HIGH** (Release mit Monitoring)  
- **70+ = MEDIUM** (Development)  
- **<70 = LOW** (Sanierung erforderlich)

## Anti-Gaming & Integrity Controls (Enhanced Enterprise)

### Badge Integrity Framework (Enterprise)
```yaml
# 23_compliance/anti_gaming/badge_integrity_enterprise.yaml
version: "1.0"
date: "2025-09-15"
deprecated: false
classification: "CONFIDENTIAL - Enterprise Controls"

controls:
  circular_dependency_check:
    description: "Enterprise-Grade Validation gegen zirkuläre Referenzen"
    script: "23_compliance/anti_gaming/circular_dependency_validator.py"
    script_deprecated: false
    frequency: "Every commit + Daily full scan"
    threshold: "Zero circular dependencies allowed"
    escalation: "Block deployment on violation"
    dependency_map_export: "23_compliance/anti_gaming/dependency_maps/"
    export_formats: ["dot", "json", "svg", "enterprise_dashboard"]
  
  business_logic_overfitting:
    description: "Validierung gegen Business-Gaming und Metric-Optimierung"
    method: "Random sampling + Quarterly manual review"
    script: "23_compliance/anti_gaming/overfitting_detector.py"
    script_deprecated: false
    frequency: "Weekly automated + Monthly manual"
    sample_size: "20%" # Higher than public 15%
    reviewer_required: true
    internal_audit: "Quarterly by compliance team"
  
  enterprise_badge_validation:
    description: "Enterprise Badge-Berechnungen gegen dokumentierte Formeln"
    script: "23_compliance/anti_gaming/badge_integrity_checker.sh"
    script_deprecated: false
    frequency: "Every PR + Pre-release"
    documentation_required: true
    business_review: "Quarterly threshold review"
    source_validation: true
    formula_verification: true

dependency_graph_generation:
  enabled: true
  script: "23_compliance/anti_gaming/dependency_graph_generator.py"
  output_directory: "23_compliance/anti_gaming/dependency_maps/"
  formats:
    dot: true
    json: true
    svg: true
    enterprise_dashboard: true
    confidential_mapping: true
  update_frequency: "Daily"
  ci_integration: true
  classification: "CONFIDENTIAL"

external_review_cycle:
  frequency: "Every 6 months"
  last_review: "2025-09-15"
  next_review: "2026-03-15"
  internal_review: "Every 3 months (zusätzlich)"
  reviewer_requirements:
    - "External: Independent third party (nicht Projekt-Maintainer)"
    - "Internal: Senior Compliance Officer + Legal Review"
    - "Credentials: Compliance/Audit background erforderlich"
    - "Clearance: Access to confidential compliance mappings"
    - "Documentation: 23_compliance/reviews/ + internal audit trail"
  
  review_scope:
    - "Badge calculation logic verification"
    - "Circular dependency analysis"
    - "Business compliance matrix accuracy check"
    - "Anti-gaming control effectiveness"
    - "Internal audit trail validation"
    - "Regulatory mapping completeness"
    - "Dependency graph validation (confidential)"
    - "Business logic gaming assessment"
```

### Gaming Prevention Measures (Enterprise)
- **Circular Dependencies:** Enterprise-Grade Checks + tägliche Full-Scans + Dashboard-Monitoring
- **Business Overfitting:** Wöchentliche + monatliche manuelle Reviews + 20% Sampling
- **Internal Gaming:** Zusätzliche 3-Monats interne Reviews
- **Regulatory Gaming:** Spezielle Checks für Jurisdictions-Mappings
- **Audit Trail Gaming:** Blockchain-verifizierte Evidence-Ketten
- **Dependency Visualization:** Enterprise Dashboard mit Confidential Mappings

## Machine-Readable Review System (Enterprise)

### Review Log (JSON/YAML Integration)
```json
// 23_compliance/reviews/review_log_enterprise.json
{
  "review_system_version": "1.0",
  "classification": "CONFIDENTIAL",
  "last_updated": "2025-09-15T10:30:00Z",
  "review_history": [
    {
      "review_id": "2025-09-15-external",
      "date": "2025-09-15",
      "type": "external",
      "reviewer": {
        "name": "Dr. Sarah Miller",
        "organization": "Compliance Consulting LLC",
        "credentials": "CPA, CISA",
        "independence_verified": true,
        "clearance_verified": true
      },
      "status": "PASS",
      "matrix_version": "2.1",
      "badge_logic_version": "1.0",
      "findings": {
        "critical": 0,
        "major": 1,
        "minor": 3
      },
      "score": "98/100",
      "next_review": "2026-03-15",
      "report_path": "23_compliance/reviews/external_review_2025-09-15.md",
      "dependencies_validated": 156,
      "circular_dependencies_found": 0,
      "badge_integrity_validated": true,
      "compliance_matrix_accuracy": "99.2%",
      "jurisdictional_coverage": {
        "eu_markets": "99.8%",
        "apac_markets": "98.1%",
        "americas_markets": "97.3%"
      }
    }
  ],
  "internal_review_history": [
    {
      "review_id": "2025-09-01-quarterly",
      "date": "2025-09-01",
      "type": "internal_quarterly",
      "reviewer": "Senior Compliance Officer",
      "classification": "CONFIDENTIAL",
      "business_risk_assessment": "LOW",
      "competitive_advantage_maintained": true
    }
  ],
  "review_schedule": {
    "next_internal_monthly": "2025-10-15",
    "next_internal_quarterly": "2025-12-15",
    "next_external": "2026-03-15",
    "overdue_reviews": [],
    "business_critical_reviews": []
  },
  "ci_integration": {
    "pr_checks_enabled": true,
    "review_status_check": "required",
    "overdue_review_blocking": true,
    "business_review_blocking": true,
    "last_automated_check": "2025-09-15T09:15:00Z"
  }
}
```

### Review CI/CD Integration (Enterprise)
```yaml
# .github/workflows/review_validation_enterprise.yml
name: Enterprise Review Status Validation
on: [pull_request, schedule]

jobs:
  check_review_status:
    runs-on: ubuntu-latest
    steps:
      - name: Validate Internal Review Currency
        run: |
          python 23_compliance/reviews/review_status_checker.py --enterprise
          # Fails if internal reviews overdue or business logic changed
      
      - name: Validate Business Compliance
        run: |
          python 23_compliance/reviews/business_compliance_checker.py
          # Enterprise-specific business logic validation
          
      - name: Update Review Log
        run: |
          python 23_compliance/reviews/update_review_log.py --pr-context --enterprise
          # Updates machine-readable log with enterprise context
```

## EU-Regulatorik-Mapping (Vollständig + Versioniert)

### Versioned Regulatory Mappings
```yaml
# 23_compliance/mappings/eu_regulatorik_v2.1.yaml
version: "2.1"
date: "2025-09-15"
deprecated: false
regulatory_basis: "EU-Gesamtpaket 2024/2025 + Brexit-Updates"
classification: "CONFIDENTIAL - Internal Compliance Mappings"

deprecated_mappings:
  - id: "eidas_v1_old"
    name: "eIDAS 910/2014 (Original)"
    status: "deprecated"
    deprecated: true
    replaced_by: "eidas2_eudi"
    deprecation_date: "2025-06-01"
    migration_deadline: "2026-05-20"
    notes: "Ersetzt durch eIDAS 2.0/EUDI Framework"

active_mappings:
  eidas2_eudi: 
    name: "eIDAS 2.0/EUDI"
    path: "23_compliance/mappings/eidas2_eudi/"
    deprecated: false
    business_priority: "HIGH"
    
  gdpr: 
    name: "GDPR (EU) 2016/679"
    path: "23_compliance/mappings/gdpr/"
    deprecated: false
    business_priority: "CRITICAL"
    
  mica: 
    name: "MiCA (EU) 2023/1114"
    path: "23_compliance/mappings/mica/"
    deprecated: false
    business_priority: "CRITICAL"
    
  nis2: 
    name: "NIS2 (EU) 2022/2555"
    path: "23_compliance/mappings/nis2/"
    deprecated: false
    business_priority: "HIGH"
    
  ai_act: 
    name: "AI Act (EU) 2024/1689"
    path: "23_compliance/mappings/ai_act/"
    deprecated: false
    business_priority: "HIGH"
    
  dora: 
    name: "DORA (EU) 2022/2554"
    path: "23_compliance/mappings/dora/"
    deprecated: false
    business_priority: "HIGH"
    
  psd3: 
    name: "PSD3/PSR (EU)"
    path: "23_compliance/mappings/psd3/"
    deprecated: false
    business_priority: "MEDIUM"
    
  psd2: 
    name: "PSD2 (EU)"
    path: "23_compliance/mappings/psd2/"
    deprecated: false
    business_priority: "MEDIUM"
    successor: "psd3"
    
  data_act: 
    name: "Data Act (EU)"
    path: "23_compliance/mappings/data_act/"
    deprecated: false
    business_priority: "MEDIUM"
    
  aml6_amlr: 
    name: "6th AMLD/AMLR"
    path: "23_compliance/mappings/aml6_amlr/"
    deprecated: false
    business_priority: "HIGH"
    
  amla: 
    name: "AMLA (EU Aufsicht)"
    path: "23_compliance/mappings/amla/"
    deprecated: false
    business_priority: "HIGH"
    
  iso_42001: 
    name: "ISO/IEC 42001:2023 (AI Management System)"
    path: "23_compliance/mappings/iso_42001/"
    deprecated: false
    busine
HASH_END::B


---

## MAXIMALSTAND ADDENDUM – Registry Pflichtstruktur (logs + locks) – Canonical
*generated:* 2025-09-30T12:02:08Z

```text
24_meta_orchestration/
  registry/                               # KANONISCH (zentral, keine modulnahen Registries erlaubt)
    logs/                                 # MUSS existieren
      registry_events.log                 # Append-only (WORM-kompatibel)
      registry_audit.yaml                 # Audit-Änderungen (structured)
      integrity_checksums.json            # SHA256 aller Registry-Artefakte
      chat_ingest/                        # Intake für die nächsten 6 Chat-Dateien
        chat_01.md
        chat_02.md
        chat_03.md
        chat_04.md
        chat_05.md
        chat_06.md
    locks/                                # MUSS existieren
      owner.yaml                          # Owner/Signer der Registry
      registry_lock.yaml                  # Version/Blueprint-Lock (A–C Hashes)
      hash_chain.json                     # Append-only Hash-Ledger
    manifests/                            # MUSS existieren
      registry_manifest.yaml              # Index 24×16 Shards
      version_manifest.json               # Artefakt-Versionen
      compliance_manifest.yaml            # Mapping → 23_compliance/*
    registry_index.yaml                   # Einstiegspunkt
```
**Bau-Regel:** Wird einer dieser Pfade nicht erzeugt → **FAIL** (Exit Code 24) im Gate `24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py`.


---

## MAXIMALSTAND ADDENDUM – Common MUST je Modul (Ebene 2)
*generated:* 2025-09-30T12:02:08Z

JEDES Root-Modul **muss** folgende Basis besitzen (physische Dateien/Ordner):
```text
module.yaml
README.md
docs/
src/
tests/
```
*module.yaml* enthält mindestens: `name`, `owner`, `version`, `status`, `last_update`, `max_depth`, `shard_profile`.


---

## MAXIMALSTAND ADDENDUM – Root-Depth-Matrix (Ebene 3–6, verbindlich)
*generated:* 2025-09-30T12:02:08Z

```yaml
root_depth_matrix:
  "01_ai_layer":
    max_depth: 3
    level_3: ["agents/", "prompts/", "evaluation/", "safety/", "runtimes/"]
  "02_audit_logging":
    max_depth: 5
    level_3: ["ingest/", "processors/", "storage/", "retention/", "blockchain_anchors/", "quarantine/"]
    level_4: ["quarantine/singleton/", "storage/worm/", "storage/blockchain_anchors/"]
    level_5: ["quarantine/singleton/quarantine_store/", "quarantine/singleton/quarantine_store/staging/"]
  "03_core":
    max_depth: 3
    level_3: ["domain/", "services/", "api/", "schemas/", "tokenomics/"]
  "04_deployment":
    max_depth: 3
    level_3: ["ci/blueprints/", "cd/strategies/", "containers/", "manifests/"]
  "05_documentation":
    max_depth: 5
    level_3: ["architecture/", "runbooks/", "adr/", "references/", "internationalization/"]
    level_4: ["internationalization/jurisdiction_specific/"]
    level_5: ["internationalization/jurisdiction_specific/en/technical/", "internationalization/jurisdiction_specific/de/compliance_eu/"]
    disabled:
      - "internationalization/jurisdiction_specific/zh/技术文档/"
  "06_data_pipeline":
    max_depth: 3
    level_3: ["ingestion/", "preprocessing/", "training/", "eval/", "deployment/"]
  "07_governance_legal":
    max_depth: 3
    level_3: ["legal/", "risk_links/", "stakeholder_protection/", "partnerships/"]
  "08_identity_score":
    max_depth: 3
    level_3: ["models/", "rules/", "api/"]
  "09_meta_identity":
    max_depth: 3
    level_3: ["schemas/", "resolvers/", "profiles/"]
  "10_interoperability":
    max_depth: 3
    level_3: ["standards/", "mappings/", "connectors/"]
  "11_test_simulation":
    max_depth: 3
    level_3: ["unit/", "integration/", "fuzz/"]
  "12_tooling":
    max_depth: 3
    level_3: ["scripts/", "linters/", "generators/", "hooks/"]
  "13_ui_layer":
    max_depth: 4
    level_3: ["admin_frontend/", "partner_dashboard/", "public_frontend/", "components/"]
    level_4: ["admin_frontend/app/", "partner_dashboard/app/", "public_frontend/app/"]
  "14_zero_time_auth":
    max_depth: 3
    level_3: ["wallet/", "sso/", "flows/", "policies_local/"]
  "15_infra":
    max_depth: 3
    level_3: ["k8s/", "terraform/", "network/", "secrets/"]
  "16_codex":
    max_depth: 3
    level_3: ["badges/", "matrices/", "artifacts/"]
  "17_observability":
    max_depth: 3
    level_3: ["dashboards/", "alerts/", "otel/", "score/", "logs/"]
  "18_data_layer":
    max_depth: 3
    level_3: ["schemas/", "repositories/", "migrations/", "adapters/"]
  "19_adapters":
    max_depth: 3
    level_3: ["wallets/", "shops/", "egov/", "ehealth/", "social/"]
  "20_foundation":
    max_depth: 3
    level_3: ["tokenomics/", "governance_specs/", "security/"]
  "21_post_quantum_crypto":
    max_depth: 3
    level_3: ["algorithms/", "allow_list/", "rotation/"]
  "22_datasets":
    max_depth: 3
    level_3: ["raw/", "interim/", "processed/", "external/", "reference/"]
  "23_compliance":
    max_depth: 6
    level_3: ["policies/", "evidence/", "mappings/", "exceptions/", "tests/", "anti_gaming/", "reviews/", "governance/", "jurisdictions/", "regional/"]
    level_4: ["evidence/ci_runs/", "regional/eu/", "jurisdictions/eu_eea_uk_ch_li/", "jurisdictions/americas/", "security/"]
    level_5: ["jurisdictions/eu_eea_uk_ch_li/uk_crypto_regime/", "privacy/ccpa_cpra/", "security/pqc/"]
    level_6: ["jurisdictions/us_ca_br_mx/us_irs_1099_da_final/"]
  "24_meta_orchestration":
    max_depth: 4
    level_3: ["triggers/ci/", "registry/", "pipelines/"]
    level_4: ["triggers/ci/gates/", "registry/logs/", "registry/locks/", "registry/manifests/"]
```
__Regel__: `max_depth` ist *erlaubte* Tiefe. Pfade unter `disabled:` dürfen **nicht** erstellt werden.


---

## MAXIMALSTAND ADDENDUM – SHARD-16 – Globale Pflicht-Belegung (für alle Roots)
*generated:* 2025-09-30T12:02:08Z

```yaml
shard_profile_default:
  S01_policies: "Policies/Konfigurationen"
  S02_evidence: "Evidenzen/Nachweise"
  S03_configs: "Technische Configs (YAML/JSON)"
  S04_registry: "Registries/Indizes (nur zentral erlaubt)"
  S05_tests: "Unit/Integration/Fuzz"
  S06_simulation: "Szenarien/Last/Fehlerbilder"
  S07_tooling: "CLI/Helper/Linter"
  S08_docs: "Docs/Runbooks/ADR"
  S09_api: "API/Interfaces"
  S10_adapters: "Bridges/Adapter zu Dritt-Systemen"
  S11_datasets: "Daten/Proben/Kataloge"
  S12_governance: "DAO/Stakeholder/Prozesse"
  S13_security: "Security/Keys/Rotation (ohne Secrets)"
  S14_interop: "Standards/Kompatibilität"
  S15_observability: "Dashboards/Alerts/OTEL/Score"
  S16_deployment: "CI/CD/Manifeste"
```
**Zuordnung:** Pro Modul werden S01–S16 auf die vorhandenen Ordner gemappt (z. B. `23_compliance/policies/` → `S01_policies`). Die kanonische Map liegt in:  
`24_meta_orchestration/registry/manifests/registry_manifest.yaml`.


---

## MAXIMALSTAND ADDENDUM – CORRECTION: LOGS vs LOCKS & Intake Relocation
*generated:* 2025-09-30T12:05:53Z

### Korrekturgrundsatz (SAFE-FIX, keine Löschung – nur Ergänzung)
Die Semantik der Ordner **LOGS** (nur Log-Dateien) und **LOCKS** (gesperrte/append-only/signed Artefakte) wird präzisiert. Vorherige Beispiele mit `chat_ingest/` und `audit.yaml` unter `logs/` werden **außer Kraft gesetzt** und hiermit **kanonisch** ersetzt.

### Kanonische Registry-Struktur (final, verbindlich)
```text
24_meta_orchestration/
  registry/
    logs/                       # NUR *.log oder *.log.jsonl (append-only)
      registry_events.log       # Ereignis-Log (WORM)
      access.log                # Zugriffe auf Registry
      error.log                 # Fehler-/Gate-Logs
    locks/                      # Gesperrte/append-only/signed Artefakte
      owner.yaml                # Signierter Owner/Signer (write-once)
      registry_lock.yaml        # Version/Blueprint-Lock (nur signierte Bumps)
      hash_chain.json           # Append-only Hash-Kette (jede Zeile = neuer Block)
    manifests/                  # Indexe & berechnete Zustände
      registry_manifest.yaml    # 24×16 Shard-Mapping (kanonisch)
      version_manifest.json     # Artefakt-Versionen (mutable, auditierbar)
      integrity_checksums.json  # SHA256-Checksums (mutable; NICHT unter logs/)
    intake/                     # NEU: Eingangsbereich (nicht-Logs)
      chat_ingest/              # Intake der 6 Chat-Dateien (keine Logfiles)
        chat_01.md
        chat_02.md
        chat_03.md
        chat_04.md
        chat_05.md
        chat_06.md
    registry_index.yaml         # Einstiegspunkt
```

### Verlagerungen (DELTA, canonical MOVE-Regeln)
- **chat_ingest/**: von `registry/logs/` → **`registry/intake/chat_ingest/`**
- **registry_audit.yaml**: von `registry/logs/` → **`23_compliance/evidence/registry/registry_audit.yaml`**
- **integrity_checksums.json**: von `registry/logs/` → **`registry/manifests/`**

### Dateityp-Policies (erzwingend)
- `registry/logs/`: **nur** `*.log` oder `*.log.jsonl` (append-only). Keine YAML/JSON außer `.log.jsonl`.
- `registry/locks/`: write-once / append-only (Owner/Lock/Hash-Kette). Änderungen nur per signiertem Prozess.
- `registry/manifests/`: berechnete Zustände/Indexe/Checksums (mutable, auditierbar).
- `registry/intake/`: Eingangsdaten (z. B. Chat-Dateien), werden nach Verarbeitung referenziert, nicht verschoben.

### CI-Gate-Anpassungen (erzwingen Semantik)
- **FAIL (Exit 24)**, wenn
  - unter `registry/logs/` Dateien ≠ `*.log` / `*.log.jsonl` liegen
  - `registry/locks/` fehlt oder unsignierte Änderungen erkannt werden
  - `integrity_checksums.json` nicht unter `registry/manifests/` liegt
  - `chat_ingest/` nicht unter `registry/intake/` liegt
- Gate-Datei (Beispiel): `24_meta_orchestration/triggers/ci/gates/structure_lock_l3.py`

### SHARD-16 Mapping (keine Änderung, nur Klarstellung für Intake)
- Die 6 Chat-Dateien aus `registry/intake/chat_ingest/` werden durch den Dispatcher in die **Pflicht-Roots (02,03,06,17,23,24)** und ggf. Indirekt-/Spezial-Roots verteilt; pro Root werden die **S01…S16**-Shards befüllt. Evidenz landet **nicht** in `registry/logs/`, sondern in `23_compliance/evidence/…` (WORM-geeignete Pfade).
