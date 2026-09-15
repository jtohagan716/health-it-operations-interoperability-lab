# C-CDA Migration and Reconciliation Validation

## Objective

Demonstrate a deterministic migration workflow that transforms a synthetic
source clinical record into C-CDA XML and reconciles clinically significant
source values against the resulting document.

The increment also verifies that incomplete clinical data is not silently
accepted. A target document missing its medication route receives a
`QUARANTINE` disposition.

## Scope

The synthetic source record contains:

- Avery Testpatient demographic data
- One lisinopril medication
- RxNorm medication metadata
- Oral route code `C38288`
- A 10 mg dose
- Two encounters with descriptions and effective times

The implementation includes a synthetic source document, an XSLT
transformation, a generated C-CDA document, a reconciliation utility, an
incomplete negative fixture, and automated contract tests.

This is a controlled laboratory workflow. It does not represent a production
deployment or a general-purpose certified migration engine.

## Successful reconciliation

Observed result:

- Overall status: `PASS`
- All 16 field-level checks passed
- Patient demographic values matched
- Medication identity, route, and dose matched
- Both encounter descriptions and effective times matched

Evidence:

`evidence/ccda-migration/successful-reconciliation.json`

## Controlled quarantine

The negative fixture deliberately omits the medication route.

Observed result:

- Overall status: `QUARANTINE`
- Expected route code: `C38288`
- Actual route code: `null`
- Expected route display: `By Mouth`
- Actual route display: `null`
- Unrelated reconciled fields continued to pass

This demonstrates that loss of clinically significant route information is
reported explicitly rather than accepted as a successful migration.

Evidence:

`evidence/ccda-migration/quarantined-missing-route.json`

## Deterministic transformation

The transformation was repeated using the same source and stylesheet. The
generated target had this SHA-256 digest before and after execution:

`C22A59345DE1C679B40CBF85ED94C14DAD29FF3AD4B5A66F99E6F41597832842`

The hashes were identical, demonstrating byte-for-byte reproducibility for the
controlled input.

Evidence:

`evidence/ccda-migration/deterministic-transformation.json`

## Automated validation

Focused migration tests were executed with warnings treated as errors.

Command:

`python -m pytest -q -W error tests/ccda/test_ccda_migration_source_contract.py tests/ccda/test_ccda_migration_transform.py tests/ccda/test_ccda_migration_reconciliation.py`

Observed result:

`10 passed in 1.26s`

The complete C-CDA test suite was also executed.

Command:

`python -m pytest -q tests/ccda`

Observed result:

`30 passed in 1.39s`

## Conclusion

The controlled migration:

1. Produces deterministic C-CDA XML.
2. Preserves the selected demographic, medication, and encounter values.
3. Reconciles 16 source-to-target fields successfully.
4. Detects missing medication-route information.
5. Quarantines the incomplete document with field-level failure details.
6. Passes the focused and complete C-CDA automated test suites.
