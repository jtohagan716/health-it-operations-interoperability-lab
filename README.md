# Health IT Operations & Interoperability Lab

A hands-on healthcare interoperability and systems-reliability lab for validating how clinical and administrative data moves, transforms, persists, fails, recovers, and reconciles across system boundaries.

The project applies enterprise healthcare operations experience to a modern local stack built with **HL7 v2, Mirth Connect, OpenEMR, DICOM, Orthanc PACS, X12 EDI, FHIR R4, SMART on FHIR, SQL, Python, pytest, PowerShell, and Docker Compose**.

> All patients, encounters, orders, results, identifiers, and credentials used by this project are synthetic.

## What This Project Demonstrates

This is not a collection of disconnected protocol examples. Each workflow is designed to answer operational questions that matter in real healthcare interfaces:

- Did the transaction originate from the expected source?
- Did it travel through the intended interface path?
- Did its clinical meaning survive transformation and persistence?
- Did identifiers remain correlated across system boundaries?
- Did failures produce truthful acknowledgments and observable state?
- Did retries, replays, and duplicates behave safely?
- Did processing recover predictably after dependency restoration?
- Did the final database, API, PACS, or clinical workflow state match the source transaction?

The engineering lifecycle is deliberately repeatable:

```text
Understand -> Design -> Implement -> Validate
          -> Break -> Diagnose -> Recover
          -> Reconcile -> Document
```

## Featured Workflow: HL7 ORU Results from Mirth to OpenEMR

The strongest current workflow carries a synthetic laboratory result through Mirth and into the OpenEMR provider-review lifecycle.

```text
Laboratory ORU^R01
        |
        v
Mirth MLLP listener
        |
        +--> semantic validation
        +--> AA / AR acknowledgment
        +--> accepted persistence or quarantine
        |
        v
PostgreSQL audit and delivery state
        |
        v
Guarded OpenEMR delivery worker
        |
        +--> explicit target correlation
        +--> mandatory non-persisting dry run
        +--> duplicate and replay protection
        +--> commit postcondition verification
        |
        v
OpenEMR native DORN result parser
        |
        v
Provider Pending Review -> signed / reviewed
```

### Live proof

The complete workflow was validated with a final glucose result:

| Evidence | Verified value |
| --- | --- |
| Procedure | LOINC `2345-7` - Glucose |
| Result | `90 mg/dL` |
| Reference range | `70-99` |
| Abnormal flag | `N` |
| Mirth acknowledgment | `AA` |
| OpenEMR persistence | Exactly one report and one result |
| Report/result status | `final` / `final` |
| Provider workflow | `received` -> `reviewed` |
| Duplicate behavior | Older duplicate blocked before OpenEMR delivery |

The implementation does **not** write directly to OpenEMR tables. It invokes OpenEMR's native result parser through a local guarded boundary and verifies the resulting clinical records.

Detailed evidence:

- [OpenEMR ORU Ingestion Bridge](docs/validation/openemr-oru-ingestion-bridge.md)
- [Mirth-to-OpenEMR ORU Delivery](docs/validation/mirth-openemr-oru-delivery.md)
- [HL7 / Mirth Audit Reliability Validation](docs/validation/03-hl7-mirth-audit-reliability-validation.md)
- [HL7 Replay, Message Identity, and Payload Integrity](docs/validation/04-hl7-replay-payload-integrity-validation.md)

## Validated Capabilities

| Area | What is validated |
| --- | --- |
| HL7 ADT | Deterministic `ADT^A04` processing, field extraction, semantic checks, positive/negative scenarios, and acknowledgment correlation |
| HL7 ORU | Normal, abnormal, critical, preliminary, and corrected result scenarios; OBR/OBX validation; quarantine and recovery |
| Mirth Connect | MLLP listeners, source transformation, destination persistence, postprocessor ACK policy, dependency failure, and recovery |
| Transaction integrity | MSH-10/MSA-2 correlation, SHA-256 payload identity, exact replay classification, conflicting identity detection, and duplicate containment |
| OpenEMR results | Order/patient/encounter/lab correlation, guarded dry run, native DORN ingestion, persistence verification, Pending Review, and provider acknowledgment |
| Radiology/PACS | HL7 ORM orders, DICOM C-STORE, C-FIND/C-MOVE, Orthanc routing, order-to-study lineage, result correlation, and reconciliation |
| X12 eligibility | 270/271 envelope and business validation, request/response correlation, persistence, replay, and idempotency behavior |
| FHIR R4 | Patient identity and laboratory-result retrieval/reconciliation against OpenEMR runtime state |
| SMART on FHIR | Discovery, authorization-code flow, token lifecycle, role-aware scope behavior, and authenticated resource access |
| Operational readiness | Container, token, database, PACS, DICOM listener, and C-ECHO prerequisite checks before live tests |

