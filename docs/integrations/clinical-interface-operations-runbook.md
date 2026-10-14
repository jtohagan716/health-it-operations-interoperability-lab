# Clinical Interface Operations Runbook

This runbook accompanies the [synthetic ORU-to-OpenEMR case study](warren-oru-openemr-case-study/README.md). It records the readiness checks, regression test, delivery sequence, and observed acknowledgment issue.

## Scope

The demonstrated workflow is:

```text
Synthetic ORU^R01 -> Mirth MLLP listener (6662) -> PostgreSQL interface audit
  -> target-mapped delivery queue -> guarded OpenEMR receiver
  -> procedure report/result -> provider view
```

All patient and order data are synthetic. The fixture imitates selected MEDITECH Expanse-style source fields; it does not connect to MEDITECH or a hospital system.

## Check readiness

From the repository root in PowerShell:

```powershell
Test-NetConnection 127.0.0.1 -Port 6662 -InformationLevel Detailed
docker ps --filter "publish=6662" --format "table {{.Names}}`t{{.Ports}}`t{{.Status}}"
```

Confirm that `TcpTestSucceeded` is `True` and the expected Mirth container publishes port `6662`. A running container by itself does not prove the listener is reachable.

## Run the focused regression suite

```powershell
$base = Join-Path $env:TEMP ("pytest-oru-" + [guid]::NewGuid().ToString("N"))
python -m pytest -q `
    .\tests\interoperability\test_live_oru_scenario_contract.py `
    .\tests\interoperability\test_meditech_style_source_contract.py `
    --basetemp $base
```

Recorded result, October 13, 2026: **8 passed in 5.95 seconds**. It covered six accepted ORU runtime scenarios and two source-contract tests. These tests validate the Mirth scenario suite; they are not a test of the complete OpenEMR handoff or ACK transport for order `109`.

## Trace an eligible OpenEMR delivery

For a fresh synthetic order, register its OpenEMR target mapping **before** sending the ORU. The local queue trigger creates a delivery item when an accepted message is inserted while its mapping is active. Registering a mapping after message insertion does not retroactively enqueue that earlier message.

The recorded order-109 delivery used:

```powershell
python -m scripts.hl7.mirth_openemr_delivery deliver `
    --placer-order ORD-MEDITECH-AVERY-109 `
    --confirm-order-id 109 `
    --openemr-container health-it-openemr-lab-openemr-1
```

It returned `DELIVERED`, delivery ID `5`, and final result data for Glucose `92 mg/dL`. A read-only database query and OpenEMR provider view confirmed the result. **Order 109 already has a report/result. Do not rerun delivery or resend this scenario against that order.** Use a new, clean synthetic target and inspect its before-state for a new demonstration.

## Investigate the sender ACK timeout

For order 109, the MLLP sender timed out without receiving response bytes. Mirth logs showed the message was accepted and persisted as `oru_message_id=52`; its postprocessor selected `AA`. This establishes the ACK policy decision, not successful transmission of ACK bytes to the sender. The guarded OpenEMR delivery succeeded later, but it does not close the ACK issue.

When investigating this class of issue:

1. Record the sender timeout and generated message control ID.
2. Correlate that ID with Mirth validation, persistence, and postprocessor logs.
3. Check whether the sender received response bytes; do not infer delivery from an `AA` policy log alone.
4. Check the target mapping and delivery queue separately from MLLP ACK behavior.
5. Inspect the deployed response behavior before retrying. Avoid blind resends where the message may already be persisted.

## Operational limitations

- The source-specific ACK transmission remains unresolved.
- Source-specific replay/conflict testing is not included in this evidence package.
- No source-specific FHIR publication was performed in this workflow.
- This is technical validation, not formal end-user UAT or production readiness approval.
