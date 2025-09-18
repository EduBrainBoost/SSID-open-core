# Compliance Template Usage Guide

This directory contains templates that automatically include the required legal disclaimer for all compliance-related outputs.

## Available Templates

### 1. Report Template (`report_template.md`)
**Usage**: All compliance reports, audit reports, evidence documentation
**Placeholders**:
- `{REPORT_TITLE}`, `{REPORT_DATE}`, `{REPORT_STATUS}`, etc.
**Requirement**: Legal disclaimer is automatically included

### 2. Badge Metrics Template (`badge_metrics_template.json`)
**Usage**: Badge scoring, metrics export, compliance dashboards
**Placeholders**:
- `{VERSION}`, `{STRUCTURE_SCORE}`, `{TEST_SCORE}`, etc.
**Requirement**: Legal disclaimer included in JSON structure

### 3. Dashboard Template (`dashboard_template.yaml`)
**Usage**: Compliance dashboard configurations
**Placeholders**:
- `{VERSION}`, `{DATE}`, `{DASHBOARD_COMPONENTS}`, etc.
**Requirement**: Legal disclaimer configuration included

### 4. API Response Template (`api_response_template.json`)
**Usage**: All API responses related to compliance data
**Placeholders**:
- `{API_VERSION}`, `{TIMESTAMP}`, `{COMPLIANCE_DATA_PLACEHOLDER}`, etc.
**Requirement**: Legal disclaimer and metadata included

## Template Usage Instructions

### Mandatory Requirements
1. **Always use these templates** for any compliance-related output
2. **Never remove or modify** the legal disclaimer text
3. **Replace all placeholders** with actual values
4. **Update version and date** when creating new documents

### Legal Disclaimer Text (NEVER MODIFY)
```
The SSID-open-core repository meets the Blueprint 4.x maximal standard according to local build and test systems.
All compliance, badge, and audit reports apply solely to the local repository and build state.
This does NOT constitute official certification under MiCA, eIDAS, DORA, ISO, SOC2, or any similar regulations.
External authorities, auditors, and reviewers are EXPLICITLY invited to review all artifacts free of charge and independently.
Official certifications require an external audit in accordance with the applicable regulatory requirements.
```

### Automation Integration

#### Scripts and Tools
All validation and reporting scripts should use these templates:
- `12_tooling/scripts/structure_guard.sh` - Use report template for evidence
- `23_compliance/anti_gaming/` scripts - Use metrics template for outputs
- Dashboard generators - Use dashboard template
- API implementations - Use API response template

#### CI/CD Integration
Templates should be automatically applied in:
- GitHub Actions workflows
- Pre-commit hooks
- Evidence generation
- Report automation

### Template Compliance Validation

#### Required Checks
1. Legal disclaimer presence validation
2. Placeholder replacement verification
3. Format consistency checking
4. Version tracking

#### Validation Script
```bash
# Check if document uses template and includes disclaimer
./12_tooling/scripts/template_compliance_checker.sh [document_path]
```

## Creating New Templates

### When to Create New Templates
- New types of compliance outputs
- Partner-specific documentation formats
- Regulatory-specific report formats
- Integration-specific API formats

### Template Requirements
1. **Include legal disclaimer** exactly as specified above
2. **Use clear placeholders** with descriptive names
3. **Document all placeholders** in this guide
4. **Test template validation** before deployment
5. **Add to automation scripts** as appropriate

### Template Naming Convention
- `{purpose}_template.{extension}`
- Examples: `audit_template.md`, `export_template.json`, `partner_template.yaml`

## Error Handling

### Missing Disclaimer
If legal disclaimer is missing from any compliance output:
- **Immediate action**: Add disclaimer using appropriate template
- **Root cause**: Update generation process to use templates
- **Prevention**: Implement template validation in CI/CD

### Incorrect Disclaimer Text
If disclaimer text is modified:
- **Immediate action**: Restore exact disclaimer text
- **Root cause**: Review modification process
- **Prevention**: Implement disclaimer text validation

### Missing Templates
If new compliance outputs are created without templates:
- **Immediate action**: Create appropriate template
- **Documentation**: Update this guide
- **Integration**: Add to automation systems

## Support

### Questions
- **Template Usage**: Create GitHub issue with `[TEMPLATE]` tag
- **Legal Questions**: Create GitHub issue with `[LEGAL]` tag
- **Technical Issues**: Create GitHub issue with `[COMPLIANCE]` tag

### Updates
This template system is part of the governance framework and follows the standard review cycle:
- **Review Frequency**: Quarterly
- **Owner**: Community Lead
- **Backup**: Technical Lead

---

**Legal & Audit Disclaimer:**
The SSID-open-core repository meets the Blueprint 4.x maximal standard according to local build and test systems.
All compliance, badge, and audit reports apply solely to the local repository and build state.
**This does NOT constitute official certification under MiCA, eIDAS, DORA, ISO, SOC2, or any similar regulations.**
External authorities, auditors, and reviewers are EXPLICITLY invited to review all artifacts free of charge and independently.
Official certifications require an external audit in accordance with the applicable regulatory requirements.