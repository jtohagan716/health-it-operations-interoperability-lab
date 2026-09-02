# Synthetic condition and encounter-diagnosis provisioning

This issue #31 increment adds clinically coherent ICD-10-CM conditions to the deterministic OpenEMR population. It deliberately distinguishes ongoing problem-list conditions from diagnoses associated with a particular encounter.

## Population model

- 100 encounter diagnoses: one for every synthetic patient's historical encounter
- 50 longitudinal problems: one for each patient in the prediabetes, diabetes, hypertension, cardiovascular, and respiratory cohorts
- 150 total `medical_problem` source records
- 100 `issue_encounter` relationships
- no billing or charge rows

The one-patient probe uses `SYNTHMRN000002`, a hypertension patient in the generated population, so it exercises both the unlinked problem-list and linked encounter-diagnosis paths. Cohort membership is resolved from the persisted synthetic patient record rather than inferred from patient numbering.

## Native OpenEMR behavior

`ConditionService::insert()` creates the source record in `lists`, assigns its UUID, and applies OpenEMR validation. `PatientIssuesService::linkIssueToEncounter()` creates the encounter relationship and its UUID without replacing unrelated issue links.

OpenEMR 8.2.0's FHIR Condition implementation separates unlinked `medical_problem` records into the `problem-list-item` category and records linked through `issue_encounter` into the `encounter-diagnosis` category. The provisioning model maintains separate records where both clinical concepts are required.

## Safety controls

- local synthetic environment only
- dry run by default
- one-patient representative probe
- exact commit-count confirmation
- synthetic patient and encounter preconditions
- active ICD-10-CM code validation
- stable external identifiers
- post-write relationship verification
- idempotent replay
- reverse-order compensating cleanup
- no billing-table writes

## Commands

Dry run:

```powershell
python -m scripts.synthetic.diagnoses
```

One-patient probe:

```powershell
python -m scripts.synthetic.diagnoses --probe --commit --environment local-lab --confirm-patient-count 1
```

Verify the probe:

```powershell
python -m scripts.synthetic.diagnoses --probe --verify
```

Full population:

```powershell
python -m scripts.synthetic.diagnoses --commit --environment local-lab --confirm-patient-count 100
```

Full verification:

```powershell
python -m scripts.synthetic.diagnoses --verify
```
## FHIR Condition validation

The registered OpenEMR FHIR client requests `user/Condition.rs`. An authenticated patient-based Condition search returned the expected problem-list and encounter-diagnosis resources and preserved:

- patient references
- encounter references for encounter diagnoses
- `problem-list-item` and `encounter-diagnosis` categories
- clinical and verification statuses
- onset dates
- abatement dates for ended conditions
- human-readable condition descriptions

Database-to-FHIR reconciliation identified a version-scoped coding behavior in the tested OpenEMR 8.2.0 environment. Synthetic records retained values such as `ICD10:I10` in `lists.diagnosis`, while the resulting FHIR resources populated `Condition.code.text` without exposing `Condition.code.coding`.

A separate control condition was created through OpenEMR's native issue editor by selecting Essential (primary) hypertension from its ICD-10 terminology search. OpenEMR stored the selected code as `ICD10:I10.` and produced the same text-only FHIR representation. Ending that control condition correctly produced `clinicalStatus` of `inactive` and preserved both `onsetDateTime` and `abatementDateTime`.

Source inspection explains the observed behavior: the FHIR Condition services select `lists.diagnosis` as a string, while the shared `populateCode()` implementation creates structured coding only when the supplied diagnosis value is an array. Otherwise, it deliberately falls back to the issue title as `Condition.code.text`.

A read-only source comparison against the OpenEMR 8.3.0 container image found that the shared Condition coding implementation is identical. Changes in the problem-list and encounter-diagnosis services were limited to Provenance handling. OpenEMR 8.3.0 runtime behavior has not yet been evaluated, so this evidence is recorded as an OpenEMR 8.2.0 runtime observation rather than a general product defect.

## Scope boundary

This increment provisions clinical condition records and encounter relationships. It does not create charges, claims, medications, laboratory results, or radiology results.
