# MiCA Token Classification Policy — OPA/Rego
# Enforces utility token classification under Regulation (EU) 2023/1114
# SAFE-FIX: No PII, no secrets. Policy logic only.
# Generated: 2026-03-29 | Agent: A8-COMPLIANCE-MAPPING-CLOSURE

package ssid.compliance.mica.token_classification

# Default: token must pass all classification checks
default is_utility_token := false
default is_compliant_offer := false

# SSID token qualifies as utility token per Art. 3(1)(9)
is_utility_token if {
    provides_network_access
    not is_investment_vehicle
    not is_electronic_money
    not is_asset_referenced
}

# Token provides access to network services
provides_network_access if {
    input.token_type == "utility"
    input.provides_service_access == true
    input.service_description != ""
}

# Token must NOT be an investment vehicle
is_investment_vehicle if {
    input.promises_yield == true
}

is_investment_vehicle if {
    input.promises_profit == true
}

is_investment_vehicle if {
    input.promises_dividend == true
}

# Token must NOT be electronic money (Art. 3(1)(7))
is_electronic_money if {
    input.pegged_to_fiat == true
    input.maintains_stable_value == true
}

# Token must NOT be asset-referenced (Art. 3(1)(6))
is_asset_referenced if {
    input.references_asset_basket == true
}

# Compliant public offer under Title II
is_compliant_offer if {
    is_utility_token
    has_compliant_white_paper
    marketing_compliant
    withdrawal_right_enabled
}

# White paper must meet Art. 6 requirements
has_compliant_white_paper if {
    input.white_paper.exists == true
    input.white_paper.describes_issuer == true
    input.white_paper.describes_rights == true
    input.white_paper.describes_technology == true
    input.white_paper.risk_disclosure == true
    input.white_paper.notified_to_nca == true
}

# Marketing must meet Art. 7 requirements
marketing_compliant if {
    input.marketing.fair_and_clear == true
    input.marketing.consistent_with_white_paper == true
    not input.marketing.contains_yield_claims
    not input.marketing.contains_investment_advice
}

# Withdrawal right (Art. 12) — 14 calendar days
withdrawal_right_enabled if {
    input.withdrawal_period_days >= 14
}

# CASP exemption check — SSID is NOT a CASP
not_casp if {
    input.provides_custody == false
    input.provides_exchange == false
    input.provides_trading == false
    input.provides_advisory == false
}

# Violations for audit trail
violations[msg] if {
    input.promises_yield == true
    msg := "MICA_VIOLATION: Token promises yield — not a utility token"
}

violations[msg] if {
    input.promises_profit == true
    msg := "MICA_VIOLATION: Token promises profit — fails utility classification"
}

violations[msg] if {
    not has_compliant_white_paper
    msg := "MICA_WHITE_PAPER: White paper does not meet Art. 6 requirements"
}

violations[msg] if {
    input.marketing.contains_yield_claims == true
    msg := "MICA_MARKETING: Marketing contains yield claims — Art. 7 violation"
}

violations[msg] if {
    input.withdrawal_period_days < 14
    msg := sprintf("MICA_WITHDRAWAL: Withdrawal period %d days < required 14 days", [input.withdrawal_period_days])
}

# Market abuse flag (Art. 76)
market_abuse_suspected if {
    input.unusual_trading_volume == true
}

market_abuse_suspected if {
    input.price_manipulation_indicators == true
}
