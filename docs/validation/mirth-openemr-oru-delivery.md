# Mirth to OpenEMR ORU delivery

This feature connects the accepted side of `ORU_R01_IN` to the guarded OpenEMR ingestion bridge.

The boundary is intentionally two-stage:

1. Mirth validates the inbound ORU and persists only accepted results in the interoperability audit database.
2. The delivery worker claims one accepted result, performs the mandatory OpenEMR dry run, commits once, verifies persistence, and records the outcome.

Mirth never writes OpenEMR tables directly. Quarantined messages never enter the delivery queue. A unique constraint prevents the same accepted Mirth message from being enqueued twice, and the existing bridge blocks replay into an order that already has results.

## Install the migration

Existing PostgreSQL volumes do not rerun init scripts automatically:

```powershell
Get-Content .\infrastructure\mirth\interop-db\init\018-openemr-oru-delivery.sql -Raw |
    docker exec -i health-it-mirth-lab-interop-db-1 `
        sh -lc 'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## Register a new OpenEMR order before sending its result

Use a fresh OpenEMR order with no results. The inbound ORU's OBR-2 must equal `--placer-order`.

```powershell
python -m scripts.hl7.mirth_openemr_delivery register-target `
    --placer-order 4 `
    --order-id 4 `
    --patient-id 1 `
    --encounter-id 6 `
    --lab-id 2 `
    --patient-identifier LAB000001 `
    --patient-family-name Testpatient `
    --patient-given-name Avery `
    --patient-date-of-birth 19800115 `
    --patient-sex M `
    --confirm-order-id 4
```

## Send through Mirth, then deliver

Send an accepted ORU to Mirth port 6662 with `OBR-2` set to the registered placer order. The trigger automatically creates one pending delivery.

```powershell
python -m scripts.hl7.mirth_openemr_delivery deliver `
    --confirm-order-id 4
```

The command fails closed if correlation, dry-run validation, commit verification, or replay protection fails. Inspect the ledger with:

```sql
SELECT delivery_id, oru_message_id, openemr_order_id,
       delivery_status, attempt_count, last_error,
       openemr_control_id, report_count, result_count
FROM audit.openemr_oru_deliveries
ORDER BY delivery_id DESC;
```

## What this proves

A successful live run proves the result traveled through the actual chain: lab ORU -> Mirth validation -> accepted audit row -> guarded delivery worker -> OpenEMR native DORN parser -> Pending Review. It does not claim continuous background delivery; this version runs the worker explicitly, one claimed message at a time.


## Live end-to-end validation — 2026-09-01

Validated using OpenEMR Order 4 for Avery Testpatient:

- Mirth accepted the ORU over MLLP and returned AA.
- Mirth persisted glucose 90 mg/dL with a 70-99 reference range.
- The delivery trigger queued the accepted result for OpenEMR.
- A repeated logical result produced two audit messages, but the delivery boundary allowed only one active delivery.
- The older duplicate was marked FAILED before reaching OpenEMR.
- Delivery 2 passed the mandatory OpenEMR dry run and committed successfully.
- OpenEMR created exactly one procedure_report and one procedure_result.
- The result appeared in the provider Pending Review workflow.
- Provider signing changed review_status from received to reviewed.

Verified identifiers:

- OpenEMR order: 4
- OpenEMR report: 2
- OpenEMR result: 2
- Delivery: 2
- Filler/control ID: LAB-ORDER-4-RESULT-001
- Procedure: 2345-7 Glucose
- Result: 90 mg/dL
- Report status: final
- Result status: final
- Provider review status: reviewed

A separate full-suite run exposed one delayed MLLP acknowledgment under load. Mirth logs proved that the message was persisted and an AA was generated after the sender timed out. An isolated retry and the complete five-scenario live test subsequently passed. This is retained as reliability evidence rather than treated as message loss.
