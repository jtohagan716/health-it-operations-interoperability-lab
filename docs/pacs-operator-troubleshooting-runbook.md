# PACS Operator Troubleshooting Runbook

## Purpose

This runbook documents a practical troubleshooting approach for Digital Imaging and Communications in Medicine (DICOM) and Picture Archiving and Communication System (PACS) workflow issues in the interoperability lab.

The focus is on identifying the failure layer quickly, validating expected behavior, and confirming downstream results rather than relying on a single status code or user interface message.

---

# Environment

## Local PACS

- System: Orthanc
- Application Entity Title (AET): `ORTHANC`
- DICOM Port: `4242`
- Web / REST Port: `8042`

## Healthy Remote DICOM Destination

- Name: `interoplab`
- Application Entity Title (AET): `INTEROPLAB`
- Host: `host.docker.internal`
- Port: `11112`

## Intentionally Unavailable Remote Destination

- Name: `unavailable`
- Application Entity Title (AET): `UNAVAILABLE`
- Host: `host.docker.internal`
- Port: `11113`

---

# Standard Troubleshooting Sequence

Use this sequence before assuming the root cause:

1. Confirm the PACS service is running.
2. Confirm the DICOM listener port is reachable.
3. Confirm DICOM association / C-ECHO succeeds.
4. Confirm the expected patient or study exists.
5. Confirm patient and study identifiers are correct.
6. Confirm the remote Application Entity Title (AET) is configured.
7. Confirm the remote host and port are correct.
8. Review PACS job status.
9. Review PACS server logs.
10. Verify downstream receipt independently.

A successful protocol response should not be treated as complete proof until the expected downstream state is also verified.

---

# Scenario 1: Study Not Found

## Symptom

A query or retrieve request does not return the expected imaging study.

Example identifiers:

- Patient Identifier (Patient ID): `IMG000001`
- Accession Number: `RAD000001`

## Checks

### 1. Confirm the study exists locally

Open:

`All local studies`

Verify:

- Patient ID
- Patient Name
- Accession Number
- Study Description
- Study Instance Unique Identifier (UID)
- Series count
- Instance count

### 2. Confirm query direction

Determine which DICOM node is being queried.

The local Orthanc PACS contains the test study.

`INTEROPLAB` is primarily a receiving Storage Service Class Provider (SCP), not a second searchable PACS archive.

A query against the wrong Application Entity (AE) can correctly return zero results.

### 3. Validate identifiers

Confirm:

- Patient ID matches exactly.
- Accession Number matches exactly.
- Study Instance UID is correct when used as the retrieve key.

## Expected Behavior

For DICOM C-FIND:

- Known study → matching result returned.
- Unknown patient / accession → zero matches may be valid successful behavior.

For DICOM C-MOVE:

- Unknown Study Instance UID → Orthanc returns failure status `0xC000`.
- No object is delivered.

## Root Cause Categories

- Wrong patient identifier
- Wrong accession number
- Wrong Study Instance UID
- Query sent to the wrong DICOM node
- Study does not exist in the source PACS

---

# Scenario 2: Unauthorized Application Entity Title (AET)

## Symptom

DICOM connectivity may appear partially functional, but a query operation such as C-FIND is rejected.

## Example

Calling AET:

`BADCLIENT`

## Observed Orthanc Behavior

Server log:

`DICOM authorization rejected`

and:

`This AET is not listed in configuration option "DicomModalities"`

## Checks

1. Confirm the calling Application Entity Title.
2. Review Orthanc `DicomModalities`.
3. Confirm the remote node is registered.
4. Confirm the expected permissions are enabled.
5. Retry the operation after configuration correction.

## Key Lesson

Successful Transmission Control Protocol (TCP) connectivity does not imply authorization for every DICOM service.

The layers are separate:

- Network connectivity
- DICOM association
- Application Entity Title identity
- Service authorization
- DICOM operation

## Expected Behavior

Authorized AET:

`INTEROPLAB`

→ C-FIND succeeds.

Unauthorized AET:

`BADCLIENT`

→ query is rejected.

---

# Scenario 3: Destination Unavailable

## Symptom

The imaging study exists in the PACS, but a send or retrieve operation fails when attempting delivery to another DICOM node.

