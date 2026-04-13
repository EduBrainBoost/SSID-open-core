# Governance Proposals Index

This directory contains the canonical proposal registry and ballot records
for SSID governance decisions.

## Structure

```
proposals/
  registry.yaml          # Master registry of all proposals
  ballots/               # Individual ballot records (JSON)
    <proposal_id>.json   # Ballot with quorum, threshold, status, evidence
```

## Proposal Lifecycle

1. **Draft** — Proposal created, registered in `registry.yaml`
2. **Active** — Voting period open, ballot record created in `ballots/`
3. **Passed / Rejected** — Quorum and threshold evaluated
4. **Enacted** — Parameter change applied after timelock

## Validation

All proposals are validated by `23_compliance/validators/proposal_validator.py`
which enforces:

- Required fields in registry entries
- Quorum and threshold rules in ballot records
- Schema conformance (YAML registry, JSON ballots)

## Related

- `07_governance_legal/lock_fee_params_v5_4_3.yaml` — Fee parameters governed by proposals
- `23_compliance/validators/proposal_validator.py` — Schema and quorum validator
- `11_test_simulation/tests_compliance/test_proposal_validator.py` — Validator tests
