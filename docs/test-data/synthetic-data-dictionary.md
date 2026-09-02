# Synthetic Population Data Dictionary

Issue: #31

## Conventions

- All dates use ISO 8601 in manifests and the correct target format at each interface boundary.
- All identifiers are strings even when their suffix is numeric.
- `source_system` is `SYNTHETIC_POPULATION_V1` unless a scenario explicitly represents inbound HL7.
- `run_id`, `profile_version`, and `seed` provide provenance for every generated record.
- Values listed as required must be present before a record can be committed.

## Provenance fields

| Field | Required | Definition |
|---|---|---|
| `run_id` | Yes | Unique execution ID beginning with `SYNTH-` |
| `profile_version` | Yes | Version of `population-profile.json` |
| `seed` | Yes | Deterministic integer generation seed |
| `source_system` | Yes | Synthetic source identifier |
| `generated_at` | Yes | UTC manifest generation timestamp |
| `logical_key` | Yes | Stable cross-run identity for idempotent reconciliation |

## Organization

| Field | Required | Rule |
|---|---|---|
| `organization_id` | Yes | `SYNORG01` |
| `name` | Yes | Clearly fictional organization name |
| `active` | Yes | Boolean |
| `address` | Yes | Synthetic address |

## Facility and location

| Field | Required | Rule |
|---|---|---|
| `facility_id` | Yes | `SYNFAC01`–`SYNFAC03` |
| `facility_name` | Yes | Fictional name |
| `department_id` | Yes | Stable synthetic code |
| `department_name` | Yes | Clinical service name |
| `organization_id` | Yes | Resolves to the synthetic organization |
| `service_type` | Yes | Primary care, emergency, inpatient, laboratory, radiology, pharmacy, pediatrics, or specialty |

## Provider

| Field | Required | Rule |
|---|---|---|
| `provider_id` | Yes | `SYNPROV0001`–`SYNPROV0025` |
| `family_name` | Yes | Conspicuously synthetic |
| `given_name` | Yes | Conspicuously synthetic |
| `specialty_code` | Yes | Controlled profile value |
| `facility_ids` | Yes | One or more existing synthetic facilities |
| `active` | Yes | Boolean |
| `synthetic_identifier` | Yes | Must not be represented as a real NPI |
| `email` | Yes | Uses `example.invalid` |

## Patient

| Field | Required | HL7/FHIR relation | Rule |
|---|---|---|---|
| `patient_id` | Yes | PID-3 / Patient.identifier | `SYNTHMRN` plus six digits |
| `assigning_authority` | Yes | PID-3.4 | `INTEROPLAB` |
| `identifier_type` | Yes | PID-3.5 | `MR` |
| `family_name` | Yes | PID-5.1 | Synthetic namespace |
| `given_name` | Yes | PID-5.2 | Synthetic namespace |
| `name_type` | Yes | PID-5.7 | `L` |
| `birth_date` | Yes | PID-7 / Patient.birthDate | Valid date preceding all encounters |
| `administrative_sex` | Yes | PID-8 / Patient.gender | Controlled value `M`, `F`, `O`, or `U` |
| `address` | Yes | PID-11 / Patient.address | Synthetic address |
| `phone` | Yes | PID-13 / Patient.telecom | Reserved fictional number |
| `email` | Yes | Patient.telecom | `example.invalid` |
| `golden_patient` | Yes | Test metadata | Boolean |
| `cohort_codes` | Yes | Test metadata | Zero or more controlled cohort codes |

## Encounter

| Field | Required | HL7/FHIR relation | Rule |
|---|---|---|---|
| `encounter_id` | Yes | PV1-19 / Encounter.identifier | Stable unique synthetic ID |
| `patient_id` | Yes | PID-3 / Encounter.subject | Existing patient |
| `provider_id` | Yes | PV1-7 / Encounter.participant | Existing provider |
| `facility_id` | Yes | PV1-3.4 / Encounter.location | Existing facility |
| `department_id` | Yes | PV1-3.1 | Existing department |
| `encounter_type` | Yes | PV1-2 | Outpatient, emergency, inpatient, telehealth, or preventive |
| `start_at` | Yes | PV1-44 | Before or equal to `end_at` |
| `end_at` | Conditional | PV1-45 | Required for completed historical encounter |
| `status` | Yes | Encounter.status | `finished` for baseline history |

## Vital-sign panel

Each panel belongs to one encounter and contains clinically coherent observations selected from body temperature, pulse, respiratory rate, blood pressure, oxygen saturation, height, weight, and BMI.

