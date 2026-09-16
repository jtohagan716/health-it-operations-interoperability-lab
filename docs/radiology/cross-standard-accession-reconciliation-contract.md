# Cross-Standard Accession Reconciliation Contract

## Purpose

This contract defines deterministic reconciliation of one synthetic
radiology workflow across an accepted HL7 ORM order, its DICOM
Modality Worklist projection, the resulting study in Orthanc/PACS,
and the final HL7 ORU radiology report.

This is a controlled synthetic laboratory workflow. It does not claim
production deployment, certification, or universal implementation support.

## Existing authoritative records

- `audit.orm_orders` is the canonical accepted HL7 ORM order.
- `audit.modality_worklist_items` is the ORM-derived MWL projection.
- Orthanc is the PACS containing the stored DICOM study.
- `audit.radiology_workflows` stores matched or quarantined lineage.
- `scripts/radiology/lineage.py` contains existing lineage rules.

## Correlation model

| Identity | ORM | MWL | DICOM study | Final ORU |
|---|---|---|---|---|
| Patient | `patient_id` | `patient_identifier` | `PatientID` | `patient_id` |
| Placer order | `orc_placer_order_number` | `requested_procedure_id` | Not required | `placer_order_number` |
| Accession | `accession_number` | `accession_number` | `AccessionNumber` | `filler_order_number` |
| Procedure code | `procedure_code` | `procedure_code` | Not required | `service_code` |
| Procedure text | `procedure_text` | `procedure_description` | `StudyDescription` | `service_text` |
| Study identity | Not yet assigned | `study_instance_uid` | `StudyInstanceUID` | Not carried |
| Modality | Order-derived | `modality` | `Modality` | Not required |

The accession number is the principal cross-standard bridge. The placer
order preserves originating-order identity. The Study Instance UID proves
ownership of the concrete imaging study after MWL publication.

The current ORU does not carry the Study Instance UID. It is linked using
patient, placer order, accession/filler order, and procedure identity.

## Required boundaries

### ORM order

The ORM boundary requires a persisted accepted order containing patient,
placer order, accession, procedure code, and procedure text.

### MWL projection

The MWL boundary requires:

- A reference to the canonical ORM order.
- Patient identity equal to the ORM patient.
- Requested procedure ID equal to the ORM placer order.
- Accession and procedure equal to the ORM values.
- Projection status `PUBLISHED`.
- Study Instance UID and Orthanc worklist ID present.

### PACS study

The PACS boundary requires:

- A study queryable by the expected accession.
- Patient ID equal to the ORM patient.
- Accession equal across ORM, MWL, and DICOM.
- Study description equal to the ordered procedure text.
- Study Instance UID equal to the published MWL value.
- Modality equal to the MWL modality.

### Final ORU

The ORU boundary requires:

- Patient identity equal to the ORM patient.
- Placer order equal to the ORM placer order.
- Filler order equal to the ORM accession.
- Service code and text equal to the ORM procedure.
- Final OBR and OBX statuses.
- An `IMPRESSION` observation with nonempty text.

## Outcome states

### PASS

Every required ORM, MWL, PACS, and ORU check passed.

### QUARANTINE

All required artifacts exist, but one or more identity, ownership,
procedure, modality, or result checks failed. Each failure must expose
the boundary, field, expected value, actual value, and status.

### INCOMPLETE

A required artifact is not available, such as an unpublished MWL item,
missing PACS study, or missing final ORU. Incomplete is not PASS and is
not automatically an identity mismatch.

### DUPLICATE

An accession or Study Instance UID is claimed by conflicting workflows.
Existing database ownership and uniqueness controls remain authoritative.

## Determinism requirements

- Check order and boundary order remain stable.
- Identical normalized evidence produces identical results.
- JSON evidence is reproducible when volatile timestamps are excluded.
- Reconciliation does not mutate clinical workflow records.

## Initial acceptance criteria

1. A complete matching workflow returns `PASS`.
2. Every check passes for the matching workflow.
3. A wrong PACS accession returns `QUARANTINE`.
4. The accession failure contains expected and actual values.
5. A mismatched MWL/PACS Study Instance UID returns `QUARANTINE`.
6. A missing ORU returns `INCOMPLETE`.
7. A nonfinal ORU returns `QUARANTINE`.
8. Repeated reconciliation produces identical normalized JSON.
9. Existing ORM, MWL, PACS, and lineage tests continue to pass.

## Planned implementation

The first implementation will reuse existing analyzers and lineage rules.
It will add a reporting module, focused tests, and durable JSON evidence.

- `scripts/radiology/accession_reconciliation.py`
- `tests/interoperability/test_cross_standard_accession_reconciliation.py`
- `docs/validation/evidence/radiology-accession-reconciliation/`

No schema change is planned unless existing records prove insufficient.
