# HL7 Replay, Transaction Identity, and Payload Integrity Validation

## Purpose

This validation exercise examines how an HL7 v2 interface behaves when the
same transaction identity is delivered more than once.

The implementation distinguishes between:

- first delivery of a logical HL7 transaction
- exact retransmission of the same transaction and payload
- conflicting reuse of the same transaction identity with different content
- individual receipt attempts
- logical transaction identity
- payload identity
- patient/business identity

The validation combines HL7 transport testing, Mirth transformation,
PostgreSQL transaction modeling, payload fingerprinting, direct SQL
reconciliation, controlled downstream failure testing, and automated pytest
regression coverage.

All patient identifiers and message content used in this lab are synthetic.

---

## System Under Test

The current validation path is:

    Synthetic HL7 ADT^A04
            |
            v
           MLLP
            |
            v
       Mirth Connect
            |
            +--> HL7 field extraction
            |
            +--> SHA-256 payload fingerprint
            |
            v
    PostgreSQL transaction classifier
            |
            +--> audit.interface_transactions
            |
            +--> audit.interface_messages
            |
            v
      pytest + direct SQL validation

Primary components:

- HL7 v2.5.1
- ADT^A04 registration message
- Mirth Connect 4.5.2
- MLLP transport
- PostgreSQL 16
- Python / pytest
- Docker Compose

---

## Identity Model

A central objective of this validation is to avoid treating all forms of
identity as equivalent.

### Audit Identity

`audit_id` identifies one observed receipt attempt.

Each delivery may legitimately produce a separate audit record even when the
underlying logical transaction has already been seen.

### Database Transaction Identity

`transaction_id` is a PostgreSQL-generated surrogate identifier for one
logical interface transaction.

It has database meaning but no HL7 or clinical meaning.

### HL7 Transaction Identity

The current laboratory transaction identity is:

    MSH-3  Sending Application
    MSH-4  Sending Facility
    MSH-10 Message Control ID

For the synthetic sender:

    Sending Application: LABSENDER
    Sending Facility:    INTEROPLAB

PostgreSQL enforces uniqueness on the combination:

    sending_application
    sending_facility
    message_control_id

This prevents multiple logical transaction rows from being created for the
same defined transaction identity.

### Payload Identity

Mirth calculates a SHA-256 digest from the inbound HL7 payload.

The 64-character digest provides a deterministic content fingerprint used to
compare later receipts claiming the same transaction identity.

### Patient / Business Identity

For the current ADT scenario, PID-3 carries patient identification
information.

Example synthetic identifiers:

    LAB000001
    LAB999999

Patient identity is intentionally separate from MSH-10.

The same patient may participate in many legitimate HL7 transactions.

---

## PostgreSQL Logical Transaction Model

Migration `003-logical-transaction-model.sql` introduced:

    audit.interface_transactions

The table records one row per logical transaction and includes:

    transaction_id
    sending_application
    sending_facility
    message_control_id
    canonical_payload_sha256
    first_received_at
    last_received_at
    receipt_count

The original receipt table:

    audit.interface_messages

continues to preserve each observed delivery attempt.

It now also contains:

    transaction_id
    attempt_outcome

This creates a one-to-many relationship:

    one logical transaction
            |
            +--> receipt attempt 1
            +--> receipt attempt 2
            +--> receipt attempt 3
            ...

Historical audit rows created before activation of the logical transaction
model were not retroactively assigned transaction IDs.

This avoids fabricating relationships that were not recorded at the time.

---

## Atomic Receipt Classification

Migration `004-record-interface-receipt-function.sql` introduced:

    audit.record_interface_receipt(...)

Mirth now passes the extracted message facts to this PostgreSQL function
instead of directly inserting an audit row.

The function receives:

    message control ID
    message type
    trigger event
    patient identifier
    sending application
    sending facility
    payload SHA-256

PostgreSQL then establishes or locates the logical transaction and classifies
the incoming receipt.

The classification outcomes are:

    FIRST_DELIVERY
    EXACT_REPLAY
    CONFLICTING_REUSE

The transaction uniqueness constraint remains the final authority for logical
transaction identity.

Existing transaction rows are locked during replay/conflict processing so
receipt metadata can be updated safely.

---

## First Delivery Contract

A transaction identity not previously observed produces:

    FIRST_DELIVERY

The first receipt:

