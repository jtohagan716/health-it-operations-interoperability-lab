\# KB-FHIR-003 â€” Calculated Blood Pressure Observation Missing Encounter Reference



\## Status



Runtime and official release-source inspection identified a high-confidence implementation hypothesis for the missing Encounter reference. Causality has not yet been established. A controlled diagnostic modification and restoration test is planned.



Investigation in progress.



A reproducible FHIR mapping anomaly has been isolated in OpenEMR 8.2.0. Runtime source inspection has identified a high-confidence implementation hypothesis.



The application has not yet been modified. A controlled before/after/restoration test is planned to establish causality.



\## Summary



During reconciliation of synthetic OpenEMR vital-sign data against the FHIR R4 API, one calculated blood-pressure Observation was found to omit its expected Encounter reference.



The patient relationship and clinical values remained intact.



\## Environment



\- Application: OpenEMR

\- Version: 8.2.0

\- FHIR version: R4 / 4.0.1

\- Authentication: SMART / OAuth 2.0

\- Data: Synthetic laboratory data only

\- Patient identifier: `LAB000001`

\- Test environment: Docker-based local lab



\## Clinical Baseline



The source EHR encounter contained:



\- Respiratory rate: 16 /min

\- Heart rate: 72 /min

\- Temperature: 98.6 Â°F

\- Height: 70 in

\- Weight: 180 lb

\- BMI: 25.82

\- Blood pressure: 120/80 mmHg



FHIR reconciliation confirmed the expected LOINC-coded measurements.



\## Observation Search Result



The authenticated patient-scoped FHIR Observation query returned:



\- 18 total Observation resources

\- 16 vital-sign Observations

\- 2 social-history Observations



\### Relationship Reconciliation



| Validation | Result |

|---|---:|

| Vital-sign Observations | 16 |

| Correct Patient references | 16 / 16 |

| Correct Encounter references | 15 / 16 |

| Missing Encounter references | 1 / 16 |



\## Isolated Observation



The only vital-sign Observation without an Encounter reference was:



\- LOINC: `96607-7`

\- Display: Blood pressure panel mean systolic and mean diastolic

\- Patient reference: Present and correct

\- Encounter reference: Missing



All other vital-sign Observations referenced the expected Patient and Encounter.



\## Expected Relationship



```text

Patient

&#x20;  |

&#x20;  v

Encounter

&#x20;  |

&#x20;  v

Observation
