package policies.bias_fairness

# Policy: POL-BIAS
# Name: Bias & Fairness for AI/ML

violation[msg] {
    input.module_type == "ai_ml"
    input.bias_testing_enabled == false
    msg := "POL-BIAS: AI/ML modules must have bias testing"
}

violation[msg] {
    input.module_type == "ai_ml"
    input.fairness_metrics.demographic_parity == false
    msg := "POL-BIAS: Demographic parity metric required"
}

violation[msg] {
    input.module_type == "ai_ml"
    input.fairness_metrics.equal_opportunity == false
    msg := "POL-BIAS: Equal opportunity metric required"
}

compliant {
    input.module_type != "ai_ml"
}

compliant {
    count(violation) == 0
}