| Field | Required | Rule |
|---|---|---|
| `panel_id` | Yes | Stable synthetic ID |
| `encounter_id` | Yes | Existing encounter |
| `observed_at` | Yes | Within encounter period |
| `code` | Yes | Controlled LOINC code where applicable |
| `value` | Yes | Numeric value within configured scenario bounds |
| `unit` | Yes | UCUM-aligned unit |
| `interpretation` | Conditional | Consistent with value and reference range |

## Diagnosis/problem

| Field | Required | Rule |
|---|---|---|
| `diagnosis_id` | Yes | Stable synthetic ID |
| `patient_id` | Yes | Existing patient |
| `encounter_id` | Conditional | Existing encounter when encounter-associated |
| `code_system` | Yes | Declared coding system |
| `code` | Yes | Profile-approved code |
| `display` | Yes | Expected display text |
| `onset_date` | Yes | Not later than resolution date |
| `status` | Yes | Active, resolved, or historical |

## Medication

| Field | Required | Rule |
|---|---|---|
| `medication_id` | Yes | Stable synthetic ID |
| `patient_id` | Yes | Existing patient |
| `encounter_id` | Conditional | Existing encounter when ordered during visit |
| `medication_code` | Yes | Profile-approved RxNorm or declared local code |
| `dose_value` | Yes | Positive numeric value |
| `dose_unit` | Yes | Compatible with medication |
| `route_code` | Yes | Profile-approved route |
| `frequency` | Yes | Controlled frequency |
| `start_date` | Yes | Chronologically valid |
| `end_date` | Conditional | Required for discontinued historical medication |
| `status` | Yes | Active, completed, stopped, or historical |

## Allergy/intolerance

| Field | Required | Rule |
|---|---|---|
| `allergy_id` | Yes | Stable synthetic ID |
| `patient_id` | Yes | Existing patient |
| `substance_code` | Yes | Declared coding system and code |
| `reaction` | Conditional | Compatible test description |
| `severity` | Conditional | Mild, moderate, or severe |
| `status` | Yes | Active, inactive, or resolved |
| `verification_status` | Yes | Confirmed, unconfirmed, or entered-in-error |

## Immunization

| Field | Required | Rule |
|---|---|---|
| `immunization_id` | Yes | Stable synthetic ID |
| `patient_id` | Yes | Existing patient |
| `encounter_id` | Conditional | Existing encounter when administered during visit |
| `vaccine_code` | Yes | Profile-approved CVX or declared local code |
| `administered_at` | Yes | After birth date and before manifest generation |
| `status` | Yes | Completed or not-done |
| `lot_number` | Conditional | Synthetic namespace only |

## Laboratory order/result

| Field | Required | HL7 relation | Rule |
|---|---|---|---|
| `lab_order_id` | Yes | ORC-2/OBR-2 | Stable placer order number |
| `patient_id` | Yes | PID-3 | Existing patient |
| `encounter_id` | Yes | PV1-19 | Existing encounter |
| `ordering_provider_id` | Yes | ORC-12/OBR-16 | Existing provider |
| `test_code` | Yes | OBR-4/OBX-3 | Profile-approved LOINC code |
| `ordered_at` | Yes | ORC/OBR timestamp | Chronologically valid |
| `result_value` | Yes | OBX-5 | Type-compatible value |
| `result_unit` | Conditional | OBX-6 | Compatible UCUM unit |
| `reference_range` | Conditional | OBX-7 | Compatible with patient/test scenario |
| `abnormal_flag` | Conditional | OBX-8 | Consistent with value/range |
| `result_status` | Yes | OBR-25/OBX-11 | Preliminary, final, corrected, or cancelled scenario |

## Radiology order/report

| Field | Required | Rule |
|---|---|---|
| `radiology_order_id` | Yes | Stable placer order number |
| `accession_number` | Yes | Unique synthetic accession |
| `patient_id` | Yes | Existing patient |
| `encounter_id` | Yes | Existing encounter |
| `ordering_provider_id` | Yes | Existing provider |
| `procedure_code` | Yes | Profile-approved code |
| `ordered_at` | Yes | Before report time |
| `report_status` | Yes | Preliminary, final, corrected, or cancelled |
| `report_text` | Yes | Synthetic controlled template, never copied clinical text |
| `study_instance_uid` | Conditional | Deterministic test UID when paired with DICOM |

## Manifest counts

The manifest records expected, attempted, succeeded, failed, and reconciled counts for every entity type. A manifest is complete only when each expected count has an explicit reconciliation outcome.
