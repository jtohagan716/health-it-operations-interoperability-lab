Census-derived patient-name performance fixtures

Purpose

The OpenEMR performance population originally used numbered values such as
PerfFirst0001 and PerfLast00001. Those values were deterministic, but their
uniform and visibly artificial distribution was unsuitable for evaluating the
existing (lname, fname) patient-search index.

This fixture replaces only the synthetic first and last names. It preserves
patient identifiers, medical-record numbers, table sizes, and the established
name cardinalities used by the earlier MRN benchmark.

Sources

The normalized pools are derived from the U.S. Census Bureau's aggregate 2020
name-frequency tables:

Names2020_FirstNames_Sex.xlsx

Names2020_LastNames_RaceHispanic.xlsx

Source page:

https://www.census.gov/topics/population/genealogy/data/2020_names.html

These tables contain aggregate frequency statistics and do not contain patient
records or individual-level source data. The downloaded workbooks remain under
the ignored artifacts/performance-name-sources/ directory.

The source SHA-256 values used for this fixture are recorded in
fixtures/performance/names/manifest.json. The committed normalized pools also
have recorded SHA-256 values.

Normalization

Run:

python -m scripts.performance.normalize_census_names `
    --first-names <first-name-workbook> `
    --last-names <last-name-workbook> `
    --output-directory fixtures/performance/names

The normalizer uses only the Python standard library. It reads the first XLSX
worksheet directly, selects the canonical name, rank, and frequency columns,
normalizes display capitalization, rejects invalid or duplicate values, and
writes stable UTF-8 CSV output.

The committed pools contain exactly:

1,000 given names;

10,000 surnames.

Deterministic mapping

build_patient_name_map.py creates a 55,000-row PID-to-name map using Census
frequency counts and a versioned seed. Every pool entry occurs within the
primary 50,000-patient population, while the remaining assignments preserve a
nonuniform frequency distribution. The algorithm uses SHA-256-derived integer
selection rather than process-dependent random state.

For seed openemr-performance-names-20260923-v1, the mapping SHA-256 is:

96b56856bf9cd83e4b9e1e43ecc8eb977127db7ea90d61f05149b7ad0ac02468

The primary population contains 1,000 distinct given names, 10,000 distinct
surnames, and 47,840 distinct full-name combinations.

Database safeguards

apply_patient_name_map.py defaults to a read-only dry run. A commit requires
explicit confirmation of both the database name and expected row count. Before
writing, it exports and hashes the original names. The update:

operates only on openemr_performance_lab;

changes only fname and lname;

updates all three benchmark tables in one transaction;

asserts the 50,000/55,000/55,000 table sizes;

checks every updated name against the temporary mapping;

checks shared patient consistency across the tables;

reconciles every persisted PID/name pair after commit.

Validation result

The applied fixture retained unique PID and MRN counts, produced no missing
names, left zero legacy PerfFirst or PerfLast values, and produced zero
shared-name or shared-MRN mismatches. Runtime mappings, source workbooks, and
database backups remain excluded from Git under artifacts/.

Limitations

The fixture models name-frequency and name-collision behavior for controlled
search testing. It is not a demographic population model, does not preserve
relationships between names and other demographic attributes, and must not be
interpreted as representative patient or epidemiological data.