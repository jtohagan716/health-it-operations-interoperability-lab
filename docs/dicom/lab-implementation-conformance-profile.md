# Interoperability Lab DICOM Implementation Conformance Profile

## Status and scope

This document describes the behavior implemented and validated by
the health IT operations interoperability lab. It is an
implementation profile for portfolio and test purposes; it is not
a vendor certification of Orthanc, pydicom, or pynetdicom and is
not a substitute for those products' formal DICOM Conformance
Statements.

## Application entities

| Logical component | AE title | Address | Port | Primary roles |
|---|---|---|---:|---|
| Orthanc PACS | `ORTHANC` | `orthanc` or `localhost` | 4242 | Verification SCP, Storage SCP, Query/Retrieve SCP, routing Storage SCU |
| Managed receiver | `INTEROPLAB` | `dicom-storage-scp` or `localhost` | 11112 | Verification SCP, Secondary Capture Storage SCP |
| Negative-control destination | `UNAVAILABLE` | `host.docker.internal` | 11113 | Intentionally unavailable failure target |
| Simulated CT modality | `CT_MODALITY` | Host-side test client | Dynamic | Modality Worklist C-FIND SCU |
| Simulated X-ray modality | `XRAY_MODALITY` | Host-side test client | Dynamic | Modality Worklist C-FIND SCU |

The address used depends on the caller's network boundary. Docker
services use Compose DNS names. Host-side probes use published
localhost ports.

## Validated service behavior

| Service | Initiator | Provider | Validated behavior |
|---|---|---|---|
| C-ECHO | Host probe or Orthanc | `INTEROPLAB` | Successful Verification response required for health |
| C-STORE inbound | Synthetic sender | `ORTHANC` | Secondary Capture instance stored and indexed |
| C-STORE routed | `ORTHANC` | `INTEROPLAB` | Selected instance saved to host-visible destination storage |
| C-FIND | Test client | `ORTHANC` | Authorized study discovery and unauthorized-AE negative control |
| C-MOVE | Test client | `ORTHANC` | Matching study delivered to registered `INTEROPLAB` destination |
| STOW-RS | Test client | `Orthanc DICOMweb` | Deterministic instance stored through HTTP |
| QIDO-RS | Test client | `Orthanc DICOMweb` | One study discovered by Study Instance UID |
| WADO-RS | Test client | `Orthanc DICOMweb` | Exact SOP Instance retrieved and reconciled |
| MWL C-FIND | `CT_MODALITY` or `XRAY_MODALITY` | `ORTHANC` | ORM-derived scheduled procedure returned by accession and optional modality filter |

## Storage SOP Classes

The managed receiver currently declares support for:

| SOP Class | UID | Role |
|---|---|---|
| Verification | `1.2.840.10008.1.1` | SCP |
| Secondary Capture Image Storage | `1.2.840.10008.5.1.4.1.1.7` | SCP |

Support for additional storage SOP Classes must not be inferred
from this profile. They should be added deliberately and covered
by negotiated-association and persistence tests.

## Association and routing model

Orthanc accepts inbound DICOM associations on port `4242` under
AE title `ORTHANC`.

The lab's Lua routing rule evaluates newly received instance
metadata. A matching synthetic accession selects the registered
`interoplab` modality. Orthanc then acts as a Storage SCU and
opens a separate association to `INTEROPLAB` on port `11112`.

The `UNAVAILABLE` modality on port `11113` is preserved as an
intentional negative control for destination-health, routing,
failure-persistence, and recovery validation.

## Query/retrieve model

Orthanc is configured to use C-MOVE as its default retrieve
method. The requesting client asks Orthanc to move a matching
study to a registered destination AE. Orthanc performs the
resulting C-STORE sub-operations to `INTEROPLAB`.

A successful move requires all of the following:

1. The requested study exists in Orthanc.
2. The calling AE is permitted to associate.
3. The destination AE is registered in Orthanc.
4. The destination hostname and port are reachable.
5. The destination accepts the proposed storage presentation
   context.