## Example Destination

- Name: `unavailable`
- AET: `UNAVAILABLE`
- Port: `11113`

No service is listening on this port.

## Manual PACS Observation

The Orthanc job shows:

- Type: `DicomModalityStore`
- Status: `Failure`
- Remote AET: `UNAVAILABLE`

Error:

`Error in the network protocol`

Details include:

`DicomAssociation - connecting to AET "UNAVAILABLE": TCP Initialization Error`

## Checks

1. Confirm the study exists.
2. Confirm the destination is configured.
3. Confirm the Application Entity Title.
4. Confirm hostname.
5. Confirm port.
6. Run DICOM C-ECHO.
7. Review the Orthanc job details.
8. Review server logs.
9. Confirm no downstream object was received.

## Expected Behavior

Healthy destination:

`INTEROPLAB`

→ route succeeds.

Unavailable destination:

`UNAVAILABLE`

→ route fails.

## Important Observation

Orthanc may return the same broad `0xC000` failure status for different causes.

Therefore, protocol status alone may not identify the root cause.

Use:

- client result
- PACS job details
- PACS logs
- destination health
- downstream verification

together.

---

# Scenario 4: Route Reports Success — Verify Downstream Receipt

## Symptom

The PACS reports that the send operation succeeded.

## Risk

A successful source-side job should not automatically be treated as proof that the downstream object is correct.

## Verification Steps

### 1. Confirm source PACS success

Verify the Orthanc job reports:

`Success`

### 2. Confirm receiving Storage SCP activity

Expected output:

`DICOM C-STORE RECEIVED`

### 3. Verify received object identifiers

Confirm:

- Patient ID
- Accession Number
- Study Instance UID
- Series Instance UID
- SOP Instance UID

### 4. Inspect the saved DICOM object

Use pydicom or another DICOM inspection tool to confirm the object contains the expected values.

## Expected Result

Source-side job:

`Success`

Receiving Storage SCP:

`C-STORE received`

Retrieved object:

Identity and DICOM hierarchy preserved.

## Key Lesson

Source success plus independent downstream verification provides stronger evidence than source success alone.

---

# DICOM Identity and Hierarchy Reference

## Patient Level

Key fields:

- Patient Name
- Patient ID
- Patient Birth Date
- Patient Sex

## Study Level

Key fields:

- Accession Number
- Study Instance UID
- Study Description
- Study Date
- Study Time

## Series Level

Key fields:

- Series Instance UID
- Series Number
- Series Description
- Modality

## Instance Level

Key fields:

- SOP Instance UID
- SOP Class UID
- Instance Number
- Transfer Syntax UID

Hierarchy:

Patient
→ Study
→ Series
→ Instance

---

# Common Operator Questions

## "Is the PACS up?"

Check:

- Container / service status
- Port `4242`
- C-ECHO

## "Is the destination configured?"

Check:

- Remote modality inventory
- AET
- Host
- Port
- allowed DICOM operations

## "Can the PACS reach the destination?"

Run:

- manual or automated C-ECHO

## "Did the image actually leave the PACS?"

Check:

- PACS job status
- PACS logs

## "Did the destination actually receive it?"

Check:

- receiving Storage SCP
- downstream file
- DICOM metadata

## "Why did a C-MOVE fail?"

Check whether:

- the source study exists
- the destination exists
- the destination is reachable
- the AET is authorized
- PACS logs reveal a more specific network or resource error

---

# Lab Evidence

Supporting screenshots are stored in:

`docs/evidence/dicom`

Examples include:

- PACS study hierarchy
- DICOM tag inspection
- remote modality health
- manual destination selection
- successful DICOM send
- failed DICOM routing job
- receiving Storage SCP confirmation
- automated reconciliation and regression test evidence

---

# Operational Principle

Do not troubleshoot DICOM issues as a single-layer problem.

Use a layered approach:

Application / Workflow
→ DICOM operation
→ Application Entity Title authorization
→ network connectivity
→ PACS job state
→ server logs
→ downstream verification

The objective is not merely to determine whether a transaction failed.

The objective is to determine:

- where it failed
- why it failed
- whether the failure is reproducible
- whether the expected downstream state was created
- whether the problem is configuration, authorization, network, data, or workflow related