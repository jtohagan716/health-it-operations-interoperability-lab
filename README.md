# Health IT Operations & Interoperability Lab

A hands-on healthcare interoperability and systems-quality engineering lab focused on validating how healthcare information moves, transforms, persists, fails, recovers, and reconciles across system boundaries.

The project builds on enterprise healthcare systems experience and applies those concepts to a modern interoperability stack using HL7 v2, Mirth Connect, FHIR, SMART/OAuth, APIs, PostgreSQL, Docker, and automated testing.

All patient data used in this project is synthetic.

---

## Project Mission

The primary specialization of this lab is:

**Healthcare interoperability quality engineering focused on patient identity, transaction integrity, source-to-target data lineage, and reliable HL7/FHIR exchange.**

The objective is not simply to prove that individual applications or interfaces can run.

The objective is to validate whether healthcare information:

- originated from the expected source
- traveled through the expected integration path
- retained its intended meaning
- persisted to the correct destination
- remained correlated across system boundaries
- behaved safely during retries and replays
- surfaced downstream failure truthfully
- recovered predictably after dependency restoration
- reconciled correctly with downstream API and database state

---

## Engineering Approach

Each capability is developed using a repeatable engineering lifecycle:

**Understand -> Design -> Implement -> Validate -> Break -> Diagnose -> Recover -> Reconcile -> Document**

Testing is performed across multiple evidence layers rather than relying on a single success indicator.

Examples include:

- HL7 acknowledgment validation
- MSH-10 / MSA-2 transaction correlation
- interface-engine behavior
- direct SQL persistence verification
- source-to-target data reconciliation
- API contract validation
- authentication boundary testing
- controlled dependency failure
- recovery validation
- duplicate and replay analysis
- deterministic automated regression testing

---

## Current Interoperability Stack

The current lab includes:

- OpenEMR
- Mirth Connect 4.5.2
- HL7 v2.5.1
- MLLP
- FHIR R4
- US Core exposure
- SMART on FHIR / OAuth2
- PostgreSQL 16
- MariaDB
- Python
- pytest
- PowerShell
- Docker Compose
- Git / GitHub

---

## Current Validation Capabilities

### HL7 ADT Processing

The lab includes deterministic synthetic `ADT^A04` transactions processed through a Mirth MLLP listener.

Validation includes:

- HL7 field extraction
- MSH-10 message control ID correlation
- MSA-2 acknowledgment correlation
- expected AA / AE behavior
- patient identifier validation
- cross-segment consistency checks

### Source-to-Target Data Lineage

HL7 source values are traced through the interface and reconciled against persisted PostgreSQL state.

Current mappings include:

    MSH-10      -> message_control_id
    MSH-9.1     -> message_type
    MSH-9.2     -> trigger_event
    PID-3.1     -> patient_identifier
    MSH-3       -> sending_application
    MSH-4       -> sending_facility
    HL7 payload -> payload_sha256

This provides source-to-target data lineage validation rather than relying only on transport-level success.

### Failure and Recovery

Automated testing deliberately interrupts the downstream PostgreSQL dependency while Mirth remains operational.

The validation verifies:

- downstream persistence failure returns HL7 AE
- MSH-10 / MSA-2 correlation remains intact
- failed transactions are not falsely recorded as persisted
- PostgreSQL recovery is verified through actual container health
- successful processing resumes after dependency restoration
- Mirth does not require restart for recovery

### Replay and Transaction Integrity

Controlled tests currently distinguish:

    same message identity
    + same payload fingerprint
    = exact replay

from:

    same message identity
    + different payload fingerprint
    = conflicting message reuse

Mirth generates a SHA-256 fingerprint from the inbound HL7 payload and persists the fingerprint with transaction metadata in PostgreSQL.

This allows duplicate-message conditions to be classified using objective transaction evidence.

### FHIR and SMART/OAuth

The lab also includes:

- SMART client registration
- OAuth token acquisition
- token lifecycle validation
- expired-token prerequisite detection
- missing bearer-token validation
- invalid bearer-token validation
- authenticated FHIR Patient access
- HL7 PID to FHIR Patient identity reconciliation

---

## Validation Case Studies

Detailed engineering evidence is maintained under `docs/validation`.

### OpenEMR Foundation

[OpenEMR Foundation Validation](docs/validation/01-openemr-foundation-validation.md)

### Mirth Connect Foundation

[Mirth Connect Foundation Validation](docs/validation/02-mirth-connect-foundation-validation.md)

### HL7 / Mirth Failure and Recovery

[HL7 Mirth Audit Reliability Validation](docs/validation/03-hl7-mirth-audit-reliability-validation.md)

### HL7 Replay and Payload Integrity

[HL7 Replay, Message Identity, and Payload Integrity Validation](docs/validation/04-hl7-replay-payload-integrity-validation.md)

This case study includes automated-test, Mirth, PostgreSQL, and operational evidence demonstrating exact replay, conflicting message identity, SHA-256 payload fingerprinting, and source-to-target persistence validation.

---

## Current Engineering Focus

The project is intentionally moving away from accumulating unrelated technologies.

The current specialization is centered on:

- patient identity
- transaction integrity
- message versus business identity
- duplicate and replay behavior
- stale and out-of-order updates
- source-to-target data lineage
- HL7-to-FHIR semantic fidelity
- persistence validation
- FHIR conformance
- reliability and recovery

Upcoming work will extend the current transaction-integrity model into patient-identity scenarios and HL7-to-FHIR reconciliation.

---

## Planned Patient Identity Scenarios

Future validation will progressively examine:

- assigning authorities
- duplicate patient identifiers
- demographic changes
- near demographic matches
- ambiguous identity
- duplicate patient creation
- legitimate updates
- stale updates
- out-of-order updates
- patient merge/link scenarios
- FHIR Patient search
- FHIR patient matching behavior

The intended end-to-end path is:

    HL7 v2
        |
        v
      Mirth
        |
        v
    patient identity evaluation
        |
        v
    HL7-to-FHIR mapping
        |
        v
    SMART / OAuth
        |
        v
    OpenEMR FHIR API
        |
        v
    FHIR retrieval
        |
        v
    source-to-target reconciliation

---

## Background

The project builds upon healthcare IT experience involving:

- AHLTA
- CHCS
- HL7 v2
- eGate healthcare interfaces
- BEA Tuxedo middleware
- Oracle-backed healthcare systems
- IIS / ASP.NET application support
- enterprise production troubleshooting
- performance and reliability validation
- load and endurance testing
- release validation
- database analysis

Modern interoperability technologies are introduced as extensions of those systems concepts rather than as disconnected technical exercises.

---

## Data Safety and Configuration Security

All clinical data used in this project is synthetic.

No PHI or real patient information is used.

Runtime credentials, OAuth tokens, passwords, and local secrets are excluded from source control.

Exported Mirth channel configuration uses placeholders such as:

    REPLACE_WITH_LOCAL_SECRET

instead of live credentials.

---

## Project Status

**Active development - healthcare interoperability quality engineering specialization.**

See [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) for the broader engineering objectives and methodology.
