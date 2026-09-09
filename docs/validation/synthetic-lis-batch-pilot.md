# Synthetic LIS guarded batch pilot

## Purpose

This increment expands the proven one-order synthetic LIS loop into a small,
guarded batch workflow. It preserves the existing OpenEMR, Mirth Connect,
PostgreSQL, and synthetic-LIS boundaries while adding explicit batch selection,
resume, reconciliation, and stop-on-failure behavior.

The pilot remains intentionally capped at ten fresh orders. It is not a
population-scale execution mechanism.

## Workflow

For each selected laboratory order, the orchestrator performs these stages:

1. Load and verify the authoritative OpenEMR requisition.
2. Register the exact OpenEMR delivery target.
3. Send the `OML^O21` order to `LAB_OML_O21_IN` over MLLP.
4. Confirm a correlated `AA` acknowledgment or reconcile durable acceptance.
5. Claim the exact LIS order and generate its deterministic `ORU^R01` result.
6. Confirm a correlated result acknowledgment or reconcile the exact accepted
   ORU after an ambiguous transport outcome.
7. Deliver the persisted ORU through the guarded OpenEMR ingestion boundary.

## Safety controls

- maximum fresh pilot size of ten orders;
- dry run by default;
- explicit `--commit` required for mutation;
- exact order-count confirmation;
- exact ordered placer-list confirmation for fresh commits;
- one explicitly named placer order for resume;
- fresh selection excludes existing LIS orders;
- stable OML and ORU message-control identifiers;
- exact placer, message-control, ORU, delivery, and OpenEMR-order correlation;
- database-backed recovery after an acknowledgment timeout;
- no ORU resend when the exact ORU is already durably accepted;
- no delivery replay when the exact delivery is already complete;
- stop after the first unresolved failure unless continuation is explicitly
  requested.

## Static validation

```powershell
python -m pytest -q `
    .\tests\interoperability\test_synthetic_lis_batch_contract.py `
    .\tests\interoperability\test_synthetic_lis_contract.py `
    .\tests\interoperability\test_mirth_openemr_delivery.py
```

Observed result:

```text
26 passed
```

The contract suite covers structured stage outcomes, exact target selection,
dry-run non-mutation, maximum pilot size, stop-on-failure behavior, OML timeout
reconciliation, targeted resume, completed-order no-op behavior, exact ORU
correlation, and accepted-ORU recovery without duplicate transport.

## Dry-run contract

Preview fresh orders without mutation:

```powershell
python -m scripts.hl7.synthetic_lis_batch --limit 2
```

The preview returns the exact commit confirmation:

```json
{
  "commit_confirmation": {
    "order_count": 2,
    "placer_orders": [
      "SYNLAB00000901",
      "SYNLAB00001001"
    ]
  }
}
```

An earlier dry run selected `SYNLAB00000601` and `SYNLAB00000701`. Database
counts remained `5|5|6` before and after that preview, proving that selection
did not create LIS orders, acknowledge results, or deliver OpenEMR results.

## Exact selection guard

A commit must confirm both the selected count and the exact ordered placer
list shown by the dry run:

```powershell
python -m scripts.hl7.synthetic_lis_batch `
    --limit 2 `
    --commit `
    --confirm-order-count 2 `
    --confirm-placer-orders `
        SYNLAB00000901 `
        SYNLAB00001001
```

Supplying the same identifiers in reverse order was rejected before transport:

```text
SYNTHETIC LIS BATCH: FAIL - --confirm-placer-orders must match the
selected placer-order list exactly (SYNLAB00000901, SYNLAB00001001).
```

The command returned exit code `1`, and database counts remained `8|8|9`
before and after the rejected attempt.

This guard was added after runtime testing demonstrated that a fresh order can
acquire durable state between preview and commit. Count-only confirmation was
safe because existing orders were excluded, but it did not guarantee that the
commit processed the exact previewed identities.

## Successful two-order execution

A two-order committed pilot completed without an unresolved failure:

| Evidence | `SYNLAB00000701` | `SYNLAB00000801` |
| --- | --- | --- |
| OpenEMR order ID | `12` | `13` |
| OML acknowledgment | correlated `AA` | correlated `AA` |
| LIS order ID | `9` | `10` |
| ORU control ID | `SYNLIS-ORU-000009-01` | `SYNLIS-ORU-000010-01` |
| Result | `85 mg/dL` | `86 mg/dL` |
| ORU audit ID | `119` | `120` |
| Delivery ID | `8` | `9` |
| OpenEMR result | final, non-abnormal | final, non-abnormal |

The batch summary reported two attempted orders, two completed orders, zero
failed orders, and final stage `OPENEMR_DELIVERED` for each order.

## Ambiguous ORU acknowledgment recovery

The targeted resume of `SYNLAB00000601` produced a real ambiguous transport
outcome. The client timed out without receiving acknowledgment bytes and
recorded the LIS attempt as failed. Durable evidence showed that Mirth had
completed the clinical transaction:

| Evidence | Observed value |
| --- | --- |
| LIS order ID | `8` |
| Initial LIS state | `FAILED` |
| Result attempt count | `1` |
| ORU control ID | `SYNLIS-ORU-000008-01` |
| ORU audit ID | `121` |
| ORU processing state | `ACCEPTED` |
| Mirth validation | `PASS` |
| Mirth ACK policy | correlated `AA` |
| Initial delivery ID/state | `10`, `PENDING` |

The guarded resume correlated the exact placer number and message-control ID,
reported `RESULT_ACKED_AFTER_DURABLE_ACCEPTANCE`, advanced the durable LIS state
to `RESULT_ACKED`, skipped ORU retransmission, and delivered the
already-persisted message to OpenEMR.

Final evidence:

| Evidence | Observed value |
| --- | --- |
| Final LIS state | `RESULT_ACKED` |
| Result acknowledgment | `AA`, `SYNLIS-ORU-000008-01` |
| Final delivery state | `DELIVERED` |
| OpenEMR order ID | `11` |
| OpenEMR report/result IDs | `10` / `10` |
| Persisted result | `84 mg/dL`, final, non-abnormal |

This demonstrates the distinction between a failed client observation and a
failed clinical transaction. Recovery uses authoritative durable state rather
than blindly replaying a message after a socket timeout.

## Resume usage

Inspect one existing order without mutation:

```powershell
python -m scripts.hl7.synthetic_lis_batch `
    --resume-placer-order SYNLAB00000601
```

Commit a guarded resume only after reviewing its durable state:

```powershell
python -m scripts.hl7.synthetic_lis_batch `
    --resume-placer-order SYNLAB00000601 `
    --commit `
    --confirm-order-count 1
```

If a committed operation times out, do not immediately repeat it. Run the
read-only resume first and inspect the correlated LIS, ORU, and delivery state.

## Scope boundary

The pilot supports deterministic, final, single-analyte glucose results for a
small explicitly confirmed order set. It does not yet implement multi-analyte
panels, preliminary-to-final transitions, corrections, cancellations,
unsolicited results, parallel workers, or population-scale scheduling.