## Reliability Controls

The lab treats deterministic, reproducible behavior as a core requirement.

### Acknowledgment truthfulness

- Correlates outbound MSH-10 with returned MSA-2.
- Distinguishes interface availability from downstream persistence health.
- Verifies that dependency failure produces an error acknowledgment instead of false success.
- Preserves receiver-side evidence when an ACK arrives after the sender timeout.

### Message identity and replay safety

```text
same message identity + same payload fingerprint
    = exact replay

same message identity + different payload fingerprint
    = conflicting identity reuse
```

- Persists a SHA-256 fingerprint with transaction metadata.
- Separates transport identity from clinical business identity.
- Blocks duplicate active delivery to the same OpenEMR order.
- Prevents an existing OpenEMR result from being silently overwritten by replay.

### Failure containment and recovery

- Quarantines invalid ORU messages with their failure context.
- Prevents poison messages from blocking unrelated valid traffic.
- Tests dependency interruption while Mirth remains running.
- Verifies forward progress after PostgreSQL recovery.
- Records delivery state, attempt count, timestamps, errors, and postconditions.

### Clinical postcondition verification

Success is not inferred from an ACK alone. Depending on the workflow, validation reconciles the source transaction with:

- PostgreSQL audit state
- OpenEMR MariaDB records
- OpenEMR provider-review state
- OpenEMR FHIR resources
- Orthanc study metadata
- DICOM retrieval results

## Radiology and PACS Workflow

The radiology workflow spans HL7 order processing, normalized persistence, DICOM transport, PACS storage, result lineage, and live reconciliation.

```text
HL7 ORM^O01 -> Mirth -> PostgreSQL order state
                            |
                            v
                    DICOM C-STORE -> Orthanc
                            |
                            v
                    ORM -> DICOM -> ORU lineage
```

Validated behavior includes accession-number preservation, Study Instance UID preservation, modality and description checks, C-FIND/C-MOVE, metadata-driven routing, destination failure/recovery, idempotent workflow persistence, and conflicting imaging-identity rejection.

Documentation:

- [Radiology Interoperability Workflow](docs/radiology-interoperability-workflow.md)
- [PACS Operator Troubleshooting Runbook](docs/pacs-operator-troubleshooting-runbook.md)
- [DICOM Auto-Routing Failure and Recovery](docs/case-study-dicom-autorouting-failure-recovery.md)

## FHIR and SMART Authorization

The OpenEMR FHIR work validates both token-level authorization and the EHR policy applied to the authenticated principal.

```text
Valid bearer token
        -> granted SMART scope
        -> authenticated EHR principal
        -> underlying EHR policy
        -> final resource-access decision
```

Coverage includes SMART discovery, advertised endpoints and capabilities, authorization-code token acquisition, OAuth state validation, token expiry prerequisites, separate administrator/restricted-provider token files, authenticated Patient/Encounter/Observation/DiagnosticReport access, and principal-dependent Organization/Practitioner authorization.

Detailed evidence:

- [SMART on FHIR Authorization Validation](docs/validation/05-smart-fhir-authorization-validation.md)
- [Runtime Readiness Preflight](docs/operations/runtime-readiness-preflight.md)

## X12 Eligibility

The project includes a synthetic X12 270/271 eligibility workflow with envelope validation, transaction-set validation, request/response correlation, business-data checks, PostgreSQL persistence, receipt classification, replay analysis, and idempotency behavior.

- [X12 Eligibility Interoperability](docs/x12-eligibility-interoperability.md)

## Technology Stack

### Healthcare interoperability

- HL7 v2.5.1, MLLP, Mirth Connect 4.5.2
- OpenEMR and its DORN laboratory module
- FHIR R4, US Core exposure, SMART on FHIR / OAuth 2.0
- DICOM, Orthanc PACS
- X12 EDI 270/271

### Engineering and operations

- Python, pytest, PowerShell
- PostgreSQL 16, MariaDB
- REST APIs
- Docker Compose
- Git and GitHub

