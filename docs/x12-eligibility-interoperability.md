# X12 270/271 Eligibility Interoperability

## Purpose

This vertical slice demonstrates production-style handling of synthetic
X12 healthcare eligibility transactions in the
Health IT Operations & Interoperability Lab.

The implementation focuses on interoperability engineering concerns rather
than EDI parsing alone:

- X12 270 Eligibility Inquiry validation
- X12 271 Eligibility Response validation
- envelope control validation
- business-data extraction
- PostgreSQL persistence
- request/response correlation
- member-identity validation
- payload fingerprinting
- duplicate-delivery detection
- deterministic replay handling
- conflicting transaction reuse detection
- immutable canonical business state
- auditable receipt history
- automated Pytest validation

All X12 data in this repository is synthetic lab data.

This project demonstrates hands-on portfolio/lab experience and does not
represent prior production X12 experience.

---

## Operational Model

The implemented flow is:

```text
X12 270 Eligibility Inquiry
        |
        v
Envelope Validation
        |
        v
Business Data Extraction
        |
        v
SHA-256 Payload Fingerprint
        |
        v
PostgreSQL Persistence
        |
        v
X12 271 Eligibility Response
        |
        v
Envelope Validation
        |
        v
Business Data Extraction
        |
        v
PostgreSQL Persistence
        |
        v
270 <-> 271 Correlation
        |
        v
Identity / Data-Integrity Validation

PostgreSQL provides the operational audit trail for the transaction
lifecycle.

X12 270 Eligibility Inquiry

The 270 implementation validates X12 envelope integrity and extracts
eligibility business data.

Validated envelope relationships include:

ISA13 <-> IEA02 interchange control number
GS06 <-> GE02 functional-group control number
ST02 <-> SE02 transaction-set control number

Business data includes:

payer
provider
subscriber/member identifier
trace number
eligibility date
benefit code

Invalid transactions are rejected before persistence when required
control or business data is inconsistent or missing.

Examples covered by automated tests include:

mismatched ISA/IEA control numbers
mismatched GS/GE control numbers
mismatched ST/SE control numbers
missing subscriber member ID
missing eligibility date
X12 271 Eligibility Response

The 271 implementation validates the response envelope and extracts
eligibility response data.

The response is persisted independently before correlation with its
corresponding 270 request.

Relevant business information includes:

trace number
member identifier
payer
provider
eligibility date
benefit code
eligibility response/status
270 to 271 Correlation

A 271 response is not considered related to a 270 merely because both
transactions exist.

The lab explicitly correlates the request and response.

Correlation includes validation of transaction relationships and
member identity.

Example:

270
Trace:  ELIGREQ0001
Member: MEMBER1001

271
Trace:  ELIGREQ0001
Member: MEMBER1001

Result:
MATCHED / CORRELATED

A response with the expected trace relationship but an inconsistent
member is rejected from correlation:

270
Trace:  ELIGREQ0001
Member: MEMBER1001

271
Trace:  ELIGREQ0001
Member: MEMBER9999

Result:
REJECTED FROM CORRELATION

The incorrectly matched response remains independently persisted and
auditable rather than being silently discarded.

This distinction is important operationally: receiving a message and
successfully correlating that message to another business transaction
are separate events.

Canonical Transaction State

In this project, a canonical transaction means the single
authoritative PostgreSQL record representing one logical X12
transaction.

For example, if the same 270 is physically delivered twice, the system
should not create two authoritative eligibility requests.

Instead:

Physical delivery #1
        |
        v
Canonical X12 transaction
        ^
        |
Physical delivery #2

Both deliveries remain observable, but they reference the same
authoritative transaction when the second payload is an exact replay.

This prevents duplicate business state while retaining operational
evidence about what the interface actually received.

Receipt Classification

Every accepted delivery attempt is classified by PostgreSQL through:

audit.record_x12_receipt(...)

Supported classifications are:

FIRST_DELIVERY
EXACT_REPLAY
CONFLICTING_REUSE

Receipt evidence is stored separately from canonical transaction state.

This allows the system to distinguish:

How many logical transactions exist?

from:

How many times was a transaction physically received?

Those are not necessarily the same number.

FIRST_DELIVERY

A previously unseen logical transaction identity is classified as:

FIRST_DELIVERY

Expected behavior:

Create canonical transaction
        |
        +--> Create eligibility business row
        |
        +--> Create receipt row

The canonical transaction becomes the authoritative representation of
that logical X12 transaction.

EXACT_REPLAY

An exact replay occurs when:

same logical transaction identity
+
same SHA-256 payload fingerprint

Expected behavior:

Existing canonical transaction
        |
        +--> Reuse same x12_transaction_id
        |
        +--> Increment receipt_count
        |
        +--> Record EXACT_REPLAY receipt
        |
        X
   Do not create duplicate eligibility business state

Example:

Delivery 1 -> Transaction 42 -> FIRST_DELIVERY
Delivery 2 -> Transaction 42 -> EXACT_REPLAY

The second physical delivery therefore does not become a second
eligibility request.

This is idempotent processing: repeating the same valid operation does
not create additional business state.

CONFLICTING_REUSE

Conflicting reuse occurs when a payload claims the same logical X12
transaction identity as an existing transaction but its payload
fingerprint differs.

Example:

Original transaction
Trace:  TEST123
Member: MEMBER1001

Later delivery
Trace:  TEST123
Member: MEMBER9999

The second message claims to represent the same logical transaction,
but its content has changed.

Expected behavior:

Preserve receipt
        |
        v
CONFLICTING_REUSE
        |
        v
Reject processing
        |
        X
Do not overwrite canonical business state

The original authoritative member remains:

MEMBER1001

The conflicting payload is retained as operational evidence but cannot
silently mutate the accepted business transaction.

Payload Fingerprinting

Each raw X12 payload is fingerprinted using SHA-256.

The fingerprint allows the persistence layer to distinguish an
identical retransmission from reuse of an existing transaction identity
with different content.

Conceptually:

Logical identity already exists?
        |
       No
        |
        v
FIRST_DELIVERY


Logical identity already exists?
        |
       Yes
        |
        v
SHA-256 matches existing payload?
        |
     +--+--+
     |     |
    Yes    No
     |     |
     v     v
 EXACT   CONFLICTING
 REPLAY    REUSE
PostgreSQL Audit Model

The X12 vertical slice uses the following audit tables:

audit.x12_transactions
audit.x12_eligibility
audit.x12_correlations
audit.x12_receipts
x12_transactions

Stores the canonical transaction record.

Relevant concepts include:

X12 transaction type
envelope/control identity
sender and receiver
trace number
payload SHA-256
processing status
receipt count
last received timestamp
x12_eligibility

Stores eligibility-specific business data associated with the canonical
transaction.

Exact replays and conflicting reuse attempts do not create duplicate
eligibility rows.

x12_correlations

Stores validated relationships between 270 requests and 271 responses.

x12_receipts

Stores evidence of each physical delivery attempt.

Receipt outcomes include:

FIRST_DELIVERY
EXACT_REPLAY
CONFLICTING_REUSE

This separation between transaction state and receipt history provides
both data integrity and operational auditability.

Database Migrations

The X12 PostgreSQL implementation was introduced incrementally:

013-x12-eligibility-schema.sql
        |
        v
Canonical X12 transaction and eligibility persistence

014-x12-eligibility-correlation.sql
        |
        v
270 <-> 271 request/response correlation

015-x12-receipt-classification.sql
        |
        v
FIRST_DELIVERY / EXACT_REPLAY / CONFLICTING_REUSE

This progression intentionally separates basic persistence,
transaction correlation, and reliability behavior.

Synthetic Fixtures

X12 fixtures are stored under:

fixtures/x12/eligibility/

Current fixtures include:

270-valid.edi
270-invalid-gs-ge-control.edi
270-invalid-isa-iea-control.edi
270-invalid-missing-eligibility-date.edi
270-invalid-missing-member-id.edi
270-invalid-st-control.edi

271-valid.edi
271-invalid-wrong-member.edi
271-wrong-member-independent.edi

Automated replay tests derive temporary deterministic transactions from
the valid 270 fixture rather than persisting the historical fixture
identity repeatedly.

Automated Tests

The X12 suite includes:

test_270_envelope_validation.py
test_271_response_validation.py
test_270_271_correlation.py
test_eligibility_persistence_and_correlation.py
test_x12_receipt_classification.py

The receipt-classification tests explicitly demonstrate:

Exact replay
first_id == second_id
receipt_count == 2
receipt rows == 2
eligibility rows == 1

Receipt outcomes:
FIRST_DELIVERY
EXACT_REPLAY
Conflicting reuse
same logical identity
different payload
        |
        v
RuntimeError

while preserving:

receipt_count == 2
receipt rows == 2
eligibility rows == 1

Receipt outcomes:
FIRST_DELIVERY
CONFLICTING_REUSE

Canonical member:
MEMBER1001
Current Regression Baseline

The completed X12 vertical slice currently passes:

15 passed

Run the suite from the repository root with:

python -m pytest tests/x12 -v

The test suite is designed to validate deterministic behavior and clean
up synthetic replay-test state after execution.

Reliability Engineering Lessons Demonstrated

This slice intentionally exercises several concerns common to
production healthcare interfaces:

Validation before persistence

Invalid envelope or required business data is rejected before being
treated as trusted business state.

Correlation is explicit

A request and response are not assumed to belong together merely
because both were received.

Business identity is protected

Member mismatches prevent incorrect request/response association.

Physical delivery is separated from logical transaction state

Multiple receipts do not necessarily mean multiple business
transactions.

Exact replay is idempotent

Reprocessing an identical delivery does not duplicate business
state.

Conflicting reuse is fail-safe

A transaction identity cannot silently be reused to overwrite
previously accepted business information.

Audit evidence is preserved

Replays and conflicts remain observable even when they do not create
new canonical business state.

Testing is deterministic

Automated reliability tests use controlled identities and cleanup so
results can be reproduced.

Scope Boundary

This implementation is intentionally a focused X12 eligibility vertical
slice.

The goal is not to build a complete EDI platform or comprehensive X12
implementation.

The next project focus returns to the larger interconnected clinical
workflow:

Patient
  |
  v
HL7 ADT Registration
  |
  v
HL7 ORM Imaging Order
  |
  v
Mirth Connect
Validation / Routing / Transformation
  |
  v
DICOM Workflow
  |
  v
Orthanc / PACS
  |
  v
HL7 ORU Radiology Result
  |
  v
EHR / Downstream System
  |
  v
FHIR where appropriate

Across that workflow the lab will continue applying the same operational
principles demonstrated by the X12 slice:

transaction correlation
source-to-target reconciliation
identity integrity
auditability
quarantine
failure detection
deterministic replay/recovery
duplicate-safe processing
automated validation
operational evidence