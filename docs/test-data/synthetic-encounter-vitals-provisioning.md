# Synthetic encounter and vitals provisioning

This issue #31 increment adds one deterministic historical outpatient encounter and one vitals set per synthetic patient. It uses OpenEMR's native `EncounterService` rather than direct table insertion.

## Safety controls

- local synthetic environment only
- dry run by default
- one-patient probe mode
- exact commit-count confirmation
- synthetic patient marker precondition
- assigned provider and facility resolution
- stable external identifiers
- basic numeric and clinical-range validation
- database transaction plus explicit compensating cleanup for service/event side effects
- postcondition verification before commit
- idempotent replay

## Commands

Dry run:

```powershell
python -m scripts.synthetic.encounter_vitals
```

One-patient probe:

```powershell
python -m scripts.synthetic.encounter_vitals --probe --commit --environment local-lab --confirm-patient-count 1
```

Verify the probe:

```powershell
python -m scripts.synthetic.encounter_vitals --probe --verify
```

Full population (only after probe validation):

```powershell
python -m scripts.synthetic.encounter_vitals --commit --environment local-lab --confirm-patient-count 100
```

Full verification:

```powershell
python -m scripts.synthetic.encounter_vitals --verify
```

## Persistence relationships

Each logical record must produce a `form_encounter` row, a `newpatient` row in `forms`, a `form_vitals` row, and a `vitals` row in `forms`. The receiver verifies all four records and their patient/encounter relationships before commit. OpenEMR's native vitals field whitelist does not preserve `form_vitals.external_id`, so the stable vitals key is retained in the note and the authoritative correlation follows the encounter-to-forms relationship.

OpenEMR service and event-subscriber writes were observed to persist across an attempted outer rollback during the initial probe. The receiver therefore tracks exact created identifiers and performs reverse-order compensating cleanup if a later postcondition fails.

OpenEMR 8.2.0's `EncounterService::insertVital()` obtains its second return value with a lookup based only on `forms.form_id`. Because record IDs can overlap across different OpenEMR form tables, that returned form-registration ID is retained only as diagnostic evidence. The receiver establishes the authoritative registration with the full relationship: patient, encounter, `formdir='vitals'`, and the verified vitals record ID. Verification and compensating cleanup both use that qualified relationship.

## FHIR scope

Database and UI relationships are authoritative for this increment. FHIR Encounter and vital Observation representation will be reconciled after the probe. Synthetic providers intentionally have no fabricated NPI; OpenEMR 8.2.0 encounter searches restrict provider UUID joins to providers with nonblank NPIs, so provider participation may be omitted from FHIR even when the database relationship is correct.
