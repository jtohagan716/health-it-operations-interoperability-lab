# KB-FHIR-003 - Calculated Blood Pressure Observation Missing Encounter Reference

## Status

Confirmed controlled reproduction in the OpenEMR 8.2.0 laboratory environment.

A patient-scoped FHIR Observation query consistently omitted the Encounter reference from one calculated blood-pressure Observation. Runtime source inspection identified a field-name mismatch in the calculated-vitals transformation and downstream FHIR mapping path.

A controlled A/B/A experiment established causality in this lab reproduction:

- A1 - Original OpenEMR 8.2.0: 15 of 16 vital-sign Observations contained the expected Encounter reference.
- B - Temporary one-line diagnostic alias: 16 of 16 contained the expected Encounter reference.
- A2 - Original source restored: result returned to 15 of 16.

The temporary diagnostic modification was removed. The running environment was restored to the pristine OpenEMR source after testing.

This investigation confirms the mechanism responsible for the observed omission in this environment. It does not yet establish that the diagnostic alias is the correct general-purpose production fix for every calculated-vitals scenario.

## Summary

During reconciliation of synthetic OpenEMR clinical data against the FHIR R4 API, one calculated blood-pressure Observation was found to omit its expected `Observation.encounter` relationship.

The affected Observation was:

- LOINC: `96607-7`
- Display: `Blood pressure panel mean systolic and mean diastolic`

The Observation retained the correct Patient relationship and calculated blood-pressure values. The anomaly was limited to the missing Encounter relationship.

The investigation progressed from FHIR-level reconciliation to deployed application-source inspection and then to a controlled diagnostic experiment.

## Environment

- Application: OpenEMR
- Version under test: 8.2.0
- FHIR version: R4 / 4.0.1
- Authentication: SMART / OAuth 2.0
- Client context: authenticated OpenEMR user
- Test environment: local Docker-based laboratory environment
- Data classification: synthetic laboratory data only
- External patient identifier: `LAB000001`
- FHIR Patient ID: `a27ef7a3-d677-428c-9aaf-fba45109cd02`
- FHIR Encounter ID: `a27f002a-3713-4684-ac2e-61a5af1beb11`

No production data, PHI, production credentials, or proprietary configuration was used.

## Clinical Baseline

The synthetic source encounter contained the following measurements:

| Measurement | Source value |
|---|---:|
| Respiratory rate | 16 /min |
| Heart rate | 72 /min |
| Temperature | 98.6 deg F |
| Height | 70 in |
| Weight | 180 lb |
| BMI | 25.82 kg/m2 |
| Blood pressure | 120/80 mmHg |

FHIR reconciliation confirmed the corresponding clinical measurements.

The FHIR BMI value contained greater numeric precision than the OpenEMR user interface display. That difference was treated as representation precision rather than a clinical-value mismatch.

## FHIR Observation Baseline

The authenticated patient-scoped Observation search returned:

- 18 total Observation resources
- 16 vital-sign Observations
- 2 social-history Observations

### Relationship Reconciliation

| Validation | A1 baseline result |
|---|---:|
| Vital-sign Observations | 16 |
| Correct Patient references | 16 / 16 |
| Correct Encounter references | 15 / 16 |
| Missing Encounter references | 1 / 16 |

All 16 vital-sign Observations referenced the expected Patient.

Fifteen of the 16 referenced the expected Encounter.

## Isolated Observation

The only vital-sign Observation without an Encounter relationship was:

- LOINC: `96607-7`
- Display: `Blood pressure panel mean systolic and mean diastolic`
- Patient reference: present and correct
- Encounter reference: absent

Expected Patient reference:

`Patient/a27ef7a3-d677-428c-9aaf-fba45109cd02`

Expected Encounter reference:

`Encounter/a27f002a-3713-4684-ac2e-61a5af1beb11`

The source clinical values remained intact.

## Expected Relationship

The expected interoperability relationship for this encounter-scoped laboratory case was:

