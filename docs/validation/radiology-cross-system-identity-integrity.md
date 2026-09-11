Radiology Cross-System Identity Integrity Validation

Purpose

This validation demonstrates patient-safe ownership of radiology accession
numbers across HL7 ORM order processing and downstream radiology workflow
persistence.

The control prevents an accession number already associated with one patient,
placer order, and procedure from being silently reused by a conflicting
clinical identity.

Systems under test

Mirth Connect ORM_O01_IN channel

PostgreSQL interoperability audit database

Python radiology lineage persistence

HL7 v2.5.1 ORM^O01 messaging over MLLP

Pytest unit, contract, persistence, and runtime tests

All patients, orders, accessions, and clinical data used in this validation are
synthetic.

Initial discrepancy

Two independent synthetic fixture families reused the same radiology identity:

Field

ORM order fixture

Canonical radiology workflow

Patient identifier

LAB000001

RADPAT000001

Placer order number

RADORD000001

RADORD000001

Accession number

RAD000001

RAD000001

Procedure

XRCH2

XRCH2

The interoperability database consequently contained two ORM owners for one
accession:

ORM order

Message control ID

Patient

Accession

1

RAD-ORM-000001

LAB000001

RAD000001

32

RAD-ORM-WORKFLOW-000001

RADPAT000001

RAD000001

A duplicate-accession query confirmed that RAD000001 was associated with two
distinct patients.

Root cause

The mismatch originated in the laboratory's synthetic test-data design.
Separate fixture families reused the same order and accession namespace while
assigning the records to different patients.

The individual messages were structurally valid. Existing validation checked
the internal consistency of each message or radiology bundle, but no shared
persistence boundary enforced authoritative accession ownership across
transactions.

This was not identified as an OpenEMR, Mirth Connect, Orthanc, or DICOM defect.

Safety risk

An accession number is a primary correlation identifier connecting an imaging
order, acquired study, PACS record, and diagnostic report.

Allowing one accession to represent multiple patients creates a risk that a
valid image or report could be attached to the wrong clinical record even
though every individual message remains syntactically valid.

The required invariant is:

One accession may have multiple lifecycle records, but all records must agree
on patient, placer order, and procedure ownership.

Remediation

Application-level lineage guard

scripts/radiology/persist_lineage.py now resolves persisted ORM ownership
before writing a downstream radiology workflow.

The guard:

Looks up every ORM row for the proposed accession.

Allows no-owner standalone scenarios for backward compatibility.

Allows multiple lifecycle rows only when their ownership identities agree.

Rejects ambiguous historical ownership.

Compares the authoritative ORM patient, placer order, accession, and
procedure with the proposed ORM/DICOM/ORU workflow.

Fails before downstream workflow persistence when the identities disagree.

The no-owner behavior is an explicit compatibility decision. This increment
prevents contradictions when an authoritative ORM exists; it does not require
every isolated radiology scenario to have a preceding ORM transaction.

Database ownership boundary

Migration
infrastructure/mirth/interop-db/init/024-orm-accession-ownership.sql
adds:

Function audit.enforce_orm_accession_ownership()

Trigger trg_enforce_orm_accession_ownership

Enforcement on inserts and relevant ownership updates

SQLSTATE 23514 for conflicting ownership

Transaction-scoped advisory locking for concurrent accession claims

An exact-transaction replay exception preserving idempotent recovery

The database is the final enforcement boundary. A caller cannot bypass the
ownership invariant by omitting the Python lineage workflow.

Historical data handling

The migration prevents new ownership conflicts but does not silently delete or
rewrite historical records.

Existing ambiguity for RAD000001 remains detectable by the application-level
guard and can be handled through an explicit data-remediation decision with
preserved provenance.

Live runtime experiment

Two independently traceable ORM messages were generated.

Both messages were structurally valid and used:

Placer order: RADORDOWN13474229

Accession: RADOWN13474229

Procedure: XRCH2

They differed in patient ownership:

Message

Control ID

Patient

Legitimate owner

RAD-OWNER-A-13474229

LAB000001

Conflicting claimant

RAD-OWNER-B-13474229

WRONG13474229

Legitimate ownership claim

The first message received:

MSA|AA|RAD-OWNER-A-13474229|Message accepted.

Mirth recorded:

validation_status=PASS
outcome=FIRST_DELIVERY
rows_inserted=1
destination_error=false
ack_code=AA

Conflicting ownership claim

The second message also passed structural ORM validation, but PostgreSQL
rejected its business persistence:

ERROR: ORM accession ownership conflict:
accession 'RADOWN13474229' is already owned by patient 'LAB000001',
placer order 'RADORDOWN13474229', procedure 'XRCH2';
attempted patient 'WRONG13474229',
placer order 'RADORDOWN13474229', procedure 'XRCH2'

Mirth propagated the destination failure as:

MSA|AE|RAD-OWNER-B-13474229|Message processing error.

This distinguishes valid transport and syntax from unsafe clinical ownership.

Final database state

The final audit.orm_orders query returned exactly one business row:

Field

Value

ORM order ID

120

Transaction ID

472

Message control ID

RAD-OWNER-A-13474229

Patient identifier

LAB000001

Placer order

RADORDOWN13474229

Accession

RADOWN13474229

Procedure

XRCH2

No ORM business row was persisted for the conflicting patient.

Both receipt attempts remained independently traceable in
audit.interface_transactions:

Transaction

Control ID

Receipt count

472

RAD-OWNER-A-13474229

1

473

RAD-OWNER-B-13474229

1

Each transaction retained its own canonical SHA-256 payload hash. The rejected
message was therefore auditable without becoming an accepted clinical order.

Replay validation

After installing the trigger, an exact replay of the existing
RAD-ORM-000001 message received:

MSA|AA|RAD-ORM-000001|Exact replay accepted.

This proves that ownership enforcement did not break the established
idempotent replay and recovery contract.

Automated validation

Focused ownership, persistence, and linkage suite:

python -m pytest -q `
    .\tests\interoperability\test_orm_accession_ownership_migration_contract.py `
    .\tests\interoperability\test_radiology_orm_ownership.py `
    .\tests\interoperability\test_orm_o01_audit_persistence.py `
    .\tests\interoperability\test_radiology_lineage_persistence.py `
    .\tests\interoperability\test_radiology_mirth_order_workflow_linkage.py

Result:

18 passed in 31.29s

The live conflicting-owner runtime test was also executed three consecutive
times:

1 passed, 4 deselected in 17.23s
1 passed, 4 deselected in 3.68s
1 passed, 4 deselected in 4.21s

Every run produced the same functional outcome and removed its UUID-scoped
database state.

Cleanup verification:

remaining_transactions | 0
remaining_orders       | 0

Broader radiology, ORM, PACS, and DICOM regression suite:

python -m pytest -q `
    .\tests\interoperability `
    -k "radiology or orm or pacs or dicom"

Results across repeated executions:

83 passed, 188 deselected in 143.28s
83 passed, 188 deselected in 92.63s
84 passed, 188 deselected in 60.78s

Python compilation and Git whitespace validation completed without errors.

Outcome

The system now separates four important facts:

A message was received.

The message was structurally valid.

The message was independently auditable.

Its clinical ownership was safe to persist.

A structurally valid ORM message can therefore be retained as receipt evidence
while being rejected from canonical clinical order state when it conflicts
with an established accession owner.

This provides defense in depth across Python workflow validation, PostgreSQL
integrity enforcement, Mirth destination-error handling, HL7 acknowledgement
semantics, and automated regression testing.