## Running the Lab

The repository contains local Docker Compose environments for OpenEMR, Mirth/PostgreSQL, and Orthanc.

Before running authenticated FHIR, database, PACS-routing, or DICOM-retrieval tests, run the non-secret readiness gate from the repository root:

```powershell
python -m scripts.preflight.readiness
```

The command returns exit code `0` when required infrastructure and short-lived credentials are ready, and `1` when a prerequisite is unavailable. Credential and token values are never printed.

Individual validation documents contain the commands and expected evidence for each workflow. Live tests are intentionally separated from deterministic unit and contract tests because they require running infrastructure and test-owned local data.

## Evidence and Documentation

### Foundations and reliability

- [Project Charter](docs/PROJECT_CHARTER.md)
- [OpenEMR Foundation Validation](docs/validation/01-openemr-foundation-validation.md)
- [Mirth Connect Foundation Validation](docs/validation/02-mirth-connect-foundation-validation.md)
- [HL7 / Mirth Audit Reliability Validation](docs/validation/03-hl7-mirth-audit-reliability-validation.md)
- [HL7 Replay and Payload Integrity](docs/validation/04-hl7-replay-payload-integrity-validation.md)

### Clinical and protocol workflows

- [OpenEMR ORU Ingestion Bridge](docs/validation/openemr-oru-ingestion-bridge.md)
- [Mirth-to-OpenEMR ORU Delivery](docs/validation/mirth-openemr-oru-delivery.md)
- [SMART on FHIR Authorization Validation](docs/validation/05-smart-fhir-authorization-validation.md)
- [Radiology Interoperability Workflow](docs/radiology-interoperability-workflow.md)
- [X12 Eligibility Interoperability](docs/x12-eligibility-interoperability.md)

### Operations

- [Runtime Readiness Preflight](docs/operations/runtime-readiness-preflight.md)
- [PACS Operator Troubleshooting Runbook](docs/pacs-operator-troubleshooting-runbook.md)
- [DICOM Auto-Routing Failure and Recovery](docs/case-study-dicom-autorouting-failure-recovery.md)

## Current Scope and Limitations

This repository is an engineering and validation lab, not a production healthcare system.

- All data is synthetic; no PHI is used.
- Infrastructure runs in local containers.
- Selected local calls use self-signed TLS or disabled certificate verification.
- Runtime credentials, passwords, OAuth tokens, and client secrets are excluded from source control.
- Authorization results reflect the configured OpenEMR principal and local EHR policy.
- The Mirth-to-OpenEMR worker is explicitly invoked and processes one claimed message at a time.
- Continuous background delivery, production deployment, and an external commercial laboratory connection are not claimed.
- The project does not claim regulatory or production compliance certification.

## Next Operational Reliability Increment

The next feature will turn the explicitly invoked OpenEMR delivery worker into a durable background service while preserving the current safety boundary.

Planned work includes:

- automatic delivery polling
- claim leases and abandoned-work recovery
- bounded retries and dead-letter handling
- health checks and operational metrics
- deterministic restart behavior
- Docker Compose integration
- live crash-recovery and retry-safety tests

OpenEMR-specific decisions will continue to favor native extension points and result lifecycle behavior. Operational safeguards will remain outside OpenEMR where they can be tested and observed independently.

## Engineering Background

This project builds on enterprise healthcare systems experience involving:

- AHLTA and CHCS clinical systems
- HL7 ADT, laboratory, radiology, and medication interfaces
- eGate and BEA Tuxedo middleware
- Oracle-backed healthcare applications
- interface queues, synchronization jobs, and failover behavior
- Windows Server, Linux/Unix, and IIS/ASP.NET operations
- LoadRunner performance and endurance testing
- production troubleshooting, release validation, and database analysis
- distributed Department of Defense healthcare environments

The modern technologies in this repository extend those established operational concepts rather than presenting them as disconnected tutorials.

## Project Status

**Active development - healthcare interoperability quality engineering and systems reliability.**

Current validated areas include HL7 ADT/ORM/ORU processing, MLLP and ACK correlation, Mirth persistence and quarantine, guarded OpenEMR result delivery, provider-review reconciliation, replay and duplicate containment, FHIR/SMART authorization, X12 eligibility, DICOM/PACS workflows, database lineage, dependency failure, and deterministic recovery.
