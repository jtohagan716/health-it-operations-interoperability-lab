# OpenEMR ORU Ingestion Bridge

## Purpose

The bridge adapts a data-driven ORU scenario for OpenEMR's native DORN
result parser. It supports a non-mutating validation mode and an explicit
local commit mode without calling the external DORN send or acknowledgment
APIs.

## Safety Contract

- Dry run is the default.
- Commit requires both `--commit` and a matching `--confirm-order-id`.
- Patient, encounter, laboratory, order, and procedure code are validated
  before parsing.
- OBR-3 is blank during dry run because the upstream parser can otherwise
  update `procedure_order.control_id` during a nominal dry run.
- Existing results are blocked by default.
- A lifecycle update requires the explicit `--allow-existing-results` flag.
- The PHP harness invokes only `ReceiveHl7Results::receiveHl7Results()`.
  It never calls `receiveSingleResults()`, `ConnectorApi::sendAck()`, or an
  external DORN endpoint.
- Postconditions verify report/result counts and control-ID correlation.

## Dry Run

```powershell
python -m scripts.hl7.openemr_oru_ingest `
    .\fixtures\hl7\oru\scenarios\normal-glucose-final.json `
    --order-id 3 `
    --patient-id 1 `
    --encounter-id 6 `
    --lab-id 2
```

## Commit

Commit only against a prepared synthetic order with no existing result:

```powershell
python -m scripts.hl7.openemr_oru_ingest `
    .\fixtures\hl7\oru\scenarios\normal-glucose-final.json `
    --order-id 4 `
    --patient-id 1 `
    --encounter-id 6 `
    --lab-id 2 `
    --commit `
    --confirm-order-id 4
```

The adapter always performs a passing dry run before attempting the commit.

## Live Dry-Run Contract

The live pytest is opt-in and remains non-mutating:

```powershell
$env:OPENEMR_ORU_LIVE_ORDER_ID = "3"
$env:OPENEMR_ORU_LIVE_PATIENT_ID = "1"
$env:OPENEMR_ORU_LIVE_ENCOUNTER_ID = "6"
$env:OPENEMR_ORU_LIVE_LAB_ID = "2"

python -m pytest -q `
    .\tests\interoperability\test_live_openemr_oru_ingest.py
```

## Proven Manual Workflow

The initial controlled validation used OpenEMR Order ID 3 for Avery
Testpatient (`LAB000001`), encounter 6, and Interop DORN Contract Lab ID 2.
The resulting final Glucose observation was stored as `90 mg/dL`, reference
range `70-99`, abnormal flag `No`, and entered the provider Pending Review
queue. Provider signature changed `procedure_report.review_status` from
`received` to `reviewed`, while Patient Results retained the durable record.

The initial proof invoked the local parser directly. It did not claim that
Mirth delivered the message into OpenEMR. Connecting the Mirth route to this
guarded local boundary remains a separate deployment step.