6. The receiver successfully persists the object.

## Modality Worklist model

An accepted HL7 ORM imaging order remains authoritative in
`audit.orm_orders`. Mirth projects the additional patient and scheduling
fields required for modality scheduling into
`audit.modality_worklist_items`.

The database projection enforces agreement with the parent ORM order for
patient identifier, accession number, requested procedure ID, and procedure
code. Publication to Orthanc uses a guarded state model with `PENDING`,
`IN_PROGRESS`, `PUBLISHED`, `FAILED`, and `CANCELLED` states, attempt
accounting, failure detail, and stale-claim handling.

The Orthanc Worklists plugin serves a published item through DICOM MWL
C-FIND. The validated query path supports accession filtering, an optional
modality filter, and the simulated calling AE titles `CT_MODALITY` and
`XRAY_MODALITY`.

Those two AEs are query clients, not outbound Storage SCP destinations. PACS
destination-health reporting therefore surfaces but excludes them from its
Storage-destination C-ECHO aggregate.

## Identity and persistence assertions

The validated workflow preserves and compares:

- Patient ID;
- Accession Number;
- Study Instance UID;
- Series Instance UID; and
- SOP Instance UID.

The receiver uses SOP Instance UID as the destination filename.
Objects are saved within the container at `/data/received`, which
is mapped to `artifacts/dicom/received` on the host.

## Health and readiness

The receiver's Compose health check establishes a DICOM
association and sends C-ECHO. Success requires status `0x0000`.
Orthanc declares a startup dependency on this application-level
health state.

Destination availability is also independently validated from
Orthanc through its modality C-ECHO operation.

## Security posture

This is a local synthetic-data lab. DICOM TLS is not enabled, and
Orthanc HTTP authentication is disabled. No production PHI is
permitted. These settings are known lab limitations and are not
appropriate defaults for an exposed or production deployment.

## Versioned receiver dependencies

```text
pydicom==3.0.2
pynetdicom==3.0.4
```

The Orthanc container image should be pinned to an explicit
version in a future hardening change; the current Compose file
uses the upstream `latest` tag.

## Known limitations and next work

- The managed receiver currently supports only Secondary Capture
  Image Storage.
- Transfer-syntax claims have not yet been promoted into explicit
  regression assertions.
- DICOM TLS is not configured.
- Modality Performed Procedure Step feedback is not implemented.
- Post-publication procedure updates and cancellations have not been validated.
- A physical imaging modality and vendor-specific worklist behavior have not
  been tested.
- OpenEMR order-to-DICOM accession reconciliation will be added in
  a subsequent cross-standard workflow.
- FHIR ImagingStudy and DiagnosticReport linkage remains future
  work.

## Evidence

- `docs/validation/dicom-managed-storage-scp-validation.md`
- `tests/interoperability/test_dicom_storage_scp_service_contract.py`
- `tests/interoperability/test_dicom_autorouting_contract.py`
- `tests/interoperability/test_dicom_cmove_contract.py`
- `tests/interoperability/test_pacs_destination_health.py`
- `tests/interoperability/test_pacs_routing_contract.py`
- `docs/validation/dicomweb-store-query-retrieve.md`
- `tests/interoperability/test_dicomweb_runtime.py`
- `docs/validation/dicom-modality-worklist-validation.md`
- `tests/interoperability/test_dicom_mwl_contract.py`
- `tests/interoperability/test_dicom_mwl_runtime.py`
- `tests/interoperability/test_modality_worklist_projection_migration_contract.py`
- `tests/interoperability/test_mwl_projection_publisher.py`
- `tests/interoperability/test_mwl_projection_publisher_contract.py`
- `tests/interoperability/test_orm_mwl_projection_channel_contract.py`
- `tests/interoperability/test_orm_mwl_projection_runtime.py`
