# Cross-Standard Accession Reconciliation Validation

## Purpose

This validation records one controlled synthetic radiology workflow
initiated manually in OpenEMR and traced through HL7 ORM, Mirth,
DICOM Modality Worklist, modality selection, DICOM C-STORE,
Orthanc/PACS, final HL7 ORU, and persisted lineage reconciliation.

This is laboratory evidence. It does not claim production deployment,
certification, or universal interoperability support.

## Workflow identity

| Field | Value |
|---|---|
| OpenEMR order | `107` |
| Patient identifier | `SYNTHMRN000005` |
| Placer order | `OEMRRAD00000107` |
| Accession | `RAD00000107` |
| Procedure | `XRCH2 - Chest X-ray 2 Views` |
| Modality | `DX` |
| Study Instance UID | `2.25.293750971016350337408807083307746558602` |
| Final ORU control ID | `OEMR-RAD-ORU-00000107-02` |

## Operational records

| Record | Identifier | Final state |
|---|---:|---|
| ORM transaction | `853` | First delivery |
| ORM order | `385` | Accepted |
| MWL item | `132` | `PUBLISHED` |
| Orthanc worklist | `70c95d26-f52e-49d2-bcd8-a736cdf4fcca` | Published |
| Orthanc study | `9726e480-65e1a484-b84ae79b-47ff5a39-b6fa933a` | Stored |
| ORU transaction | `857` | Accepted once |
| Radiology workflow | `198` | `MATCHED` / `RECONCILED` |

## Validated sequence

1. A chest X-ray order was entered manually in OpenEMR.
2. A deterministic ORM was generated from the persisted order.
3. Mirth validated and persisted the ORM and returned an application accept.
4. The order produced a durable MWL projection.
5. Orthanc published the worklist with a deterministic Study Instance UID.
6. A simulated modality retrieved exactly one matching item by C-FIND.
7. A correlated synthetic DICOM study passed pre-transmission validation.
8. C-STORE completed with status `0x0000`.
9. Orthanc returned exactly one study with the expected identity.
10. A final narrative radiology ORU passed static validation.
11. The live ORU channel accepted the corrected profile with ACK `AA`.
12. Canonical lineage persistence returned workflow `198`.
13. Five live PACS reconciliation checks passed.
14. Cross-standard reconciliation returned `PASS` across four boundaries.

## Runtime defect found and remediated

The shared ORU channel originally applied quantitative laboratory rules
to a narrative radiology impression. It required LOINC coding, units,
reference ranges, abnormal flags, and OBR/OBX code equality, causing
a clinically valid radiology ORU to receive an `AR` acknowledgment.

The channel was changed to classify one narrowly defined radiology profile:

- OBR coding system `99INTEROP`.
- Exactly one OBX.
- OBX value type `TX`.
- Observation code `IMPRESSION`.
- Observation coding system `99INTEROP`.
- Final OBR and OBX statuses.

Only this profile bypasses quantitative laboratory requirements.
Existing single-analyte and multi-analyte laboratory policies remain present.

## Additional boundary findings

- A 15-second sender timeout occurred even though Mirth later persisted
  the ORM and generated an `AA`; durable state prevented a blind resend.
- Orthanc rejected an unregistered calling AE title; the configured
  `CT_MODALITY` identity succeeded while querying the `DX` worklist.
- A PowerShell empty-array comparison produced a false duplicate warning;
  a Python preflight established zero matching studies before C-STORE.

## Automated validation

- ORU channel and compatibility contracts: `40 passed`.
- Radiology semantic and reconciliation contracts: `15 passed`.
- Existing scenario helper contracts: `13 passed`.
- Cross-standard reconciliation: `27` individual checks passed.
- ORM, MWL, PACS, and ORU boundary states: all `PASS`.

## Full interoperability regression

The complete interoperability suite was executed after the focused
radiology and ORU regression suites. The final result was:

- `322 passed`.
- `1 skipped`.
- `1 xfailed`.
- `2 deselected`.

The two deselected tests were the authenticated DiagnosticReport
searches by patient and by patient plus code. OpenEMR advertised the
resource, the valid SMART token contained `user/DiagnosticReport.rs`,
and authenticated Observation searches passed. OpenEMR nevertheless
returned HTTP `403` with:

> Organization policy does not have permit access resource

This previously documented OpenEMR ACL boundary is independent of the
cross-standard radiology implementation. The tests were not counted as
passes, and the remaining interoperability suite had no unexpected failures.

## Deterministic evidence

Evidence file:

`docs/validation/evidence/radiology-accession-reconciliation/openemr-order-107.json`

SHA-256:

`7F7483C0D4153F72739ACED53C0740CF515BABFA9060987FE7E12E9A0BD1C186`

Reformatting and regenerating the normalized JSON produced the identical digest.

## Conclusion

The controlled workflow preserved patient, order, accession, procedure,
modality, Study Instance UID, and final-report identity across OpenEMR,
HL7, Mirth, DICOM MWL, modality acquisition, C-STORE, Orthanc/PACS,
and persisted lineage reconciliation. All required final checks passed.