- creates one logical transaction
- establishes the canonical SHA-256 payload fingerprint
- sets receipt_count to 1
- creates one receipt/audit row
- links the receipt to the logical transaction
- preserves the source patient identifier
- currently returns HL7 AA when processing succeeds

Conceptually:

    Logical Transaction X
        |
        +--> Receipt 1
             FIRST_DELIVERY

---

## Exact Replay Contract

An exact replay has:

    same sending application
    same sending facility
    same MSH-10
    same SHA-256

The interface classifies this condition as:

    EXACT_REPLAY

The second physical delivery does not create a second logical transaction.

Instead:

    Logical Transaction X
        |
        +--> Receipt 1
        |    FIRST_DELIVERY
        |
        +--> Receipt 2
             EXACT_REPLAY

The automated contract verifies that:

- transaction_id remains unchanged
- receipt_count increments
- canonical SHA-256 remains unchanged
- both receipt hashes match the canonical payload
- both receipts remain independently auditable

This distinction separates:

    duplicate receipt

from:

    duplicate logical transaction

---

## Conflicting Reuse Contract

A conflicting reuse has:

    same sending application
    same sending facility
    same MSH-10
    different SHA-256

The controlled test also changes PID-3 from:

    LAB000001

to:

    LAB999999

while retaining the original transaction identity.

The interface classifies this condition as:

    CONFLICTING_REUSE

The automated contract verifies that:

- transaction_id remains unchanged
- receipt_count increments
- the original canonical payload remains unchanged
- the conflicting receipt retains its own different SHA-256
- the conflicting patient identifier is preserved
- the conflict remains visible in audit history

Conceptually:

    Logical Transaction X
    Canonical payload = A
        |
        +--> Receipt 1
        |    Patient LAB000001
        |    Payload A
        |    FIRST_DELIVERY
        |
        +--> Receipt 2
             Patient LAB999999
             Payload B
             CONFLICTING_REUSE

The conflicting payload is evidence.

It is not allowed to redefine the canonical payload associated with the
original transaction.

---

## Detection Versus Enforcement

The current implementation deliberately separates conflict detection from
conflict enforcement.

Implemented now:

- FIRST_DELIVERY detection
- EXACT_REPLAY detection
- CONFLICTING_REUSE detection
- logical transaction correlation
- canonical payload preservation
- individual receipt preservation
- receipt counting
- automated regression testing
- source-to-target persistence validation

Not yet implemented:

- conflict-specific AE or AR policy
- quarantine workflow
- downstream business-effect suppression
- downstream OpenEMR write idempotency

At the current stage, a conflicting receipt can therefore be:

    attempt_outcome   = CONFLICTING_REUSE
    processing_status = PERSISTED
    HL7 ACK            = AA

`PERSISTED` currently means that the receipt and classification were
successfully recorded in the audit database.

It does not mean that a conflicting transaction has been approved as valid
clinical content.

Conflict enforcement will be introduced as a separate behavioral increment.

---

## Why Receipt History Is Preserved

Suppressing repeated rows entirely would lose useful operational evidence.

A reliable interface must distinguish between:

    one business transaction

and:

    multiple attempts to deliver that transaction

Receipt history can support analysis of:

- retry behavior
- lost acknowledgments
- interface latency
- downstream degradation
- sender retry policy
- repeated failures
- conflicting message identity reuse

For this reason, receipt attempts remain independently auditable even when
they belong to the same logical transaction.

---

## Retransmission as an Operational Signal

Retransmission is not automatically an error.

For example:

    sender transmits
          |
          v
    receiver processes
          |
          v
       ACK lost
          |
          v
    sender retransmits

An exact retransmission may therefore be expected reliability behavior.

However, an increase in replay frequency can also indicate a larger systems
problem such as:

- network interruption
- acknowledgment timeout
- database latency
- interface backlog
- downstream dependency degradation
- resource exhaustion
- service restart or failover behavior

Future observability work can derive metrics such as:

    total receipts
    unique logical transactions
    exact replay count
    conflict count
    replay rate
    ACK latency
    processing latency

A rising retransmission rate can therefore be treated as both a data-integrity
concern and a possible early operational warning signal.

---

## SHA-256 Payload Fingerprinting

The Mirth source transformer contains a JavaScript step named:

    audit_payload_sha256

The transformer calculates a SHA-256 digest from the inbound HL7 payload and
stores it in the Mirth channel map.

