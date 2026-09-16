# Synthetic Clinical History Provisioning Validation

## Validation Status

**PASS**

Deterministic synthetic medication, allergy, and immunization history was
successfully provisioned into the local OpenEMR laboratory environment and
independently reconciled against persisted database state.

## Scope

This validation covers the synthetic clinical-history provisioning workflow
for the 100-patient deterministic test population.

Expected population:

| Domain | Expected Records |
| --- | ---: |
| Medications | 200 |
| Allergies | 100 |
| Immunizations | 200 |
| **Total** | **500** |
| **Patients** | **100** |

The workflow is restricted to the approved `local-lab` environment and the
synthetic patient namespace.

## Guarded Provisioning

Population provisioning requires explicit confirmation of both the expected
patient count and expected record count:

```powershell
python -m scripts.synthetic.clinical_history `
    --commit-population `
    --environment local-lab `
    --confirm-record-count 500 `
    --confirm-patient-count 100
```

The population operation submits one guarded synthetic-patient manifest at a
time rather than issuing an unrestricted population write.

## Population Reconciliation Validation

The complete provisioning operation was executed again after the synthetic
clinical history was already present in OpenEMR.

Observed aggregate result:

```text
status: POPULATION_COMMITTED
patient_count: 100
record_count: 500

expected_counts:
  medications: 200
  allergies: 100
  immunizations: 200

inserted: 0
reconciled: 500
failed: 0
```

### Result

**PASS**

All 500 expected records were recognized as already present.

The repeat operation:

- inserted 0 additional records;
- reconciled all 500 expected records;
- reported 0 failures.

This demonstrates idempotent provisioning for the validated deterministic
population: repeating the same provisioning operation did not create
additional clinical-history records.

## Independent Database Reconciliation

Persisted OpenEMR state was independently checked directly against MariaDB:

```sql
SELECT 'medications' AS entity_type, COUNT(*) AS record_count
FROM prescriptions
WHERE external_id LIKE 'SYNMED%'

UNION ALL

SELECT 'allergies', COUNT(*)
FROM lists
WHERE type = 'allergy'
  AND external_id LIKE 'SYNALG%'

UNION ALL

SELECT 'immunizations', COUNT(*)
FROM immunizations
WHERE external_id LIKE 'SYNIMM%';
```

Observed result:

```text
entity_type     record_count
medications     200
allergies       100
immunizations   200
```

The synthetic patient population was independently checked with:

```sql
SELECT COUNT(DISTINCT pubpid) AS synthetic_patients
FROM patient_data
WHERE pubpid LIKE 'SYNTHMRN%';
```

Observed result:

```text
synthetic_patients
100
```

## Duplicate Logical-Key Validation

Synthetic logical keys were independently checked across the three persisted
OpenEMR clinical-history domains.

Observed result:

```text
duplicate_logical_keys
0
```

### Result

**PASS**

Every expected synthetic logical key was represented exactly once in the
validated database state.

## Validated Invariants

The validation established the following invariants for this increment:

1. The deterministic population contains exactly 100 synthetic patients.
2. The expected clinical-history population contains exactly 500 records.
3. The expected domain distribution is:
   - 200 medications;
   - 100 allergies;
   - 200 immunizations.
4. Population provisioning is explicitly restricted to the local laboratory
   workflow.
5. Repeating the provisioning operation produces no additional records for
   already-provisioned logical keys.
6. All 500 records reconcile on the repeat execution.
7. Independent database counts match the generated expected state.
8. No duplicate synthetic clinical-history logical keys were detected.

## Engineering Outcome

The increment provides a deterministic and reproducible clinical-history data
foundation for subsequent interoperability and application testing.

Rather than relying only on a successful provisioning command, validation
compares generated expected state, provisioning results, repeat-run
reconciliation behavior, and independently queried OpenEMR database state.

This allows later tests to modify synthetic patient data while retaining a
known, reproducible baseline that can be provisioned and validated again.