```text
Patient
   |
   v
Encounter
   |
   v
Observation


Patient
   |
   v
Observation

Encounter relationship absent

## Investigation Method

The investigation followed a layered troubleshooting process:

1. Validate the source EHR clinical record.
2. Retrieve the Patient through the authenticated FHIR API.
3. Retrieve and reconcile the Encounter.
4. Retrieve all patient-scoped Observations.
5. Compare Patient and Encounter relationships across all vital-sign resources.
6. Isolate the single Observation missing Encounter context.
7. Inspect the deployed OpenEMR FHIR Observation implementation.
8. Trace the calculated-vitals transformation into the downstream FHIR mapper.
9. Form a field-mapping hypothesis.
10. Preserve the original runtime source and its SHA-256 fingerprint.
11. Commit the unmodified behavioral baseline.
12. Apply one temporary diagnostic source change.
13. Restart OpenEMR to remove opcode-cache ambiguity.
14. Repeat the identical FHIR query.
15. Restore the pristine source.
16. Restart OpenEMR again.
17. Repeat the identical FHIR query a third time.

This produced an A/B/A experiment with one intended source-code variable.

## Runtime Source Finding

Runtime inspection focused on:

`FhirObservationVitalsService.php`

The calculated-record transformation preserved the encounter UUID under a field named:

```php
'encounter_uuid'
'euuid'

This created the working hypothesis that the calculated record retained the encounter UUID, but the downstream mapper did not receive it under the field name it expected.

The original runtime source was preserved before any modification and its SHA-256 fingerprint was recorded.

Diagnostic Modification

For diagnostic purposes only, the existing calculated-record transformation was temporarily supplemented with an additional alias:

'euuid' => $calculatedRecord['euuid'] ?? null,

The existing encounter_uuid field was left intact.

No other application logic was intentionally changed.

Before deployment:

the original runtime source matched the preserved pristine backup;
the diagnostic candidate differed by one added line;
the diagnostic candidate passed PHP syntax validation.

After deployment:

the live runtime file matched the diagnostic candidate by SHA-256;
OpenEMR was restarted before the FHIR query was repeated.

This was a temporary diagnostic intervention, not a production remediation.

Controlled A/B/A Experiment
A1 - Original OpenEMR 8.2.0

Initial state:

Validation	Result
Vital-sign Observations	16
Correct Patient references	16 / 16
Correct Encounter references	15 / 16
Missing Encounter references	1 / 16

LOINC 96607-7:

Patient reference: present
Encounter reference: absent
B - Diagnostic Field Alias

After adding the temporary euuid alias:

Validation	Result
Vital-sign Observations	16
Correct Patient references	16 / 16
Correct Encounter references	16 / 16
Missing Encounter references	0 / 16

LOINC 96607-7 now contained:

Encounter/a27f002a-3713-4684-ac2e-61a5af1beb11

The Patient reference remained unchanged and correct.

A2 - Pristine Source Restored

The original FhirObservationVitalsService.php was restored.

The restored live runtime SHA-256 matched the preserved pre-change source.

OpenEMR was restarted and the same authenticated FHIR Observation request was repeated.

Result:

Validation	Result
Vital-sign Observations	16
Correct Patient references	16 / 16
Correct Encounter references	15 / 16
Missing Encounter references	1 / 16

LOINC 96607-7 again contained:

Patient reference: present
Encounter reference: absent
A/B/A Result

The controlled sequence was:

A1 - Original
15 / 16 Encounter references
96607-7 Encounter absent


        |
        | add one diagnostic euuid alias
        v


B - Diagnostic
16 / 16 Encounter references
96607-7 Encounter present


        |
        | restore pristine source
        v


A2 - Restored Original
15 / 16 Encounter references
96607-7 Encounter absent

## Conclusion

The A/B/A experiment establishes a causal relationship in this OpenEMR 8.2.0 laboratory reproduction between the calculated-record encounter field mapping and the missing FHIR `Observation.encounter` relationship.

The evidence supports the following mechanism:

1. The calculated vital-sign record contains an encounter UUID.
2. The transformation exposes that value under `encounter_uuid`.
3. The downstream FHIR Observation mapping path looks for `euuid`.
4. The expected Encounter reference is therefore not emitted for the affected calculated Observation.
5. Temporarily preserving the same encounter UUID under `euuid` causes the Encounter relationship to appear.
6. Restoring the original implementation causes the omission to return.