Migration `002-add-payload-sha256.sql` added:

    payload_sha256 VARCHAR(64)

to:

    audit.interface_messages

The logical transaction table stores:

    canonical_payload_sha256

The first accepted receipt establishes the canonical fingerprint.

Later receipts are compared against it.

An exact replay therefore satisfies:

    same transaction identity
    +
    same SHA-256

A conflicting reuse satisfies:

    same transaction identity
    +
    different SHA-256

---

## Source-to-Target Data Lineage Validation

The validation traces transaction data across system boundaries rather than
relying solely on transport success.

Current mappings include:

    HL7 source                   PostgreSQL target

    MSH-10        ------------>  message_control_id
    MSH-9.1       ------------>  message_type
    MSH-9.2       ------------>  trigger_event
    PID-3.1       ------------>  patient_identifier
    MSH-3         ------------>  sending_application
    MSH-4         ------------>  sending_facility
    HL7 payload   ------------>  payload_sha256

The validation path is:

    source HL7
        |
        v
    Mirth transformation
        |
        v
    SHA-256 instrumentation
        |
        v
    PostgreSQL transaction classification
        |
        v
    database persistence
        |
        v
    direct SQL reconciliation

This is **source-to-target data lineage validation**.

A successful HL7 acknowledgment alone is not considered sufficient evidence
that the expected transaction state was persisted correctly.

---

## Relationship to Failure and Recovery Testing

This validation extends the downstream reliability work documented in:

    docs/validation/03-hl7-mirth-audit-reliability-validation.md

The controlled failure/recovery test deliberately stops the downstream
PostgreSQL audit database while Mirth remains operational.

The automated test verifies:

- downstream persistence failure produces HL7 AE
- MSA-2 remains correlated with inbound MSH-10
- failed transactions are not falsely recorded as persisted
- PostgreSQL recovery is based on Docker health status
- processing resumes successfully after database recovery
- Mirth does not require restart for recovery

The logical transaction architecture preserves that behavior.

The transaction-integrity model therefore adds another reliability question:

    What happens when the sender retries after uncertainty or failure?

---

## Automated Regression Contract

The replay and conflict scenarios are now automated in:

    tests/interoperability/test_adt_a04_audit_persistence.py

Relevant tests include:

    test_adt_a04_persists_audit_row_and_returns_aa

    test_adt_a04_downstream_failure_and_recovery

    test_duplicate_adt_a04_replay_is_classified_as_exact_replay

    test_same_message_identity_with_different_payload_is_classified_as_conflict

Together they validate:

    normal delivery
        -> AA
        -> FIRST_DELIVERY
        -> persistence

    downstream database failure
        -> AE
        -> no false persistence

    database recovery
        -> AA
        -> processing resumes

    exact replay
        -> same logical transaction
        -> EXACT_REPLAY
        -> canonical state preserved

    conflicting reuse
        -> same logical transaction
        -> CONFLICTING_REUSE
        -> conflicting evidence preserved
        -> canonical state preserved

A full interoperability regression run on 2026-08-18 produced:

    9 passed

The SMART/FHIR patient reconciliation test requires a fresh OAuth access
token. An expired token is intentionally reported as an authentication
prerequisite failure rather than being misclassified as a patient-data
reconciliation failure.

The local OpenEMR environment currently uses a self-signed HTTPS certificate,
so the FHIR test also reports the expected local TLS verification warning.

---

## Transaction Identity Lifetime Assumption

For the current laboratory model:

    sending application
    +
    sending facility
    +
    MSH-10

remains a unique logical transaction identity for the life of the audit
database.

A production interface may define a different retention or message-control-ID
reuse policy.

That policy would need to come from the applicable interface specification,
vendor behavior, or enterprise integration architecture.

The laboratory assumption is therefore explicit rather than implicit.

---

## Secure Configuration Management

The running Mirth Database Writer requires a local PostgreSQL credential.

The source-controlled Mirth channel export contains:

    REPLACE_WITH_LOCAL_SECRET

instead of the runtime password.

No runtime database credential is intentionally stored in Git.

The tracked channel configuration now calls:

    audit.record_interface_receipt(...)

rather than directly inserting into:

    audit.interface_messages

This keeps the source-controlled Mirth configuration aligned with the
validated runtime behavior.

---

## Current Engineering Findings

The current implementation demonstrates that:

