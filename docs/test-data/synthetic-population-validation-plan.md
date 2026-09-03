# Synthetic Population Validation Plan

Issue: #31

## Objective

Demonstrate that the generated synthetic population is safe, deterministic, internally coherent, correctly persisted, and suitable as a repeatable interoperability test baseline.

## Validation levels

### 1. Static contract validation

- Required documentation exists.
- Profile and schema files are valid JSON.
- Profile version and seed are explicit.
- Counts equal the approved issue #31 baseline.
- Safety limits are not lower than targets and are not unbounded.
- Identifier templates use synthetic namespaces.
- Approved local endpoints use localhost only.

### 2. Generator unit validation

- Same seed produces identical logical records.
- Different run timestamps do not alter stable identifiers.
- Patient and provider identifiers are unique.
- Dates and relationships are valid.
- Clinical values comply with scenario constraints.
- Generated HL7 escapes delimiters correctly.
- Manifest hashes change when meaningful payload content changes.

### 3. Dry-run validation

- No OpenEMR, Mirth, PostgreSQL, or MariaDB state changes.
- Exact expected counts are reported.
- Every record has provenance and a logical key.
- Safety confirmation requirements are displayed.
- Generated manifests validate against the schema.

### 4. Master-data persistence validation

- One organization, three facilities, eight departments, and 25 providers exist.
- Provider identifiers are unique and synthetic.
- Provider-to-facility and specialty relationships resolve.
- Repeating the load produces no logical duplicates.

### 5. Patient-history persistence validation

- Exactly 100 population-scoped patients exist.
- Every patient has three historical encounters.
- Every encounter resolves to patient, provider, facility, and department.
- Required dependent-record counts match the manifest.
- No patient has an impossible chronology.
- Golden-patient values match exact expectations.
- Every historical encounter has one independently correlated intake vital-sign panel.
- Additional repeat measurement events remain distinct from the encounter-level intake baseline.

### 6. Interface validation

- MLLP transport returns a correlated acknowledgment.
- Mirth records message identity, patient identity, payload hash, classification, and processing outcome.
- Invalid messages are quarantined with actionable reasons.
- Exact replay does not duplicate downstream clinical state.
- Conflicting identity reuse is rejected.
- OpenEMR delivery is verified independently of the acknowledgment.

### 7. Reconciliation validation

Compare the manifest to:

- Mirth/PostgreSQL audit state;
- OpenEMR/MariaDB persistence;
- OpenEMR FHIR/REST representation where supported;
- selected OpenEMR clinical-interface views;
- Orthanc for DICOM-associated radiology scenarios.

For each domain report expected, actual, missing, duplicate, mismatched, and unexpected counts.

### 8. Recovery validation

- Dependency outage does not produce false success.
- Failed work remains diagnosable.
- Approved replay occurs only after preconditions pass.
- A repeated baseline load remains idempotent.
- Reset/rebuild restores a known clean state.

## Risk-based priorities

| Priority | Risk | Required control |
|---|---|---|
| Critical | Execution against a non-local environment | Hard environment and endpoint refusal |
| Critical | Real PHI or real provider identifiers | Synthetic-only source review and namespace tests |
| Critical | Patient/order/result misassociation | Cross-domain identity reconciliation |
| Critical | Duplicate clinical records | Stable logical keys and idempotency tests |
| High | AA acknowledgment mistaken for downstream success | Independent persistence postconditions |
| High | Orphan clinical records | Referential-integrity reconciliation |
| High | Chronologically invalid history | Date and lifecycle validation |
| Medium | Unrealistic but structurally valid clinical data | Scenario-coherence tests |
| Medium | Poor operational evidence | Structured run and mismatch reporting |

## Test execution groups

Suggested pytest markers for later implementation:

- `contract`: profile, schema, and documentation tests;
- `unit`: deterministic generator behavior;
- `integration`: local persistence adapters;
- `live`: running Mirth/OpenEMR dependencies;
- `reconciliation`: cross-system postconditions;
- `destructive`: bounded reset operations requiring explicit opt-in;
- `performance`: rate and volume tests excluded from normal regression.

## Entry criteria for the first committed load

- Contract PR merged.
- Provisioning path for each initial entity type documented.
- Unit and dry-run tests passing.
- Both OpenEMR services healthy.
- Backup/reset method verified.
- Operator confirms 100-patient target and local-lab environment.
- No unresolved critical safety defect.

## Exit criteria for issue #31

- All approved baseline entities loaded.
- Manifest validation passes.
- Reconciliation reports zero unexpected discrepancies.
- Same-seed rerun is idempotent.
- Golden cohort verified at database and selected UI/API layers.
- Negative and recovery cases retain complete evidence.
- Runbook permits another operator to reproduce and validate the population.

## Required evidence

- profile and manifest files;
- test execution output;
- count and relationship reconciliation report;
- idempotency rerun evidence;
- selected OpenEMR screenshots;
- Mirth audit/ACK evidence for active scenarios;
- one documented failure and recovery case;
- final test completion summary.
