# HL7 ADT A04 Deterministic Fixture

## Purpose

Defines the first deterministic HL7 v2 fixture used by the Healthcare IT Operations & Interoperability Lab.

The fixture represents a synthetic outpatient registration/check-in event for patient LAB000001.

## Fixture

`fixtures/hl7/adt/adt-a04-lab000001.hl7`

## Message Identity

| Field | Value | Meaning |
|---|---|---|
| MSH-3 | LABSENDER | Sending application |
| MSH-4 | INTEROPLAB | Sending facility |
| MSH-5 | MIRTH | Receiving application |
| MSH-6 | INTEROPLAB | Receiving facility |
| MSH-9 | ADT^A04^ADT_A01 | Outpatient registration/check-in event |
| MSH-10 | LAB-A04-000001 | Deterministic message control ID |
| MSH-11 | P | Production-processing mode used within the synthetic lab |
| MSH-12 | 2.5.1 | HL7 version |

## Patient Identity

| Field | Value |
|---|---|
| PID-3 | LAB000001^^^INTEROPLAB^MR |
| PID-5 | Testpatient^Avery^^^^L |
| PID-7 | 19800115 |
| PID-8 | M |

LAB000001 is a synthetic medical-record identifier and is the deterministic business identifier used throughout the lab.

## Visit Context

| Field | Value |
|---|---|
| PV1-2 | O |
| PV1-3 | CLINIC^ROOM1^1^INTEROPLAB |
| PV1-7 | 12345^Morgan^Alice |
| PV1-19 | VISIT000004 |
| PV1-44 | 20260814220000-0400 |

Patient class O represents an outpatient visit.

## Deterministic Reconciliation Targets

- Patient identifier must resolve to LAB000001.
- Message control ID must remain LAB-A04-000001.
- Patient class must remain O.
- Visit number must remain VISIT000004.
- Successful ACK processing must reference LAB-A04-000001.

## Transport Note

The source-controlled fixture is stored as readable text.

The MLLP sender will convert segment separators to carriage returns and add the required MLLP framing bytes before transmission.

Stored fixture text is therefore not identical to the TCP wire representation.

## Data Classification

Synthetic data only. No PHI or production identifiers are used.
