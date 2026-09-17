# Mirth-to-OpenEMR Closed-Loop Playwright Validation

## Objective

Validate a deterministic laboratory workflow from an existing OpenEMR laboratory requisition through the interoperability pipeline and back into clinician-visible OpenEMR state.

The validation connects backend interoperability evidence with browser-level clinical workflow validation. The Playwright test validates only application-visible state and does not query middleware or databases.

## Validated Flow

Existing OpenEMR laboratory order
-> OML^O21
-> Mirth Connect
-> Synthetic LIS
-> ORU^R01
-> Mirth accepted-result audit
-> Guarded OpenEMR delivery
-> Native OpenEMR laboratory persistence
-> Clinician-visible OpenEMR Labs UI
-> Playwright assertion

## Deterministic Source Order

The transaction used an existing, previously unconsumed synthetic OpenEMR laboratory order rather than inserting a result directly for browser testing.

| Field | Value |
| --- | --- |
| OpenEMR order ID | 14 |
| External order ID | SYNLAB00000901 |
| Patient ID | 10 |
| Patient MRN | SYNTHMRN000009 |
| Patient | Synthetic009 Test Patient009 |
| Encounter | 21 |
| Laboratory ID | 4 |
| Ordered test | Glucose |
| LOINC | 2345-7 |
| Ordered at | 2025-01-23 11:00:00 |
| Pre-transaction reports | 0 |
| Pre-transaction results | 0 |

This provided an unused laboratory requisition suitable for closed-loop validation.

## OML Order Transport

The existing order was transmitted through the laboratory-order workflow.

Observed result:

- Status: ACCEPTED
- Placer order: SYNLAB00000901
- OpenEMR order ID: 14
- Message control ID: SYNLIS-OML-SYNLAB00000901-01
- ACK code: AA
- ACK control ID: SYNLIS-OML-SYNLAB00000901-01

The synthetic LIS persisted the received order as LIS order ID 11 with order status RECEIVED.

## Deterministic LIS Result

The synthetic LIS generated the deterministic result associated with the received order.

| Field | Value |
| --- | --- |
| LIS order ID | 11 |
| Result control ID | SYNLIS-ORU-000011-01 |
| Test | Glucose |
| LOINC | 2345-7 |
| Result | 87 |
| Units | mg/dL |
| Reference range | 70-99 |
| Abnormal flag | N |
| Result status | F |
| Observation time | 2025-01-23 11:30:00 |

The ORU sender received an HL7 AA acknowledgment correlated to control ID SYNLIS-ORU-000011-01.

## Mirth Acceptance and Provenance

Mirth persisted the accepted ORU as audit message ID 281.

Observed state included:

- Message control ID: SYNLIS-ORU-000011-01
- Placer order: SYNLAB00000901
- Filler order: SYNLIS-SYNLAB00000901
- Message: ORU^R01
- Service: 2345-7 Glucose
- Processing status: ACCEPTED
- Provenance status: LINKED
- Observation time: 2025-01-23 11:30:00+00

The accepted result created guarded OpenEMR delivery ID 12 in PENDING state.

## Guarded OpenEMR Delivery

The explicit delivery worker was run with confirmation for OpenEMR order ID 14.

Final delivery state:

- Delivery ID: 12
- ORU audit message ID: 281
- OpenEMR order ID: 14
- Status: DELIVERED
- Attempt count: 1
- Error: none
- Report count: 1
- Result count: 1

This demonstrates the explicit guarded delivery boundary. It does not claim continuous background delivery.

## Native OpenEMR Persistence

After delivery, native OpenEMR laboratory persistence contained exactly one report and one result for the target order.

| Field | Value |
| --- | --- |
| Procedure report ID | 13 |
| Procedure result ID | 16 |
| OpenEMR order ID | 14 |
| Result code | 2345-7 |
| Result text | Glucose |
| Result | 87 |
| Units | mg/dL |
| Reference range | 70-99 |
| Abnormal | no |
| Result status | final |
| Report status | final |
| Review status | received |
| Result date | 2025-01-23 11:30:00 |

The native OpenEMR representation matched the deterministic LIS result after semantic normalization of the HL7 status and abnormality values.

## Clinician-Visible Playwright Validation

tests/ui/openemr/patient-lab-closed-loop.spec.ts validates the clinician-visible endpoint of the transaction.

The browser test:

1. Authenticates through OpenEMR.
2. Searches for Synthetic009 Test Patient009.
3. Confirms MRN SYNTHMRN000009.
4. Waits for the actual patient dashboard frame.
5. Opens the clinician-visible Labs workflow.
6. Selects LOINC 2345-7.
7. Switches to Matrix view.
8. Locates the Glucose row.
9. Verifies Glucose, 87, mg/dL, and reference range 70-99 within that row.

The Playwright test intentionally does not query Mirth, PostgreSQL, MariaDB, or other backend components. Backend interoperability state and clinician-visible application state are validated independently.

## Browser Synchronization Hardening

During this increment, authentication synchronization demonstrated that the successful OpenEMR main-tabs response can exceed the framework's default 10-second response wait.

The laboratory UI tests use an explicit 30-second timeout for the successful authenticated main-tabs response rather than a fixed sleep.

This preserves event-based synchronization while tolerating observed application latency.

## Validation Results

### Runtime Readiness

FHIR_ADMIN_TOKEN: READY

FHIR_RESTRICTED_TOKEN: READY

INTEROPLAB_SCP: READY

ORTHANC_INTEROPLAB: READY

RUNTIME READINESS: PASS

### Restricted FHIR Authorization Boundary

2 passed, 2 warnings in 1.80s

### Python Regression

545 passed, 1 skipped, 1 xfailed, 34 warnings in 236.55s

The warnings are expected local-lab unverified HTTPS warnings associated with the self-signed OpenEMR development endpoint.

### Playwright Regression

5 passed

The Playwright regression included unauthenticated login behavior, authenticated login, deterministic patient-chart navigation, the closed-loop clinician-visible laboratory result, and the existing deterministic clinician-visible laboratory result.

The closed-loop test also passed repeatedly in isolated headed execution before the combined regression run.

## Evidence Chain

OpenEMR order 14
-> OML^O21
-> Mirth AA
-> synthetic LIS order 11
-> deterministic Glucose 87 mg/dL
-> ORU^R01 SYNLIS-ORU-000011-01
-> Mirth AA
-> accepted/provenance-linked audit message 281
-> guarded delivery 12
-> DELIVERED on attempt 1
-> OpenEMR report 13
-> OpenEMR result 16
-> LOINC 2345-7 / Glucose / 87 mg/dL / 70-99
-> clinician-visible OpenEMR Labs workflow
-> Playwright PASS

## Defensible Claim

This increment validates a deterministic order-to-result clinical workflow from an existing OpenEMR laboratory requisition through OML^O21, Mirth Connect, a synthetic LIS, ORU^R01, accepted and provenance-linked audit, guarded native OpenEMR delivery, and Playwright clinician-visible verification of the resulting LOINC-coded Glucose observation.

## Scope Boundary

This validation demonstrates one deterministic synthetic final numeric Glucose result through an explicit guarded delivery worker.

It does not claim continuous background OpenEMR result delivery, production LIS connectivity, validation of every laboratory result type, validation of every abnormal-flag or result-status combination, production deployment, or clinical use.

The purpose is reproducible interoperability and quality-engineering validation in the local healthcare integration laboratory.
