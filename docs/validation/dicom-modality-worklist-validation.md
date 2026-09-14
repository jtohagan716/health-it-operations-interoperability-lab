DICOM Modality Worklist Projection and Query Validation

Purpose

This increment adds a durable, guarded path from an accepted HL7 radiology
order to a queryable DICOM Modality Worklist item in Orthanc.

The validation demonstrates preservation of patient, accession, requested
procedure, modality, and scheduling identity across the following boundary:

HL7 ORM^O01
    -> Mirth Connect
    -> audit.orm_orders
    -> audit.modality_worklist_items
    -> guarded Orthanc publication
    -> DICOM MWL C-FIND

All patients, orders, accessions, and scheduled procedures used in this
validation are synthetic.

Initial observed state

The lab already validated HL7 ORM order persistence, DICOM storage,
query/retrieve, PACS routing, ORM-to-DICOM-to-ORU lineage, and accession
ownership. It did not yet provide a durable representation of scheduled
imaging work that a modality could query before image acquisition.

The necessary order identity existed in audit.orm_orders, but no persisted
projection, guarded publisher, Orthanc worklist object, or MWL C-FIND runtime
contract connected that order to a modality-facing worklist.

Implementation

Durable worklist projection

Migration 025-modality-worklist-projection.sql adds
audit.modality_worklist_items with:

a unique foreign key to the authoritative ORM order;

patient identifier, name, date of birth, and administrative sex;

accession and requested-procedure identity;

procedure code and description;

modality, scheduled station AE title, start date, and start time;

schedule-source provenance;

a unique Scheduled Procedure Step ID;

Orthanc worklist and Study Instance UID correlation;

projection status, attempt count, timestamps, and last-error state; and

indexes for projection processing and patient lookup.

The permitted lifecycle is PENDING, IN_PROGRESS, PUBLISHED, FAILED, or
CANCELLED. A published row must contain its Study Instance UID, Orthanc
worklist ID, and publication timestamp.

Canonical identity enforcement

The database trigger audit.enforce_mwl_orm_identity() locks and resolves the
parent ORM order before accepting a projection. It rejects a missing parent or
any disagreement in patient identifier, accession number, requested procedure
ID, or procedure code.

The ORM order remains authoritative. The MWL row is a controlled downstream
projection, not an independent clinical order.

Guarded publisher

scripts.radiology.mwl_projection publishes one explicitly selected MWL row
to Orthanc. The command requires the supplied MWL item ID and confirmation ID
to match exactly before work begins.

The publisher retains projection attempts and failure detail, supports stale
claim recovery through an explicit age boundary, and reconciles successful
publication with the resulting Orthanc identifiers.

Modality query

scripts.dicom.mwl_cfind_probe performs a DICOM Modality Worklist C-FIND by
accession, with optional modality and calling-AE filters. The Orthanc worklist
plugin serves the published scheduled procedure.

CT_MODALITY and XRAY_MODALITY are registered MWL query peers. They are not
outbound PACS Storage destinations and are therefore excluded from the
Storage-destination C-ECHO health aggregate.

Safety and reliability controls

synthetic data only;

exact MWL item confirmation before publication;

authoritative ORM foreign-key lineage;

database enforcement of cross-standard clinical identity;

unique ORM order, accession, Scheduled Procedure Step, and Orthanc identity;

fail-closed demographic and scheduling constraints;

explicit projection states and attempt accounting;

retained publication failure detail;

stale in-progress claim handling;

post-publication Orthanc identity persistence;

deterministic contract and runtime tests; and

role-aware PACS destination health reporting.

Runtime validation

ORM-to-MWL projection

python -m pytest -q `
    .\tests\interoperability\test_orm_mwl_projection_runtime.py

Result:

1 passed in 40.22s

DICOM MWL query

python -m pytest -q `
    .\tests\interoperability\test_dicom_mwl_runtime.py

Result:

3 passed in 17.48s

Focused contracts

The MWL schema, migration, publisher, ORM channel, and DICOM contract suites
completed with:

38 passed

Non-regression investigation

Evidence and observed state

The first broad imaging regression completed with:

1 failed, 120 passed, 193 deselected in 88.59s

The failure expected one unhealthy PACS destination but observed three.
Orthanc reported four registered modality entries:

interoplab — healthy Storage destination;

unavailable — deliberate unhealthy Storage negative control;

ct_modality — MWL query client without a Storage listener; and

xray_modality — MWL query client without a Storage listener.

Root cause

Orthanc represents configured remote DICOM peers under DicomModalities
regardless of their workflow role. The existing PACS health report assumed
that every registered peer was an outbound Storage destination and sent
C-ECHO to all four entries.

The two new MWL calling AEs were consequently misclassified as failed Storage
destinations. This was a monitoring-model defect, not a failure of MWL query,
PACS storage, or routing.

Remediation

scripts.dicom.pacs_destination_health now limits Storage-destination health
to interoplab and the deliberate unavailable control. It continues to
surface ct_modality and xray_modality as excluded non-storage peers rather
than hiding them.

Validation

The focused destination-health suite passed:

3 passed in 3.20s

The operational report returned:

Excluded non-storage peers: ct_modality, xray_modality
Healthy:   1
Unhealthy: 1
OVERALL:   DEGRADED

DEGRADED is the expected result because unavailable intentionally remains
configured as a negative control.

The complete imaging non-regression selection then passed:

121 passed, 193 deselected in 143.61s

Python compilation and Git whitespace validation also completed without
errors.

Validated outcome

The lab now demonstrates that an accepted HL7 radiology order can be projected
through an enforced persistence boundary, published to Orthanc through a
guarded and observable lifecycle, and returned to a simulated modality through
a real DICOM MWL C-FIND query. Existing DICOM storage, query/retrieve, routing,
lineage, and failure-control behavior remained intact.

Scope boundary and remaining gaps

This is a synthetic local-lab implementation, not a vendor DICOM certification
or a production deployment pattern.

The validated scope does not include:

DICOM TLS or production authentication;

production PHI;

a physical imaging modality;

Modality Performed Procedure Step feedback;

procedure updates or cancellation propagated after publication;

high-volume concurrent worklist publication; or

vendor-specific modality compatibility testing.

Those capabilities must not be inferred from the passing MWL projection and
C-FIND tests.
Final pre-commit regression

A focused DICOM/PACS/MWL pre-commit regression covering the existing imaging
capabilities and the new worklist projection completed with:

71 passed in 84.03s

This included DICOMweb, Storage SCP, autorouting, C-FIND, C-MOVE, PACS
destination health, PACS routing, Modality Worklist contracts and runtime,
projection migration, publisher behavior, ORM projection contracts, and ORM
projection runtime validation.
