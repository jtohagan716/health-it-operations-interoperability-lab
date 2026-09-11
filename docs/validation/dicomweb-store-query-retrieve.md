# DICOMweb Store, Query, and Retrieve Validation

## Purpose

This validation proves that the lab supports the HTTP-based DICOMweb workflow
without breaking the existing DIMSE workflow. It exercises STOW-RS for storage,
QIDO-RS for study discovery, and WADO-RS for instance retrieval.

## Data path

1. A unique synthetic Secondary Capture object is generated.
2. STOW-RS stores the object at `/dicom-web/studies`.
3. QIDO-RS locates the study by `StudyInstanceUID`.
4. WADO-RS retrieves the exact SOP Instance.
5. The retrieved object is parsed and reconciled with the source.

The reconciliation checks Patient ID, accession number, Study Instance UID,
Series Instance UID, SOP Instance UID, modality, and pixel data.

## Prerequisites

```powershell
docker compose -f .\infrastructure\orthanc\compose.yaml up -d --build
docker compose -f .\infrastructure\orthanc\compose.yaml ps
```

## Static contract

```powershell
python -m pytest -q `
    .\tests\interoperability\test_dicomweb_contract.py
```

## Live DICOMweb round trip

```powershell
python -m pytest -q `
    .\tests\interoperability\test_dicomweb_runtime.py
```

## Operator-level client run

```powershell
python -m scripts.dicom.create_test_dicom

python -m scripts.dicom.dicomweb_client `
    .\fixtures\dicom\interop-lab-test-image.dcm
```

Expected terminal result:

```text
DICOMWEB STORE QUERY RETRIEVE: PASS
```

## DIMSE non-regression

```powershell
python -m scripts.dicom.storage_scp_health `
    --host localhost `
    --port 11112 `
    --called-ae INTEROPLAB

Invoke-RestMethod `
    -Method Post `
    -Uri http://localhost:8042/modalities/interoplab/echo
```

The first command must report `DICOM C-ECHO: PASS`; the Orthanc echo request
must complete without an HTTP error.

## Evidence to record

- Docker service health for Orthanc and the managed Storage SCP.
- STOW-RS HTTP status.
- Exactly one QIDO-RS match for the generated Study Instance UID.
- Successful WADO-RS retrieval.
- All identity, hierarchy, modality, and pixel-data reconciliation checks.
- Successful DIMSE C-ECHO after DICOMweb enablement.

## Operational conclusion

A passing run demonstrates that the same Orthanc deployment supports both
DICOMweb and traditional DIMSE communication, and that clinical identifiers and
DICOM hierarchy survive an HTTP store-query-retrieve round trip.
