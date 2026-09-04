# Synthetic LIS closed-loop transport

This increment connects the deterministic OpenEMR laboratory requisition to a
vendor-neutral synthetic laboratory through Mirth Connect. It is deliberately
implemented as a one-order probe before population-scale execution.

## Boundary model

| Component | Responsibility |
| --- | --- |
| OpenEMR | Authoritative patient, encounter, requisition, and final result state |
| `send_openemr_lab_order.py` | Convert one verified OpenEMR requisition to `OML^O21` and send it over MLLP |
| `LAB_OML_O21_IN` | Validate the lab-order contract, classify replay, return a correlated ACK, and route accepted content |
| PostgreSQL `lis` schema | Persist the synthetic LIS order lifecycle independently of Mirth message state |
| `synthetic_lis.py` | Claim one order, assign a filler number, generate a deterministic result, and send `ORU^R01` |
| `ORU_R01_IN` | Validate and persist the result and enqueue existing guarded OpenEMR delivery |
| `mirth_openemr_delivery.py` | Use the existing confirmed native OpenEMR result-ingestion boundary |

The radiology `ORM^O01` channel remains unchanged. Laboratory orders use the
more appropriate `OML^O21` event on port `6664`; results continue to use the
existing `ORU^R01` channel on port `6662`.

## Safety and reliability controls

- one-order probe before expansion;
- explicit OpenEMR order-ID confirmation;
- database-backed message identity and SHA-256 replay classification;
- exact replay accepted without a duplicate LIS order;
- conflicting reuse rejected;
- stable placer and filler order identifiers;
- PostgreSQL row claiming with `FOR UPDATE SKIP LOCKED`;
- correlated `MSA-2` validation for both order and result ACKs;
- failed result attempts retained for diagnosis and controlled retry;
- existing guarded OpenEMR delivery confirmation;
- database-to-message-to-database reconciliation.

## Installation

Copy the package files into the matching repository paths. Add MLLP port 6664
to the Mirth service by applying `compose-lab-oml-port.patch` or adding:

```yaml
- "6664:6664"
```

Apply the migration to the existing interoperability database. Init-directory
scripts do not rerun automatically for an already-created PostgreSQL volume:

```powershell
Get-Content `
    .\infrastructure\mirth\interop-db\init\019-synthetic-lis-state.sql `
    -Raw |
    docker exec -i `
        health-it-mirth-lab-interop-db-1 `
        psql `
            -v ON_ERROR_STOP=1 `
            -U interop_app `
            -d interop
```

Create the importable Mirth channel from the existing audited ORM channel
shell:

```powershell
python .\scripts\mirth\build_lab_oml_channel.py `
    --source .\infrastructure\mirth\channels\ORM_O01_IN.xml `
    --output .\infrastructure\mirth\channels\LAB_OML_O21_IN.xml
```

Recreate only the Mirth service after exposing the new port:

```powershell
docker compose `
    --env-file .\infrastructure\mirth\.env `
    -f .\infrastructure\mirth\compose.yaml `
    up -d --force-recreate mirth
```

Import and deploy `LAB_OML_O21_IN.xml` in Mirth Administrator. Confirm that it
is listening on `0.0.0.0:6664`.

## Static validation

```powershell
python -m pytest -q `
    .\tests\interoperability\test_synthetic_lis_contract.py
```

## One-order closed-loop probe

First obtain the OpenEMR order ID without sending anything:

```powershell
$labOrder = python -m scripts.synthetic.laboratory_orders --probe --verify |
    ConvertFrom-Json

$order = $labOrder.records.SYNLAB00000101
$order |
    Select-Object order_id, order_external_id, mrn, encounter_number, lab_id
```

Send the order through Mirth, replacing `6` if the displayed order ID differs:

```powershell
python -m scripts.hl7.send_openemr_lab_order `
    --order SYNLAB00000101 `
    --confirm-order-id 6
```

Expected: `status=ACCEPTED`, `ack_code=AA`, and an ACK control ID matching the
outbound OML control ID in `MSA-2`.

Process one order in the synthetic LIS and send its result through Mirth:

```powershell
python -m scripts.hl7.synthetic_lis
```

Expected: `status=RESULT_ACKED`, a stable filler number, and a correlated
`ORU^R01` acknowledgment.

Deliver the accepted ORU through the existing guarded OpenEMR worker. Resolve
the pending delivery and confirmed order ID first; do not guess them:

```powershell
$deliveryRow = docker exec `
    health-it-mirth-lab-interop-db-1 `
    psql -U interop_app -d interop -A -t -F '|' -c `
    "SELECT delivery_id, openemr_order_id FROM audit.openemr_oru_deliveries WHERE delivery_status = 'PENDING' ORDER BY delivery_id LIMIT 1;"

$deliveryId, $confirmedOrderId = $deliveryRow.Trim() -split '\|'

python -m scripts.hl7.mirth_openemr_delivery `
    deliver `
    --delivery-id $deliveryId `
    --confirm-order-id $confirmedOrderId
```

## Replay validation

Resend the same OML with the same message control ID and payload:

```powershell
python -m scripts.hl7.send_openemr_lab_order `
    --order SYNLAB00000101 `
    --confirm-order-id 6
```

The ACK should remain `AA`, while `lis.orders` must still contain exactly one
row for the placer order. The result worker should report that no eligible
order exists after the original result was acknowledged.

## Known limitation: clinical result chronology

The first closed-loop probe preserved transport, correlation, result content,
and clinical persistence correctly. However, the synthetic LIS derived the
ORU observation timestamp from the runtime order-receipt timestamp rather
than the historical clinical order timestamp carried by the OML message.

Consequently, the OpenEMR order and encounter are dated 2025-01-15 while the
result is dated 2026-09-04. OpenEMR correctly preserved the timestamp it
received; this is a simulator chronology issue rather than an identified
OpenEMR defect.

Before population-scale execution, LIS state will retain the clinical order
timestamp from OBR-7 and derive a deterministic result timestamp from that
clinical event time. Runtime receipt timestamps will remain separate
operational audit data.

## Scope boundary

This first slice supports one ordered glucose test and one final numeric result.
It does not yet model multi-analyte panels, corrected results, preliminary-to-
final transitions, cancellations, unsolicited results, or population-scale
execution. Those behaviors should be added only after the single-order identity,
ACK, persistence, delivery, and replay contracts are proven end to end.

