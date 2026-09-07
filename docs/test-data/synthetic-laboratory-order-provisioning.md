# Synthetic laboratory-order provisioning

This issue #31 increment establishes the first vendor-neutral laboratory-order
baseline for the deterministic OpenEMR population. It creates one glucose
requisition for the first historical encounter of each synthetic patient while
keeping order persistence separate from message transport and result creation.

## Delivered phase

| Entity | Count |
|---|---:|
| Synthetic patients represented | 100 |
| Parent laboratory requisitions | 100 |
| Ordered-test lines | 100 |
| Result observations | 0 |

Each requisition contains one glucose ordered-test line using LOINC `2345-7`.
This phase deliberately does not claim completion of the population contract's
future targets of 450 ordered-test lines and 500 result observations. Those
targets require clinically appropriate panels and result cardinalities rather
than repeated copies of a single glucose test.

## Persistence model

The increment distinguishes three levels that are sometimes all described as
“lab orders”:

| Clinical level | OpenEMR representation |
|---|---|
| Requisition | `procedure_order` |
| Ordered test | `procedure_order_code` |
| Atomic result observation | `procedure_result` |

The parent order uses a stable `SYNLAB` external identifier. Its ordered-test
line, patient, encounter, ordering provider, laboratory, diagnosis, timestamp,
and `forms` registration are independently reconciled after persistence.

## Vendor-neutral laboratory configuration

The receiver resolves or creates a separate `Synthetic Interoperability
Laboratory` procedure provider with receiving application `SYNLIS`. Existing
DORN and radiology configurations are preserved and are not reused, renamed, or
modified.

The laboratory is a local test dependency. It has no fabricated NPI, remote
credentials, or production endpoint.

## OpenEMR boundary

OpenEMR does not expose a general procedure-order insertion method through
`ProcedureService`. The guarded receiver therefore follows the native
procedure-order form boundary:

- the parent `procedure_order` field contract follows `common.php`;
- UUID creation uses `UuidRegistry`;
- `addForm()` creates the encounter form registration;
- native `insertProcedureOrderCode()` creates the ordered-test line;
- exact database postconditions are verified before commit.

The adapter is restricted to the local synthetic environment. It does not send
the order, invoke DORN, create results, or write billing and charge records.

## Safety controls

- local synthetic environment only
- dry run by default
- one-patient probe
- exact commit-count confirmation
- persisted synthetic patient marker
- existing encounter, provider, and diagnosis preconditions
- stable external identifiers
- vendor-neutral laboratory configuration
- native ordered-test save function
- database transaction
- reverse-order compensating cleanup
- exact post-write relationship verification
- idempotent replay
- no result, billing, claim, or external-transmission writes

## Commands

Dry run:

```powershell
python -m scripts.synthetic.laboratory_orders
```

One-patient probe:

```powershell
python -m scripts.synthetic.laboratory_orders --probe --commit --environment local-lab --confirm-patient-count 1
```

Verify the probe:

```powershell
python -m scripts.synthetic.laboratory_orders --probe --verify
```

Replay the probe:

```powershell
python -m scripts.synthetic.laboratory_orders --probe --commit --environment local-lab --confirm-patient-count 1
```

Full phase, after probe acceptance:

```powershell
python -m scripts.synthetic.laboratory_orders --commit --environment local-lab --confirm-patient-count 100
```

Full verification:

```powershell
python -m scripts.synthetic.laboratory_orders --verify
```

## Next closed-loop increment

After native order persistence is accepted, the order will be exported as a
vendor-neutral `OML^O21` message and sent over MLLP to a dedicated Mirth
laboratory channel. A stateful synthetic LIS adapter will assign the filler
identifier and use the existing ORU scenario engine to return a correlated
result through Mirth and OpenEMR's native result-ingestion path.

That increment will validate the complete lineage:

```text
OpenEMR requisition
    -> OML^O21
    -> Mirth order audit
    -> synthetic LIS state
    -> ORU^R01
    -> Mirth result audit
    -> OpenEMR report and result
    -> FHIR DiagnosticReport and Observation
```

## Validation evidence

The one-patient probe created and independently verified:

- laboratory `Synthetic Interoperability Laboratory` with receiving application
  `SYNLIS`;
- glucose orderable LOINC `2345-7` with `mg/dL` units and `70-99` reference
  range;
- placer order `SYNLAB00000101` for `SYNTHMRN000001`;
- encounter relationship to `SYNENC00000101`;
- diagnosis `ICD10:Z00.00`;
- native OpenEMR UUID and procedure-order form registration.

The full population commit produced the following outcome:

| Evidence | Observed value |
|---|---:|
| Expected patients | 100 |
| Expected requisitions | 100 |
| Expected ordered-test lines | 100 |
| Resolved requisitions | 100 |
| Existing probe requisitions | 1 |
| Newly created requisitions | 99 |
| Initial full commit elapsed time | 30.10 seconds |

Independent verification returned 100 of 100 expected requisitions. Direct
database reconciliation established:

- 100 represented patients and 100 unique order external identifiers;
- exactly 10 patients, requisitions, and ordered-test lines in each cohort;
- 100 qualified `forms` registrations;
- zero duplicate order identifiers;
- zero patient, encounter, laboratory, ordered-test, diagnosis, or form
  relationship violations;
- zero order/encounter chronology violations;
- blank remote host, login, and password values for the synthetic laboratory.

A complete replay resolved all 100 requisitions as `EXISTING`, created zero new
records, and completed in 15.58 seconds. These elapsed times are operational
observations from the local environment, not performance benchmarks.

The focused synthetic-population regression suite completed with 111 passing
tests, including 19 laboratory-order contract tests.
