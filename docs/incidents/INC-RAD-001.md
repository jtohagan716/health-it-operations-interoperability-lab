# INC-RAD-001 - Imaging Study Not Found as Expected

## Reported Symptom

A chest X-ray order was submitted successfully through the integration environment.

The sending workflow received an HL7 application acknowledgment indicating acceptance.

Radiology reported that the expected imaging study could not be located using the expected patient/order information.

## Incident Case

- Case: `RADINCFEBF56`
- Patient ID: `RADINCFEBF56`
- HL7 Message Control ID: `RAD-ORM-RADINCFEBF56`
- Placer Order Number: `ORDRADINCFEBF56`
- Expected Accession Number: `ACCRADINCFEBF56`

## Systems in Scope

- HL7 ORM order source
- Mirth Connect
- PostgreSQL interoperability database
- DICOM transport
- Orthanc PACS
- Radiology workflow correlation

## Initial Hypotheses

The reported symptom could have been caused by several different failure classes:

- HL7 message rejected by the interface engine
- HL7 message acknowledged but not persisted
- Patient identity mismatch
- Order/accession mapping error
- DICOM transmission failure
- PACS storage failure
- Imaging study stored under unexpected workflow identity
- Cross-system order-to-study correlation failure

## Investigation

### 1. HL7 Application Acknowledgment

The incident ORM was transmitted through Mirth Connect.

Observed acknowledgment:

- ACK code: `AA`
- Message Control ID: `RAD-ORM-RADINCFEBF56`

This proved that the HL7 message was accepted at the application acknowledgment boundary.

It did not prove downstream persistence or imaging workflow correctness.

### 2. ORM Persistence Verification

The interoperability PostgreSQL database was queried using the HL7 message control ID.

Observed persisted values:

- Message Control ID: `RAD-ORM-RADINCFEBF56`
- Patient Identifier: `RADINCFEBF56`
- Placer Order Number: `ORDRADINCFEBF56`
- Filler Order / Accession Number: `ACCRADINCFEBF56`
- Procedure Code: `XRCH2`
- Procedure Text: `Chest X-ray 2 Views`

This confirmed that the accepted HL7 order persisted with the expected clinical identity.

### 3. PACS Patient Search

Orthanc was queried by Patient ID:

`RADINCFEBF56`

A study was present in PACS.

Orthanc Study ID:

`93d4c33c-5357c5ec-8743449e-659ba6f1-49f91293`

This eliminated complete DICOM delivery or PACS storage failure as the primary cause.

### 4. PACS Study Metadata Verification

The stored study contained:

- Patient ID: `RADINCFEBF56`
- Patient Name: `Testpatient^Avery`
- Study Description: `Chest X-ray 2 Views`
- Accession Number: `IMGRADINCFEBF56`

The patient identity and study description were consistent with the expected workflow.

The accession number was not.

## Fault Isolation

The accepted HL7 ORM order contained:

`ACCRADINCFEBF56`

The stored DICOM study contained:

`IMGRADINCFEBF56`

The workflow therefore diverged at the cross-system accession identity boundary.

## Root Cause

The DICOM study was successfully stored in Orthanc for the correct patient, but its DICOM `AccessionNumber` did not match the accession assigned to the accepted HL7 ORM order.

Expected HL7 accession:

`ACCRADINCFEBF56`

Observed DICOM accession:

`IMGRADINCFEBF56`

Because downstream radiology workflow correlation depends on accession identity, the study could not be located using the expected order information even though both HL7 and DICOM transport operations independently succeeded.

## Systems Eliminated

The investigation provided evidence against the following primary failure causes:

- HL7 transport failure
- HL7 application rejection
- ORM persistence failure
- Patient identity mismatch
- DICOM transmission failure
- Complete PACS storage failure
- Procedure description mismatch

## Corrective Action

Ownership of the incorrectly correlated PACS study was positively established before modification.

The incident-owned Orthanc study was identified by:

- Patient ID: `RADINCFEBF56`
- Incorrect Accession Number: `IMGRADINCFEBF56`
- Orthanc Study ID: `93d4c33c-5357c5ec-8743449e-659ba6f1-49f91293`

The incident-owned study was removed from Orthanc.

The original failed DICOM artifact was preserved as evidence.

A corrected DICOM object was generated as `study-corrected.dcm` with:

- Patient ID: `RADINCFEBF56`
- Corrected Accession Number: `ACCRADINCFEBF56`
- New Study Instance UID
- New Series Instance UID
- New SOP Instance UID

The corrected object was retransmitted to Orthanc through a DICOM C-STORE operation.

The C-STORE operation returned status `0x0000`.

## Recovery Verification

Recovery was verified independently against the original failure condition.

Orthanc was searched using the expected accession number:

`ACCRADINCFEBF56`

The corrected study was successfully located.

The recovered PACS metadata contained:

- Patient ID: `RADINCFEBF56`
- Accession Number: `ACCRADINCFEBF56`
- Study Description: `Chest X-ray 2 Views`
- Study Instance UID: `1.2.826.0.1.3680043.8.498.26373805534543855907191816558273121847`

The persisted HL7 order and recovered DICOM study therefore agreed on the workflow's patient and accession identities.

The original reported symptom was resolved: the imaging study could now be located using the accession assigned to the accepted radiology order.

## Regression Prevention

The radiology lineage suite already includes an automated negative-path regression for this failure class.

`tests/interoperability/test_radiology_lineage_negative_paths.py`

The regression creates a structurally valid DICOM study with the correct patient identity but an incorrect accession number and verifies that:

`validate_order_to_dicom()`

raises:

`ValueError("Radiology accession mismatch")`

This incident provided runtime confirmation that the same semantic defect can produce a real cross-system workflow failure even when:

- HL7 returns `AA`
- the ORM persists successfully
- DICOM C-STORE returns `0x0000`
- the PACS stores the study successfully

The existing regression therefore protects a clinically meaningful interoperability invariant rather than only a synthetic edge case.

## Engineering Lesson

Successful protocol-level responses do not prove successful clinical workflow correlation.

For this incident:

- HL7 returned `AA`
- DICOM C-STORE returned `0x0000`
- the ORM persisted successfully
- the DICOM study was stored successfully

The workflow still failed because cross-system semantic identity was inconsistent.

Operationally:

`transport success != workflow correctness`