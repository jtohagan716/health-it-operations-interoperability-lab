# Radiology Interoperability Workflow

## Overview

This workflow demonstrates end-to-end healthcare imaging interoperability across HL7 v2, Mirth Connect, PostgreSQL, DICOM, and Orthanc PACS.

The goal is not simply to prove that an HL7 message can be accepted or that a DICOM object can be stored.

The goal is to validate whether one synthetic clinical imaging case preserves its identity and meaning across multiple protocols, applications, persistence layers, and reconciliation boundaries.

All patient data used in this workflow is synthetic.

---

## End-to-End Workflow

```text
Synthetic Radiology Order
        |
        | HL7 ORM^O01
        | TCP / MLLP
        v
+-------------------+
|   Mirth Connect   |
+-------------------+
        |
        | HL7 validation
        | ACK correlation
        | transaction fingerprinting
        v
+----------------------------+
| PostgreSQL                 |
|                            |
| audit.interface_transactions
| audit.orm_orders           |
+----------------------------+
        |
        | same patient
        | same order
        | same accession
        | same procedure
        v
+-------------------+
|   DICOM Object    |
+-------------------+
        |
        | DICOM C-STORE
        v
+-------------------+
|   Orthanc PACS    |
+-------------------+
        |
        | Patient ID
        | Accession Number
        | Study Instance UID
        | Study Description
        | Modality
        v
+-------------------+
| Radiology Result  |
|    HL7 ORU        |
+-------------------+
        |
        v
+----------------------------+
| Radiology Lineage          |
| ORM -> DICOM -> ORU        |
+----------------------------+
        |
        v
+----------------------------+
| audit.radiology_workflows  |
+----------------------------+
        |
        | live Orthanc reconciliation
        v
+----------------------------+
| MATCHED / RECONCILED       |
+----------------------------+

Clinical Identity Contract

The workflow uses several identifiers together rather than assuming that successful transport proves clinical correlation.

The primary lineage contract includes:

Domain	Identity or Meaning
HL7 ORM	Patient identifier
HL7 ORM	Placer order number
HL7 ORM	Filler order / accession number
HL7 ORM	Procedure code
HL7 ORM	Procedure description
DICOM	Patient ID
DICOM	Accession Number
DICOM	Study Instance UID
DICOM	Study Description
DICOM	Modality
HL7 ORU	Patient identifier
HL7 ORU	Order identity
HL7 ORU	Accession identity
HL7 ORU	Final report status
HL7 ORU	Radiology impression

A workflow is considered successfully correlated only when the expected identities and clinical semantics remain consistent across these boundaries.

Canonical Synthetic Workflow

The persistent demonstration case uses:

Patient ID:          RADPAT000001
Placer Order:        RADORD000001
Accession Number:    RAD000001
Procedure Code:      XRCH2
Procedure:           Chest X-ray 2 Views
Modality:            DX
Report Status:       F
Impression:          No acute cardiopulmonary abnormality.

The corresponding DICOM study uses a stable Study Instance UID so the source object can be reconciled against the study stored in Orthanc.

HL7 ORM Runtime Processing

The imaging order is represented as an HL7 v2.5.1 ORM^O01 message.

The message enters Mirth Connect through a TCP/MLLP listener.

Runtime validation includes:

expected message type and trigger event
MSH-10 message control identity
patient identity
order identity
accession identity
procedure code and description
HL7 version
receiving application
acknowledgment behavior

Successful processing must return an HL7 AA acknowledgment.

The returned MSA-2 value must correlate to the inbound MSH-10 message control ID.

Transport success alone is therefore insufficient.

Interface Transaction Persistence

Mirth persists transaction evidence into PostgreSQL.

The interface transaction layer records information including:

sending application
sending facility
message control ID
canonical payload SHA-256
receipt count

The normalized imaging-order layer records information including:

patient identifier
placer order number
filler order number
accession number
order control
order status
procedure code
procedure description

This allows the test harness to independently verify both transport-level transaction state and business-level order state.

Replay and Conflicting Identity Protection

The ORM runtime tests distinguish an exact replay from conflicting message-control-ID reuse.

Conceptually:

same interface identity
+ same canonical payload fingerprint
= exact replay

while:

same interface identity
+ different canonical payload fingerprint
= conflicting reuse

Exact replay reuses the canonical transaction state.

Conflicting reuse is rejected rather than silently overwriting or ambiguously duplicating the existing transaction.

This protects deterministic transaction identity across retries and reprocessing.

DICOM Generation and C-STORE

A matching DICOM object is generated for the same synthetic imaging workflow.

The DICOM identity includes:

PatientID
AccessionNumber
StudyInstanceUID
SeriesInstanceUID
SOPInstanceUID
StudyDescription
Modality

The object is transmitted to Orthanc through a real DICOM association using C-STORE.

The acceptance test requires:

association established
C-STORE response status = 0x0000

This verifies actual DICOM transport rather than inserting PACS metadata directly through a database or test shortcut.

Orthanc Runtime Verification

After C-STORE, the test queries the live Orthanc REST API.

Study-level verification includes:

PatientID
AccessionNumber
StudyInstanceUID
StudyDescription

Series-level verification includes:

Modality

Modality is validated at the series level because that is where the relevant Orthanc DICOM metadata is represented for this workflow.

ORM to DICOM to ORU Lineage

The radiology lineage validator parses and correlates:

ORM order
   |
   v
DICOM study
   |
   v
ORU result

The processing model is:

parse
  |
  v
validate
  |
  v
establish identity
  |
  v
detect replay or conflict
  |
  v
persist

The workflow is persisted only after the clinical identities and expected semantics have been validated.

Radiology Workflow Persistence

Validated workflows are stored in:

audit.radiology_workflows

Persisted lineage includes:

patient_identifier
placer_order_number
accession_number
procedure_code
procedure_text
study_instance_uid
modality
oru_message_control_id
report_status
impression
lineage_status

The canonical successful lineage state is:

MATCHED

Accession Number and Study Instance UID are used as key imaging identities when detecting existing workflow state.

Reuse of those identities with conflicting clinical data is rejected.

Live PACS Reconciliation

Persistence does not complete the acceptance contract.

The persisted workflow is subsequently reconciled against the study actually stored in Orthanc.

The reconciliation checks:

patient ID preserved
accession number preserved
Study Instance UID preserved
study description preserved
modality preserved

If every check passes:

pacs_reconciliation_status = RECONCILED

The Orthanc study identifier and reconciliation timestamp are persisted.

If reconciliation fails:

pacs_reconciliation_status = FAILED

Diagnostic failure detail is retained.

This distinguishes successful database persistence from verified agreement with the downstream PACS.

End-to-End Runtime Acceptance Test

The principal runtime acceptance contract is:

tests/interoperability/test_radiology_runtime_acceptance.py

For every execution, the test generates a unique synthetic clinical case.

The test verifies:

ORM enters Mirth through TCP/MLLP.
Mirth returns AA.
MSH-10 and MSA-2 remain correlated.
Interface transaction state is persisted.
Normalized ORM business state is persisted.
Patient, order, accession, and procedure identity are correct.
A matching DICOM object is generated.
The object enters Orthanc through DICOM C-STORE.
Live Orthanc metadata preserves the expected imaging identity.
A matching final ORU result participates in lineage validation.
ORM, DICOM, and ORU lineage is persisted.
The persisted workflow is reconciled against live Orthanc.
PACS state becomes RECONCILED.
PostgreSQL independently proves that the Mirth ORM record and radiology workflow describe the same clinical case.
Test cleanup removes only state owned by that test execution.

The acceptance test therefore validates more than endpoint availability.

It validates:

transport
+ acknowledgment
+ persistence
+ identity preservation
+ semantic correlation
+ PACS storage
+ downstream reconciliation
+ deterministic cleanup
Automated Regression Coverage

The radiology interoperability suite currently contains 19 automated tests.

Coverage includes:

ORM-to-DICOM identity validation
ORM-to-DICOM-to-ORU lineage
patient identity preservation
order and accession preservation
procedure identity preservation
final result and impression validation
negative accession mismatch rejection
lineage persistence
idempotent persistence
conflicting workflow identity rejection
Mirth ORM runtime processing
exact replay handling
conflicting message-control-ID reuse rejection
Mirth order-to-radiology workflow linkage
live Orthanc reconciliation
successful PACS reconciliation persistence
failed PACS reconciliation state
test isolation
complete end-to-end runtime acceptance

Latest acceptance checkpoint:

19 passed
Test Isolation and Persistent Evidence

Runtime acceptance tests generate unique synthetic identities for each execution.

Examples include unique:

patient identifiers
message control IDs
placer order numbers
accession numbers
Study Instance UIDs
Series Instance UIDs
SOP Instance UIDs

Cleanup follows a strict ownership rule:

Tests may delete only data they created.

This prevents automated regression tests from deleting persistent demonstration records or unrelated runtime state.

The persistent canonical demonstration record remained intact after the full radiology regression:

RADPAT000001 | RAD000001 | MATCHED | RECONCILED

This provides an additional acceptance property:

new functionality works
+
existing regression remains green
+
persistent evidence remains intact
Failure-Oriented Validation

The radiology suite deliberately tests conditions that should not be accepted silently.

Examples include:

DICOM accession mismatch
conflicting radiology identity reuse
conflicting HL7 message-control-ID reuse
PACS reconciliation failure

These tests are important because healthcare integration reliability depends on identifying incorrect correlation, not merely proving successful paths.

A technically successful transmission with incorrect patient, order, accession, study, or result correlation is an interoperability failure.

Related DICOM and PACS Engineering

The repository also contains broader PACS engineering work covering:

Orthanc operational validation
DICOM C-STORE
C-FIND
C-MOVE
AE authorization behavior
remote modality configuration
metadata-driven routing
downstream Storage SCP behavior
destination failure
recovery and retry
operator troubleshooting

See:

pacs-operator-troubleshooting-runbook.md
case-study-dicom-autorouting-failure-recovery.md
evidence/dicom/
Engineering Significance

This workflow demonstrates the distinction between several levels of integration success.

Port open
    !=
Message accepted
    !=
Message acknowledged correctly
    !=
Order persisted correctly
    !=
Image stored correctly
    !=
Clinical identities correlated correctly
    !=
Result correlated correctly
    !=
Downstream PACS reconciled correctly

Reliable healthcare interoperability requires evidence across those boundaries.

The radiology workflow therefore emphasizes:

deterministic behavior
patient and transaction identity
cross-system correlation
protocol-level validation
source-to-target lineage
replay safety
conflict detection
failure visibility
downstream reconciliation
non-destructive automated testing
operational evidence

The final acceptance criterion is not simply that every component is running.

It is that the same clinical imaging case remains identifiable, internally consistent, and verifiably reconciled from order through PACS.