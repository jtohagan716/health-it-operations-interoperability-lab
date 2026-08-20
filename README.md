# Health IT Operations & Interoperability Lab

A hands-on healthcare interoperability and systems-quality engineering lab focused on validating how healthcare information moves, transforms, persists, fails, recovers, and reconciles across system boundaries.

The project builds on enterprise healthcare systems experience and applies those concepts to a modern interoperability stack using HL7 v2, Mirth Connect, FHIR R4, SMART on FHIR/OAuth 2.0, REST APIs, PostgreSQL, Docker, and automated testing.

All patient data used in this project is synthetic.

---

## Project Mission

The primary specialization of this lab is:

**Healthcare interoperability quality engineering focused on patient identity, transaction integrity, source-to-target data lineage, and reliable HL7/FHIR exchange.**

The objective is not simply to prove that individual applications or interfaces can run.

The objective is to validate whether healthcare information:

* originated from the expected source
* traveled through the expected integration path
* retained its intended meaning
* persisted to the correct destination
* remained correlated across system boundaries
* behaved safely during retries and replays
* surfaced downstream failure truthfully
* recovered predictably after dependency restoration
* reconciled correctly with downstream API and database state
* respected authentication and authorization boundaries

---

## Engineering Approach

Each capability is developed using a repeatable engineering lifecycle:

**Understand -> Design -> Implement -> Validate -> Break -> Diagnose -> Recover -> Reconcile -> Document**

Testing is performed across multiple evidence layers rather than relying on a single success indicator.

Examples include:

* HL7 acknowledgment validation
* MSH-10 / MSA-2 transaction correlation
* field-level and cross-segment HL7 validation
* interface-engine behavior
* direct SQL persistence verification
* source-to-target data reconciliation
* API contract validation
* SMART/FHIR authentication and authorization testing
* token-lifecycle prerequisite validation
* controlled dependency failure
* recovery validation
* duplicate and replay analysis
* deterministic automated regression testing

---

## Current Interoperability Stack

The current lab includes:

* OpenEMR
* Mirth Connect 4.5.2
* HL7 v2.5.1
* MLLP
* FHIR R4
* US Core exposure
* SMART on FHIR / OAuth 2.0
* PostgreSQL 16
* MariaDB
* Python
* pytest
* PowerShell
* Docker Compose
* REST APIs
* Git / GitHub

---

## Current Validation Capabilities

### HL7 ADT Processing

The lab includes deterministic synthetic `ADT^A04` transactions processed through a Mirth MLLP listener.

Validation includes:

* HL7 segment, field, and component extraction
* MSH-10 message control ID correlation
* MSA-2 acknowledgment correlation
* expected AA / AE behavior
* patient identifier validation
* assigning-authority validation
* patient demographic validation
* visit and encounter-context validation
* coded-value interpretation
* HL7 timestamp validation
* MSH / EVN trigger-event consistency
* positive and negative message scenarios

The current analyzer distinguishes structural parsing from semantic validation so incomplete or inconsistent messages can be evaluated without causing the validator itself to fail unexpectedly.

### Source-to-Target Data Lineage

HL7 source values are traced through the interface and reconciled against persisted PostgreSQL state.

Current mappings include:

```text
MSH-10      -> message_control_id
MSH-9.1     -> message_type
MSH-9.2     -> trigger_event
PID-3.1     -> patient_identifier
MSH-3       -> sending_application
MSH-4       -> sending_facility
HL7 payload -> payload_sha256
```

This provides source-to-target data-lineage validation rather than relying only on transport-level success.

### Failure and Recovery

Automated testing deliberately interrupts the downstream PostgreSQL dependency while Mirth remains operational.

The validation verifies:

* downstream persistence failure returns HL7 AE
* MSH-10 / MSA-2 correlation remains intact
* failed transactions are not falsely recorded as persisted
* PostgreSQL recovery is verified through actual container health
* successful processing resumes after dependency restoration
* Mirth does not require restart for recovery

This provides a repeatable method for distinguishing interface availability from downstream dependency health.

### Replay and Transaction Integrity

Controlled tests distinguish:

```text
same message identity
+ same payload fingerprint
= exact replay
```

from:

```text
same message identity
+ different payload fingerprint
= conflicting message reuse
```

Mirth generates a SHA-256 fingerprint from the inbound HL7 payload and persists the fingerprint with transaction metadata in PostgreSQL.

This allows duplicate-message conditions to be classified using objective transaction evidence rather than message identity alone.

### HL7 Field and Semantic Validation

Automated pytest coverage currently includes:

