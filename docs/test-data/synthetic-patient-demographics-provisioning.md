# Synthetic Patient-Demographics Provisioning

Issue: #31

## Purpose

Provision 100 deterministic, entirely synthetic patients as the identity foundation for later encounters, vitals, diagnoses, medications, allergies, immunizations, laboratory history, radiology history, and active HL7 scenarios.

## OpenEMR 8.2.0 implementation decision

OpenEMR's `PatientService::insert()` is the supported application service for database patient creation. It validates required fields, allocates the internal PID and UUID, sets registration timestamps, and emits patient-created events.

The OpenEMR FHIR Patient service supports read and write operations, but its source currently states that inbound race and ethnicity mapping is not correct. This fixture therefore:

- calls `PatientService::insert()` inside the OpenEMR container;
- uses stable `SYNTHMRN000001` through `SYNTHMRN000100` public identifiers;
- resolves primary providers from deterministic `synprov0001` through `synprov0025` usernames;
- stores OpenEMR-native list option IDs for sex, race, ethnicity, language, and marital status;
- uses database verification for exact persistence and FHIR reads for downstream representation testing.

OpenEMR has no patient-level `facility_id` field. The primary provider supplies the organizational relationship, while later encounters will carry the actual facility and location history.

## Population properties

- 100 unique MRNs and logical keys
- 10 golden patients, one from each clinical cohort
- 10 patients per cohort
- 4 patients assigned to each of the 25 synthetic providers
- pediatric, adult, and older-adult birth dates
- balanced Male/Female administrative-sex values
- controlled race, ethnicity, language, and marital-status values
- five deliberate near-duplicate identity pairs with different MRNs
- reserved `716-555-0100` through `716-555-0199` telephone values
- unique `example.invalid` email addresses
- no SSNs, driver-license numbers, portal credentials, or real identifiers

## Commands

Dry run:

```powershell
python -m scripts.synthetic.patient_demographics
```

One-patient probe:

```powershell
python -m scripts.synthetic.patient_demographics `
    --probe `
    --commit `
    --environment local-lab `
    --confirm-patient-count 1
```

Probe verification:

```powershell
python -m scripts.synthetic.patient_demographics --probe --verify
```

Full commit after probe approval:

```powershell
python -m scripts.synthetic.patient_demographics `
    --commit `
    --environment local-lab `
    --confirm-patient-count 100
```

Full verification:

```powershell
python -m scripts.synthetic.patient_demographics --verify
```

## Safety and reconciliation

Dry run is the default. Writes require the exact local environment and exact operation count. The OpenEMR receiver accepts only one probe patient or the complete 100-patient manifest.

Patients are located by exact `pubpid`. Zero matches permits creation through `PatientService`; one exact match returns `EXISTING`; multiple matches or any demographic conflict fails closed. All writes run in one transaction, and postconditions are verified before commit.

The generated PHP program and its payload are streamed to the container over standard input. This avoids Windows command-line and environment-variable size limits for the 100-patient manifest.

## Known OpenEMR FHIR relationship limitation

Database-to-FHIR reconciliation identified a reproducible OpenEMR 8.2.0 behavior affecting the assigned-provider relationship.

The synthetic patient record correctly stores `patient_data.providerID`, and the referenced provider is active, authorized, and has a valid UUID. Both a direct FHIR Patient read by UUID and a Patient search by MRN return the correct patient identity and demographics but omit `Patient.generalPractitioner`.

Source inspection showed that `PatientService::search()` selects the joined provider UUID. During patient-result hydration, however, the record is reduced to the fields returned by `PatientService::getFields()`, which does not preserve the joined `provider_uuid`. `FhirPatientService::parseOpenEMRGeneralPractitioner()` therefore receives no provider UUID and cannot add the Practitioner reference.

This is treated as an observed OpenEMR FHIR representation limitation rather than a synthetic-data provisioning failure because:

- the patient-to-provider relationship is correctly persisted in OpenEMR
- the provider exists with a valid UUID
- core FHIR Patient identity and demographic fields reconcile successfully
- the omission is reproducible through both direct-read and identifier-search endpoints

The finding is retained as future regression and potential upstream defect evidence.

## Scope boundary

This increment creates patient demographics and primary-provider assignments only. It does not create portal accounts, encounters, clinical observations, diagnoses, orders, or results. Active ADT messages remain a later delivery phase so baseline provisioning and live interface traffic can be tested independently.
