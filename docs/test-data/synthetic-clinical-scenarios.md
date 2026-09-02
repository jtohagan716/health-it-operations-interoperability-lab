# Synthetic Clinical Scenario Catalog

Issue: #31

## Purpose

The scenario catalog defines why records exist and which observable behaviors they must support. It prevents the generator from producing disconnected random data.

## Golden cohort

Ten golden patients have stable identifiers `SYNTHMRN000001` through `SYNTHMRN000010`. Their exact dates and values will be stored in generated manifests and asserted by regression tests.

| Patient | Scenario | Required history and test purpose |
|---|---|---|
| 001 | Preventive adult | Annual encounters, normal vitals, routine screening laboratory history |
| 002 | Hypertension | Repeated elevated blood pressure, diagnosis, medication start, subsequent improvement |
| 003 | Prediabetes | Glucose and HbA1c trend, normal/abnormal interpretation boundaries |
| 004 | Diabetes | Active diagnosis, medication history, serial glucose/HbA1c results |
| 005 | Respiratory | Cough encounter, chest radiology order/report, short-term medication |
| 006 | Cardiovascular | Multiple providers, medication reconciliation, laboratory and imaging history |
| 007 | Pediatric preventive | Age-appropriate encounters, growth vitals, and immunizations |
| 008 | Older adult | Multiple chronic problems, polypharmacy, allergy and medication reconciliation |
| 009 | Corrected result | Preliminary, final, and corrected laboratory-result lifecycle |
| 010 | Identity edge case | Demographic update, exact replay, and controlled conflicting identifier test |

## Historical encounter scenarios

Every patient receives exactly three completed historical encounters. Encounter types are assigned deterministically from the profile while preserving cohort needs.

Required encounter patterns include:

- preventive outpatient visit;
- chronic-condition follow-up;
- urgent or emergency visit;
- inpatient admission/discharge history for a bounded cohort;
- telehealth follow-up;
- pediatric well visit;
- medication reconciliation;
- laboratory-only or imaging-associated encounter where supported.

Dependent records must occur inside or after their originating encounter as clinically appropriate.

## Active ADT scenarios

Active transactions are not part of the initial baseline count. They execute against known patients after baseline reconciliation.

| Scenario | Message | Expected behavior |
|---|---|---|
| New outpatient registration | `ADT^A04` | AA, audit persisted, patient delivered once, downstream identity reconciled |
| Demographic update | `ADT^A08` | Existing patient updated without duplicate creation |
| Inpatient admission | `ADT^A01` | New encounter associated with correct patient/provider/location |
| Transfer | `ADT^A02` | Existing active encounter location changes |
| Discharge | `ADT^A03` | Existing encounter closes with correct discharge time/status |
| Exact replay | Same message identity and payload | Accepted/classified as exact replay; no duplicate clinical record |
| Conflicting reuse | Same control identity, altered payload | Rejected and retained as integrity evidence |
| Unknown patient update | A08 for unknown MRN | Rejected or quarantined according to approved policy |
| Patient merge | `ADT^A40` | Deferred until merge safeguards and reset strategy are validated |

## Laboratory scenarios

- normal final glucose;
- abnormal final glucose;
- critical high glucose;
- preliminary-to-final progression;
- corrected result replacing the intended prior result;
- cancellation;
- unknown order number;
- patient/order mismatch;
- invalid value or unit;
- exact replay versus legitimate clinical correction;
- downstream OpenEMR unavailability and controlled recovery.

## Radiology scenarios

- imaging order with deterministic accession number;
- final narrative report correlated to patient/order/accession;
- DICOM study correlated through Study Instance UID;
- unauthorized or unknown AE behavior;
- downstream destination unavailable;
- autorouting recovery;
- patient/accession mismatch;
- corrected report;
- duplicate order/report handling.

## Medication scenarios

- active chronic medication;
- completed short-term medication;
- medication discontinuation;
- dose/unit/route/frequency reconciliation;
- documented allergy conflict as a deliberate negative test;
- medication attached to wrong patient as a blocked test case;
- database-to-FHIR semantic reconciliation;
- missing or incompatible dispense unit.

## Vitals and observation scenarios

- normal adult panel;
- elevated blood pressure;
- improving blood-pressure trend after medication start;
- pediatric growth trend;
- oxygen saturation during respiratory encounter;
- calculated BMI consistency;
- observation timestamp outside encounter as a negative case;
- invalid unit as a negative case.

## Identity and data-quality scenarios

- duplicate MRN within the same assigning authority;
- same local identifier under different assigning authorities;
- demographic update without logical identity change;
- conflicting date of birth;
- missing legal name type;
- unknown administrative-sex code;
- future date of birth;
- orphan encounter;
- orphan result;
- provider/facility relationship mismatch;
- chronology violation.

## Operational scenarios

Each major domain eventually demonstrates:

1. Normal execution.
2. Dependency unavailable.
3. Validation rejection.
4. Queue or audit visibility.
5. Safe retry or controlled replay.
6. Downstream persistence verification.
7. Evidence sufficient for escalation.

## Scenario completion rule

A scenario is not complete merely because a message received an AA acknowledgment. Completion requires the expected audit classification, downstream state, field-level reconciliation, and absence of unintended duplicate records.