* valid ADT^A04 messages
* incomplete or invalid ADT messages
* unsupported coded values
* missing patient identifiers
* missing assigning authorities
* missing visit identifiers
* missing message control IDs
* MSH / EVN event mismatches
* timestamp-format validation
* cross-segment semantic consistency

The validation model intentionally separates:

```text
Can the message be parsed?
        |
        v
Is the data structurally usable?
        |
        v
Is the message semantically consistent?
        |
        v
Does it satisfy the expected interface contract?
```

---

## FHIR and SMART on FHIR Authorization Validation

The lab includes automated validation of the OpenEMR SMART/FHIR authorization boundary.

Coverage includes:

* SMART discovery
* advertised authorization and token endpoints
* authorization-code token acquisition
* OAuth `state` validation
* bearer-token handling
* token lifecycle and expiration prerequisites
* missing credential rejection
* invalid credential rejection
* granted SMART scope validation
* authenticated FHIR resource access
* application/EHR policy constraints
* HL7 PID to FHIR Patient identity reconciliation

### Authentication Boundary

Observed behavior includes:

```text
Missing bearer token  -> HTTP 401
Invalid bearer token  -> HTTP 401
Valid Patient access  -> HTTP 200
```

The authorization harness does not display bearer-token values and keeps temporary credentials outside the repository.

### Token Lifecycle

The token-acquisition workflow records non-secret lifecycle metadata including:

* token type
* configured lifetime
* acquisition time
* calculated expiration time
* granted scopes

The test harness classifies authentication state as:

```text
FRESH
EXPIRING_SOON
EXPIRED
```

Authenticated workloads can be prevented from starting when the token is expired or has insufficient remaining lifetime.

This allows authentication-prerequisite failures to be distinguished from FHIR API, interoperability, or data-validation failures.

### SMART Scope Contract

The current authorization grant includes:

```text
fhirUser
openid
user/Encounter.rs
user/Observation.rs
user/Organization.rs
user/Patient.rs
user/Practitioner.rs
```

Automated tests validate both the presence of the expected SMART scopes and the runtime behavior of corresponding FHIR resource requests.

Observed runtime behavior:

| Resource     | SMART Scope Granted | Runtime Result |
| ------------ | ------------------- | -------------- |
| Patient      | Yes                 | HTTP 200       |
| Encounter    | Yes                 | HTTP 200       |
| Observation  | Yes                 | HTTP 200       |
| Organization | Yes                 | HTTP 403       |
| Practitioner | Yes                 | HTTP 403       |

Organization and Practitioner access are denied by the current EHR policy even though the corresponding SMART scopes are present in the authorization grant.

This demonstrates an important authorization boundary:

```text
Valid bearer token
        |
        v
Granted SMART scope
        |
        v
Underlying EHR / organization policy
        |
        v
Final resource-access decision
```

A granted OAuth/SMART scope does not necessarily imply unconditional access to the corresponding resource.

### SMART Discovery Contract

Automated tests validate the OpenEMR SMART discovery document at:

```text
/apis/default/fhir/.well-known/smart-configuration
```

Validation includes:

* discovery endpoint availability
* authorization endpoint advertisement
* token endpoint advertisement
* supported SMART scopes
* advertised capabilities
* expected endpoint host

The OpenEMR implementation currently advertises `scopes_supported` as a nested collection. The test harness normalizes the returned structure before evaluating the advertised scope contract.

Selected advertised capabilities include:

```text
launch-ehr
launch-standalone
client-confidential-symmetric
client-confidential-asymmetric
client-public
sso-openid-connect
permission-user
permission-patient
permission-offline
permission-v1
permission-v2
context-ehr-encounter
```

The discovery document also advertises resource-specific scopes for healthcare resources including Patient, Encounter, Observation, DiagnosticReport, Organization, Practitioner, ServiceRequest, Specimen, Procedure, and others.

---

## Automated Test Coverage

Current automated validation includes interoperability and security-oriented pytest suites covering:

```text
HL7 transport and acknowledgment
HL7 audit persistence
HL7 field validation
cross-segment semantic consistency
FHIR patient identity reconciliation
SMART authorization boundaries
token lifecycle behavior
SMART scope contracts
SMART discovery contracts
```

Authentication/security coverage currently includes 20 automated tests across:

```text
tests/security/test_fhir_authorization_boundaries.py
tests/security/test_fhir_token_lifecycle.py
tests/security/test_fhir_scope_contract.py
tests/security/test_smart_configuration_contract.py
```

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

### SMART on FHIR Authorization

