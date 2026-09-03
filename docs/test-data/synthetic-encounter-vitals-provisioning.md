# Synthetic encounter and vitals provisioning

This issue #31 increment provisions three deterministic historical outpatient encounters and one intake vital-sign panel per encounter for each of the 100 synthetic patients. It expands the previously validated one-encounter baseline without replacing or changing the original records. OpenEMR's native `EncounterService` performs the clinical writes rather than direct table insertion.

## Delivered population

| Entity | Delivered count |
| --- | ---: |
| Synthetic patients | 100 |
| Patient cohorts | 10 |
| Patients per cohort | 10 |
| Historical encounters per patient | 3 |
| Historical encounters | 300 |
| Intake vital-sign panels | 300 |
| Encounter form registrations | 300 |
| Unique encounter identifiers | 300 |
| Unique vital identifiers | 300 |

The history covers January through December 2025. Every cohort contributes 30 encounters, preserving balanced deterministic coverage while producing repeated clinical activity for each patient.

## Longitudinal model

Each patient's visit schedule is derived from the same stable base date and patient sequence:

| Visit | Offset | Purpose | Compatibility behavior |
| --- | ---: | --- | --- |
| `01` | 0 days | Original cohort-specific visit | Preserved unchanged from the earlier baseline |
| `02` | 120 days | Interval reassessment | Adds a small deterministic vital-value variation |
| `03` | 240 days | Longitudinal review | Adds a second deterministic variation |

Encounter and vital identifiers retain both the patient sequence and visit sequence. Examples include `SYNENC00000101`, `SYNENC00000102`, and `SYNENC00000103`, with corresponding `SYNVIT` identifiers.

The visit-specific adjustments prevent repeated encounters from containing copied measurements while keeping values within the previously validated cohort templates. They are deterministic scenario values designed for interoperability, lifecycle, reconciliation, and reliability testing. They are not represented as an epidemiological sample or a model of national disease prevalence.

## Safety controls

- local synthetic environment only
- dry run by default
- one-patient probe mode
- exact patient-count confirmation for committed runs
- synthetic patient marker precondition
- assigned provider and facility resolution
- stable encounter and vital identifiers
- unique record-cardinality validation
- basic numeric and clinical-range validation
- encounter and vital timestamp verification
- database transaction plus explicit compensating cleanup for service/event side effects
- postcondition verification before commit
- independently queryable persistence relationships
- idempotent replay

The commit confirmation remains `--confirm-patient-count 100`. That value confirms the number of patients placed in scope; the payload separately declares and validates the expected 300 clinical records.

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

Full population, only after probe validation:

```powershell
python -m scripts.synthetic.encounter_vitals --commit --environment local-lab --confirm-patient-count 100
```

Full verification:

```powershell
python -m scripts.synthetic.encounter_vitals --verify
```

## Persistence relationships

Each logical encounter/vitals record produces and verifies:

- one `form_encounter` row;
- one `newpatient` registration in `forms`;
- one `form_vitals` row; and
- one `vitals` registration in `forms`.

The receiver verifies the patient, encounter, provider, facility, category, class, reason, timestamps, vital values, BMI, and both native form relationships before reporting a committed record as successful.

OpenEMR's native vitals field whitelist does not preserve `form_vitals.external_id`. The stable vital key is therefore retained in the note, and authoritative correlation follows the qualified patient-to-encounter-to-form relationship.

OpenEMR service and event-subscriber writes were observed to persist across an attempted outer rollback during the original probe. The receiver consequently tracks exact identifiers created by the current execution and performs reverse-order compensating cleanup if a later postcondition fails.

OpenEMR 8.2.0's `EncounterService::insertVital()` obtains its second return value with a lookup based only on `forms.form_id`. IDs can overlap across OpenEMR form tables, so that returned registration ID is retained only as diagnostic evidence. The receiver establishes the authoritative registration using the complete relationship: patient, encounter, `formdir='vitals'`, and the verified vital record ID. Verification and compensating cleanup both use that qualified relationship.

## Validation evidence

The expansion was executed against a live local OpenEMR population that initially contained 100 synthetic encounters and 100 corresponding vital panels.

The pre-write dry run reported:

- 100 expected patients;
- 300 expected encounter/vitals records;
- 100 existing records; and
- 200 records that would be created.

The one-patient probe resolved the original visit and created only visits `02` and `03`. Independent verification resolved all three visits, and direct MariaDB reconciliation confirmed their chronological dates, cohort-specific reasons, provider and facility relationships, adjusted vital values, calculated BMI values, and stable identifiers.

After the probe, the full dry run reported 102 existing records and 198 records that would be created. The committed population then verified all 300 records.

Independent database reconciliation established:

- exactly 300 synthetic encounters across 100 patients;
- exactly three encounters for every patient;
- exactly 30 encounters in each of the ten cohorts;
- exactly 300 encounter form registrations;
- exactly 300 uniquely keyed vital panels;
- zero duplicate encounter identifiers;
- zero chronology violations; and
- zero orphaned patient, provider, or facility relationships.

A full committed replay resolved all 300 records as existing and created zero additional records. The focused and cross-domain synthetic-data regression suites completed with 92 passing tests.

## Performance observation

The full 300-record idempotent replay completed in 51.79 seconds on the local development environment. This is retained as an operational observation, not a formal performance benchmark: the run did not control warm-up state, competing host workload, container resource allocation, or repeated-sample variance.

Formal performance work is intentionally separate. A future increment can establish reproducible database, API, application, and batch baselines; inspect execution plans and index selectivity; report distribution statistics such as median and tail latency; and demonstrate before-and-after improvements without weakening correctness or reconciliation controls.

## Vital-measurement scope

This increment delivers one intake vital panel for each of the 300 historical encounters. The population requirements retain a longer-term target of 600 vital measurement events. The remaining measurements should represent purposeful repeat observations or scenario-specific reassessments rather than duplicate copies added solely to reach a target count.

This distinction preserves the difference between an encounter, an intake panel, and a later measurement event and provides a defensible basis for future workload and capacity testing.

## FHIR scope

Database and OpenEMR user-interface relationships are authoritative for this increment. FHIR Encounter and vital Observation representation will be reconciled as a separate interoperability step after the historical population baseline is complete.

Synthetic providers intentionally have no fabricated NPI. OpenEMR 8.2.0 encounter searches restrict provider UUID joins to providers with nonblank NPIs, so provider participation may be omitted from FHIR even when the underlying database relationship is correct.