This moves the finding beyond correlation or source-code suspicion. The behavior was reproduced through controlled introduction and removal of a single mapping variable.

## What This Experiment Does Not Establish

This experiment does not establish that adding an unconditional `euuid` alias is the correct upstream production fix.

Calculated clinical observations can have different scopes and derivation rules. Before proposing a permanent code change, the intended semantics of each calculated-vitals type should be reviewed.

In particular, a permanent remediation should determine whether the calculated Observation is:

- derived entirely from one encounter;
- derived across multiple encounters;
- intended to represent a longitudinal calculation;
- or subject to another context rule.

The diagnostic alias demonstrates the mapping mechanism. It should not be treated as a universal production patch without that additional semantic analysis.

## Operational Impact

In this reproduction, the clinical measurement itself was not lost or altered.

The defect affected resource context.

A downstream consumer relying on `Observation.encounter` could potentially lose the ability to associate the calculated Observation with the expected visit without applying additional reconciliation logic.

Possible downstream effects include:

- incomplete encounter-based grouping;
- weaker clinical provenance;
- inconsistent reporting;
- interoperability reconciliation discrepancies;
- additional interface-engine or consumer-side matching logic.

The exact impact depends on how a consuming system uses the Encounter relationship.

## Recovery and Restoration

The diagnostic source modification was removed after testing.

The original OpenEMR source file was restored.

The restored runtime SHA-256 was verified against the preserved pre-change source.

The final A2 query confirmed that the restored environment again exhibited the original 15-of-16 Encounter-reference behavior.

The laboratory environment was therefore not left running modified vendor application code.

## Evidence

Evidence for this investigation is stored under:

`docs/operations/known-behaviors/evidence/KB-FHIR-003/`

Key artifacts include:

- `baseline-results.txt`
- `observation-baseline.json`
- `original-runtime-source-sha256.txt`
- `runtime-source-excerpts.txt`
- `diagnostic-patch.txt`
- `diagnostic-patch-results.txt`
- `diagnostic-runtime-sha256.txt`
- `observation-diagnostic-patch.json`
- `restoration-results.txt`
- `restored-runtime-sha256.txt`
- `observation-restored-original.json`

These artifacts preserve the behavioral baseline, diagnostic state, restored state, raw FHIR responses, source evidence, and runtime fingerprints used in the experiment.

## Security and Data Handling

All clinical records used in this investigation are synthetic.

No PHI was used.

OAuth access tokens, client secrets, authorization codes, callback URLs containing authorization codes, and other credentials are intentionally excluded from repository evidence.

## Engineering Classification

This finding is classified as:

- FHIR interoperability behavior;
- resource relationship mapping defect reproduced in the lab;
- calculated-vitals transformation/mapping issue;
- data-context integrity issue;
- controlled root-cause reproduction.

It is not classified as:

- clinical-value corruption;
- authentication failure;
- authorization failure;
- data-loss event;
- security vulnerability.

## Recommended Next Investigation

Before proposing an upstream fix:

1. Inspect the calculated-vitals service that generates the affected `96607-7` record.
2. Determine the intended encounter semantics for that calculation type.
3. Determine whether other calculated Observation types exhibit the same field-name behavior.
4. Test multiple encounters and multiple blood-pressure measurements.
5. Determine whether calculated observations spanning encounters should intentionally omit `Observation.encounter`.
6. Search existing OpenEMR issues and pull requests for the same behavior.
7. If no existing report covers the defect, prepare a minimal reproducible upstream issue using synthetic data only.
8. Propose a permanent correction only after the expected semantics are established.

## Engineering Lesson

A successful HTTP response and clinically correct measurement values do not prove interoperability correctness.

FHIR validation must also reconcile relationships and context.

In this case:

```text
HTTP 200
+
correct Patient
+
correct blood-pressure values
!=
complete resource relationship integrity

The defect became visible only after validating Patient, Encounter, and Observation relationships as a connected clinical data model rather than validating individual field values in isolation.