[SMART on FHIR Authorization Validation](docs/validation/05-smart-fhir-authorization-validation.md)

This case study documents SMART discovery, OAuth authorization-code handling, bearer-token lifecycle validation, authentication boundaries, granted scopes, runtime resource authorization, and EHR policy constraints.

Evidence is maintained under:

```text
docs/validation/evidence/smart-auth/
```

---

## Current Engineering Focus

The project is intentionally moving away from accumulating unrelated technologies.

The current specialization is centered on:

* patient identity
* transaction integrity
* message identity versus business identity
* duplicate and replay behavior
* poison-message containment
* interface failure isolation
* stale and out-of-order updates
* source-to-target data lineage
* HL7-to-FHIR semantic fidelity
* persistence validation
* FHIR conformance
* authentication and authorization boundaries
* reliability and recovery

The next interoperability work extends the existing transaction-integrity model into controlled HL7 rejection/quarantine behavior, followed by patient-identity scenarios and laboratory-result workflows.

---

## Planned Reliability and Message-Containment Work

The next interface-reliability phase will validate that a defective transaction cannot prevent unrelated valid transactions from continuing through the integration pipeline.

Target behavior:

```text
Valid HL7
   |
   +--> validate --> accept --> persist --> ACK

Invalid HL7
   |
   +--> validate --> reject / quarantine
                       |
                       +--> preserve original message
                       +--> preserve message identity
                       +--> preserve validation failure
                       +--> prevent downstream poisoning

Next valid HL7
   |
   +--> continue processing normally
```

The goal is to validate deterministic containment and recovery rather than relying on manual service restoration after a defective transaction.

---

## Planned Patient Identity Scenarios

Future validation will progressively examine:

* assigning authorities
* duplicate patient identifiers
* demographic changes
* near demographic matches
* ambiguous identity
* duplicate patient creation
* legitimate updates
* stale updates
* out-of-order updates
* patient merge/link scenarios
* FHIR Patient search
* FHIR patient matching behavior

The intended end-to-end path is:

```text
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
```

---

## Planned Clinical Workflow Expansion

After the current ADT and reliability work, the lab will expand into additional healthcare interoperability workflows including:

* ORU laboratory results
* OBR / OBX field and semantic validation
* laboratory Observation reconciliation
* DiagnosticReport relationships
* ServiceRequest context
* Specimen relationships
* HL7-to-FHIR laboratory mapping
* VXU immunization messaging
* US Core validation
* additional patient-identity and MPI scenarios

Longer-term work may include DICOM/PACS and radiology workflow intersections where they naturally complement the interoperability-quality specialization.

---

## Background

The project builds upon healthcare IT experience involving:

* AHLTA
* CHCS
* HL7 v2
* eGate healthcare interfaces
* BEA Tuxedo middleware
* Oracle-backed healthcare systems
* Windows Server
* Linux / Unix systems
* IIS / ASP.NET application support
* enterprise production troubleshooting
* performance and reliability validation
* authenticated web-service load testing
* load and endurance testing
* release validation
* database analysis
* distributed healthcare-system operations

Modern interoperability technologies are introduced as extensions of those systems concepts rather than as disconnected technical exercises.

---

## Data Safety and Configuration Security

All clinical data used in this project is synthetic.

No PHI or real patient information is used.

Runtime credentials, OAuth access tokens, passwords, client secrets, and local configuration secrets are excluded from source control.

Temporary OAuth token material is stored outside the repository.

Authorization diagnostics deliberately avoid displaying bearer-token values.

Exported Mirth channel configuration uses placeholders such as:

```text
REPLACE_WITH_LOCAL_SECRET
```

instead of live credentials.

---

## Known Lab Constraints

This project is an engineering and validation lab rather than a production healthcare system.

Current constraints include:

* synthetic healthcare data only
* local containerized infrastructure
* self-signed TLS in the development environment
* certificate verification disabled for selected local validation calls
* OpenEMR-specific authorization-policy behavior
* no claim of production compliance certification

These limitations are documented so test results can be interpreted within the correct environment and scope.

---

## Project Status

**Active development — healthcare interoperability quality engineering specialization.**

Current validated areas include:

```text
HL7 ADT processing
MLLP transport
ACK correlation
field-level validation
cross-segment consistency
PostgreSQL audit persistence
failure and recovery
replay classification
payload integrity
FHIR patient reconciliation
SMART/OAuth authorization boundaries
token lifecycle validation
SMART scope contracts
SMART capability discovery
```

See [`docs/PROJECT_CHARTER.md`](docs/PROJECT_CHARTER.md) for the broader engineering objectives and methodology.
