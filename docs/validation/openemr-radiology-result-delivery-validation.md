# OpenEMR Radiology Result Delivery Validation

## Purpose

This validation records delivery of a final synthetic radiology report
into the native OpenEMR procedure-results data model. It extends the
cross-standard accession workflow by proving that the final narrative
result is visible to an OpenEMR user.

This is controlled laboratory evidence. It does not claim production
deployment or universal radiology-report compatibility.

## Workflow identity

| Field | Value |
|---|---|
| OpenEMR order | `107` |
| Patient identifier | `SYNTHMRN000005` |
| Encounter | `122` |
| Placer order | `OEMRRAD00000107` |
| Accession | `RAD00000107` |
| Procedure | `XRCH2 - Chest X-ray 2 Views` |
| Final ORU control ID | `OEMR-RAD-ORU-00000107-02` |

## Persisted OpenEMR result

| Record | Value |
|---|---|
| Procedure report ID | `12` |
| Procedure result ID | `15` |
| Report status | `final` |
| Review status | `received` |
| Result code | `IMPRESSION` |
| Result name | `Radiology Impression` |
| Result status | `final` |
| Narrative | `No acute cardiopulmonary abnormality.` |

OpenEMR's native DORN result parser stores this textual narrative in
`procedure_result.comments`. The procedure-results screen therefore
shows the narrative in the Notes section rather than in the quantitative
Value column.

## Validation sequence

1. A radiology ORU scenario was created from the reconciled workflow.
2. Static scenario validation initially rejected blank quantitative
   fields on the textual `TX` observation.
3. Scenario validation was narrowed so only `TX` observations may leave
   units, reference range, and abnormal flag blank.
4. Numeric `NM` observations retain all existing quantitative
   requirements.
5. A non-mutating OpenEMR ingestion dry run passed.
6. The guarded commit persisted exactly one report and one result.
7. OpenEMR displayed the final report and narrative impression.
8. A deliberate replay attempt returned `REPLAY_BLOCKED`.
9. Report and result counts remained `1:1` after the rejected replay.
10. The focused regression suite completed with `38 passed` while
    treating warnings as errors.

## Reliability correction

The warning-strict regression exposed four tests that used unmanaged
`open(...).read()` calls. They were changed to `Path.read_text()` so
file handles close deterministically under Python 3.14.

## Known boundary

The OpenEMR order header continues to display `Pending` even though the
persisted report and result are final. The database order-status field is
blank and `date_transmitted` is null. This increment does not infer or
force an order-level status transition; that behavior remains explicitly
documented for separate lifecycle analysis.

## Conclusion

The final synthetic radiology impression was delivered into OpenEMR,
displayed through its native procedure-results interface, and protected
against accidental replay. Existing numeric laboratory and panel
validation behavior remained intact.

## Deterministic evidence

Evidence file:

`docs/validation/evidence/radiology-result-delivery/openemr-order-107.json`

SHA-256:

`ADF4762BD7F9D55828AEA5E191B01AC1D8894FFF0FC1FCFBD216195D61855FF2`