1. A successful HL7 AA alone does not prove correct transaction semantics.
2. Physical receipt identity and logical transaction identity are different.
3. MSH-10 must not be confused with patient or other healthcare business identity.
4. SHA-256 provides deterministic evidence for distinguishing exact replay from conflicting content.
5. Exact retransmission can be correlated to one logical transaction while preserving every receipt attempt.
6. Conflicting payloads can be retained as evidence without overwriting canonical transaction state.
7. PostgreSQL constraints provide an authoritative transaction-identity boundary.
8. Receipt/audit history and downstream business effects are separate concerns.
9. Controlled failure/recovery behavior remains testable alongside replay classification.
10. Source-to-target reconciliation provides stronger evidence than transport success alone.

---

## Next Engineering Contract

The next transaction-integrity increment will focus on enforcement behavior.

### Exact Replay

The system already identifies:

    same transaction identity
    +
    same SHA-256

as:

    EXACT_REPLAY

Future downstream business processing must ensure that replay does not create
an unintended duplicate business effect.

### Conflicting Reuse

The system already identifies:

    same transaction identity
    +
    different SHA-256

as:

    CONFLICTING_REUSE

The next enforcement phase will determine and test an explicit policy such as:

    preserve receipt evidence
    +
    prevent conflicting business processing
    +
    produce visible failure or quarantine behavior

The ACK policy will be tested independently rather than assumed.

### Legitimate Later Update

A legitimate later transaction may have:

    new MSH-10
    +
    same healthcare business identifier
    +
    new state

That must remain distinct from retransmission.

### Stale / Out-of-Order Update

Later validation will examine whether an older business-state update arriving
after a newer update can incorrectly regress downstream state.

---

## Longer-Term Direction

The transaction-integrity model will become part of a broader healthcare
interoperability quality-engineering workflow:

    HL7 v2
        |
        v
      Mirth
        |
        v
    transaction integrity
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

Future scenarios include:

- assigning-authority behavior
- duplicate patient records
- demographic changes
- ambiguous patient identity
- FHIR Patient search and matching
- legitimate patient updates
- stale and out-of-order updates
- retry behavior and replay observability
- downstream service failure
- authorization failure
- FHIR profile and conformance validation

---

## Engineering Direction

The objective of this lab is not simply to accumulate interoperability
technologies.

The specialization is healthcare interoperability quality engineering with
particular emphasis on:

- patient identity
- transaction integrity
- source-to-target data lineage
- HL7 and FHIR semantic fidelity
- persistence validation
- failure and recovery behavior
- deterministic automated testing
- operational observability

The goal is to validate not merely whether healthcare information was
transmitted, but whether it arrived at the correct destination, retained its
intended meaning, created the expected persisted state, and behaved safely
under retry, replay, failure, recovery, and conflicting-data conditions.

---

## Validation Evidence

The following screenshots provide visual evidence of the transaction-integrity
and payload-fingerprinting work.

### Mirth SHA-256 Payload Transformer

The Mirth `ADT_A04_IN` source transformer includes the
`audit_payload_sha256` JavaScript step alongside the HL7 field-mapping steps.

![Mirth SHA-256 payload transformer](../images/hl7-replay/mirth-payload-sha256-transformer.png)

### PostgreSQL Payload Fingerprint Persistence

A successfully processed synthetic ADT transaction was queried directly from
PostgreSQL after SHA-256 instrumentation was enabled.

![PostgreSQL SHA-256 persistence validation](../images/hl7-replay/postgres-payload-sha256-validation.png)

### Exact Replay Versus Conflicting Reuse

Direct SQL evidence demonstrates that identical payloads produce identical
fingerprints while conflicting content produces a different fingerprint.

![Exact replay versus conflicting reuse](../images/hl7-replay/postgres-replay-vs-conflict.png)

### Controlled Downstream Failure Evidence

The Mirth dashboard captured expected Database Writer errors during deliberate
PostgreSQL dependency interruption.

![Mirth controlled downstream failure evidence](../images/hl7-replay/mirth-downstream-failure-evidence.png)

---

## Evidence Summary

Evidence is gathered from multiple layers:

    Automated test evidence
        pytest assertions and controlled scenarios

    Interface evidence
        Mirth transformation and ACK behavior

    Persistence evidence
        PostgreSQL transaction and receipt reconciliation

    Operational evidence
        controlled downstream failure and recovery

Together these provide stronger assurance than relying on any single layer
such as an HL7 acknowledgment, application log, or database row alone.
