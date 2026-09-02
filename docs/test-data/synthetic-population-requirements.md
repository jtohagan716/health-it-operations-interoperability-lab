# Synthetic Clinical Population Requirements

Issue: #31 — Build deterministic synthetic clinical population for interoperability testing

## Purpose

Create a reproducible local test population that supports healthcare interoperability, functional, integration, IV&V, database-reconciliation, operational-recovery, and performance testing across Mirth Connect and OpenEMR.

The initial release provisions 100 synthetic patients, 25 synthetic providers, organizational master data, and longitudinal clinical history. A later delivery phase generates active HL7 traffic against this known baseline.

## Baseline environment

- OpenEMR 8.2.0
- MariaDB 11.8.8
- Mirth Connect 4.5.2
- PostgreSQL interoperability audit store
- Local Docker-based laboratory only

Container image digests and runtime health remain authoritative in the repository compose files and validation evidence.

## Core principles

1. **Synthetic only:** no production-derived records, PHI, real NPIs, real insurance identifiers, or copied clinical narratives.
2. **Deterministic:** the same profile version and seed produce the same identifiers, relationships, and expected counts.
3. **Idempotent:** rerunning a load reconciles existing synthetic records instead of creating uncontrolled duplicates.
4. **Environment guarded:** mutating commands refuse unknown or non-local targets.
5. **Dry-run first:** every mutating workflow supports a non-writing preview.
6. **Explicit confirmation:** the requested patient count and target environment must be confirmed before commit.
7. **Auditable:** each run emits a manifest containing the seed, profile version, identifiers, counts, timestamps, and outcomes.
8. **Reconciled:** success requires downstream persistence verification; an HL7 AA acknowledgment alone is not proof of OpenEMR persistence.
9. **Resettable:** synthetic data can be removed or the laboratory can be rebuilt using documented, bounded procedures.
10. **Clinically coherent:** dates, diagnoses, observations, medications, laboratory results, and radiology history must remain internally consistent.

## Initial population targets

| Domain | Exact target |
|---|---:|
| Organizations | 1 |
| Facilities | 3 |
| Departments/locations | 8 |
| Providers | 25 |
| Patients | 100 |
| Historical encounters | 300 |
| Vital-sign panels | 600 |
| Encounter diagnoses | 400 |
| Medication records | 200 |
| Allergy/intolerance records | 100 |
| Immunization records | 200 |
| Laboratory orders | 450 |
| Laboratory results | 500 |
| Radiology orders | 100 |
| Radiology reports | 100 |
| Golden patients | 10 |

These targets describe the generated baseline manifest. Active HL7 scenario traffic is tracked separately so repeated runtime validation does not alter the expected baseline silently.

## Population composition

The population must include adult, pediatric, and older-adult patients. Clinical cohorts may overlap and include preventive care, hypertension, diabetes/prediabetes, respiratory disease, cardiovascular disease, pediatric preventive care, older-adult polypharmacy, and deliberate identity or lifecycle edge cases.

Ten golden patients have explicitly defined longitudinal histories and exact assertions. The remaining 90 patients provide deterministic variation and volume.

## Identifier namespaces

All generated identifiers use reserved synthetic namespaces:

- Population run: `SYNTH-YYYYMMDD-NNN`
- Patient MRN: `SYNTHMRN000001` through `SYNTHMRN000100`
- Provider ID: `SYNPROV0001` through `SYNPROV0025`
- Encounter ID: `SYNENC000001` and higher
- Facility code: `SYNFAC01` through `SYNFAC03`
- Message control ID: `SYNTH-<MESSAGE>-<RUN>-<SEQUENCE>`

Generated people use conspicuously synthetic names and the `example.invalid` email domain. Telephone values use reserved fictional ranges. Provider records must not use plausible real NPIs.

## Ingestion boundaries

Data must use the most appropriate supported boundary:

- Facilities, locations, and providers: supported OpenEMR configuration/API or a guarded OpenEMR-side provisioner.
- Historical patients and encounters: supported OpenEMR REST/FHIR interfaces when semantics are sufficient; otherwise a guarded OpenEMR-side fixture adapter.
- Active ADT traffic: MLLP through the existing Mirth ADT channel, followed by an independently verified OpenEMR delivery boundary.
- Laboratory and radiology transactions: existing ORM/ORU Mirth paths and guarded downstream delivery where implemented.
- Medication, allergy, immunization, and vitals: supported OpenEMR REST/FHIR interfaces or a documented guarded adapter.

Direct MariaDB writes are not the default. Any required database fixture adapter must run inside the local environment, call OpenEMR-supported data functions where available, declare every affected table, execute transactionally, and verify postconditions.

## Functional requirements

The implementation shall:

- generate the exact configured entity counts;
- preserve stable identifiers across reruns;
- create three historical encounters per patient;
- associate every encounter with one facility, location, and provider;
- enforce chronological ordering of encounters and dependent observations;
- create clinically consistent vital signs and laboratory ranges;
- associate medication history with relevant diagnoses where applicable;
- preserve order/report/result relationships;
- distinguish exact replay, conflicting identity reuse, and legitimate clinical correction;
- create a machine-readable manifest before commit;
- record actual load and reconciliation outcomes after commit;
- fail closed when safety prerequisites are absent;
- report mismatches without silently repairing them.

## Safety requirements

A mutating command must refuse execution unless all of the following are true:

- environment equals `local-lab`;
- OpenEMR base URL is an approved localhost URL;
- the profile declares `synthetic_only: true`;
- the operator supplies `--commit`;
- the operator supplies the exact `--confirm-patient-count 100` value;
- the seed is explicit;
- the run identifier begins with `SYNTH-`;
- the requested population does not exceed the configured safety maximum;
- dependency health checks pass.

Logs and manifests must not contain credentials, access tokens, or database passwords.

## Acceptance criteria

The baseline population is accepted only when:

1. Contract tests pass.
2. Dry-run manifest counts match the profile.
3. The committed run produces no unexpected errors.
4. OpenEMR contains exactly 100 population-scoped patients and 25 population-scoped providers.
5. Every generated relationship resolves to an existing parent record.
6. Manifest-to-database reconciliation has zero unexpected missing, duplicate, or mismatched records.
7. A repeated load with the same seed creates no additional logical patients or providers.
8. A conflicting identifier reuse is rejected and retained as evidence.
9. Selected golden patients are verified in the OpenEMR clinical interface.
10. Reset/rebuild instructions are validated in the local environment.

## Out of scope for the contract PR

- Production deployment
- Real patient or provider data
- Bulk performance execution
- Implementation of every OpenEMR clinical domain adapter
- Active ADT delivery into OpenEMR
- Corrected-result lifecycle implementation

Those capabilities are delivered through subsequent issue #31 pull requests after this contract is approved.
