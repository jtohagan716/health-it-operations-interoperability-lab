# OpenEMR MariaDB Patient Name Search Performance Study

## Executive summary

This study evaluated patient last-name search behavior in a local OpenEMR laboratory using MariaDB 11.8.8, a deterministic 50,000-patient synthetic population, the existing `idx_patient_name (lname, fname)` index, direct database measurements, and an isolated Playwright browser workflow.

The existing composite name index supported every evaluated last-name prefix query with a range access plan. No test produced a no-index or no-good-index warning. First-page searches remained inexpensive at the database layer, including common, medium-frequency, rare, broad-prefix, high-collision full-name, and absent-value cases. Deep offset pagination became more expensive as MariaDB examined progressively more index entries, but it continued to use the intended index. Count queries were also index-supported and completed in less than one millisecond on average in this environment.

An isolated OpenEMR performance site was then connected to a cloned database containing the same 50,000-patient fixture. A Playwright workflow authenticated through the real web client, opened Patient Search, submitted a `Smith` last-name search, and validated the first 100 rendered results. Four sequential qualification runs all passed. Finder completion ranged from 7.725 to 8.518 seconds and averaged 8.165 seconds. The corresponding isolated database search averaged approximately 1.58 milliseconds. The difference demonstrates that the observed end-user latency is dominated by work above the isolated SQL operation, but this study does not attribute that time to a particular PHP, OpenEMR, HTTP, browser, or rendering component.

The evidence does not justify adding another patient-name index. The responsible next step is targeted application-layer observation of the existing finder workflow, not speculative schema modification.

## Research question

The study asked whether realistic patient-name distributions materially changed the behavior of OpenEMR patient search, whether the existing `(lname, fname)` index remained appropriate, and how isolated database performance compared with timing observed through the actual OpenEMR browser workflow.

## Scope

The evaluated scope was deliberately narrow:

- synthetic patient first and last names;
- last-name prefix search;
- combined last-name and first-name prefix search;
- first-page result retrieval;
- offset pagination;
- matching-row count queries;
- execution plans and MariaDB statement measurements;
- one isolated OpenEMR browser workflow using a common surname.

The study did not benchmark production traffic, concurrent browser users, remote networks, every OpenEMR patient-search field, first-name-only search, or alternative database engines. It did not modify the live `openemr` patient population or establish a production service-level objective.

## Environment

- Host: Windows 11 development workstation
- Application: local containerized OpenEMR laboratory
- Database: MariaDB 11.8.8
- Browser automation: Playwright with Chromium
- Primary database fixture: 50,000 synthetic patients
- Browser target database: `openemr_ui_performance_lab`
- Browser target site: `performance`
- Result page size: 100 rows
- Browser execution model: one worker, sequential execution

The host was memory constrained during portions of the study. Recorded free physical memory was commonly below 1 GB. Timing results therefore describe this controlled laboratory and must not be generalized as production OpenEMR performance.

## Deterministic realistic-name fixture

The original performance population used uniform numbered values such as `PerfFirst0001` and `PerfLast00001`. Although deterministic, those names did not exercise realistic frequency skew or name collisions.

The replacement fixture used normalized aggregate U.S. Census Bureau 2020 name-frequency data. It contained 1,000 given names and 10,000 surnames. A versioned seed and SHA-256-derived selection created a reproducible 55,000-row PID-to-name map while ensuring that every pool entry appeared in the primary 50,000-patient population.

For seed `openemr-performance-names-20260923-v1`, the mapping SHA-256 was:

`96b56856bf9cd83e4b9e1e43ecc8eb977127db7ea90d61f05149b7ad0ac02468`

Two independent builds produced byte-identical output. An alternate seed produced a different mapping, confirming both same-seed determinism and seed sensitivity. The primary population contained:

- 50,000 unique patient identifiers;
- 50,000 unique medical-record numbers;
- 1,000 distinct given names;
- 10,000 distinct surnames;
- 47,840 distinct full-name combinations;
- 2,160 rows participating in duplicate full-name combinations;
- zero blank names; and
- zero remaining legacy `PerfFirst` or `PerfLast` values.

Shared patients were reconciled across the three benchmark tables with zero name or MRN mismatches.

## Existing schema and candidate index

The evaluated table already contained the composite secondary index:

```sql
KEY idx_patient_name (lname, fname)
```

This ordering is suitable for last-name equality and left-anchored last-name prefix predicates. It can also constrain first name after the leading last-name component is supplied. It is not intended to optimize first-name-only search, which was outside this study.

## Experimental controls

The database work used the following controls:

- fixed fixture content and recorded hashes;
- exact scenario definitions;
- warm-up operations before measured execution;
- Performance Schema statement timing;
- 100 measured executions per scenario;
- exact sample-count checks;
- execution-plan capture;
- rows-examined and rows-sent capture;
- no-index and no-good-index warning checks;
- sequential scenario execution on a single host;
- database health checks; and
- ignored evidence artifacts with SHA-256 manifests.

Insert and update comparisons alternated indexed and comparison-table execution order. Alternation reduced systematic cache, warm-up, checkpoint, and sequencing bias: neither variant was always given the advantage or penalty associated with running first or second. It did not eliminate environmental noise, but it prevented execution position from being perfectly confounded with index state.

The browser qualification used:

- an isolated cloned OpenEMR database;
- a separate `performance` site configuration;
- one Playwright worker;
- sequential runs;
- a 240-second test allowance for the constrained host;
- 90-second authentication response allowance;
- suppression of one known background run during measurement;
- exact result-count and displayed-prefix assertions; and
- no patient-chart selection or clinical-data mutation.

## Search scenarios

Seven first-page scenarios were measured:

1. Common surname prefix: `Smith%`
2. Medium-frequency surname prefix: `Barnes%`
3. Rare surname prefix: `Abate%`
4. Broad two-character prefix: `Ma%`
5. Broad three-character prefix: `Wil%`
6. High-collision full name: `Smith%` and `Michael%`
7. Absent surname prefix

Pagination scenarios covered `Ma%` at offsets 0, 100, 500, 1,000, and 1,500; `Smith%` at offsets 0, 100, and 400; and `Wil%` at offset 600. Count scenarios covered `Ma%`, `Smith%`, and `Wil%`.

## Execution-plan results

All seven first-page scenarios used `idx_patient_name` with range access and index condition evaluation. Estimated rows reflected predicate selectivity:

| Scenario | Estimated rows | Access | Index |
|---|---:|---|---|
| `Smith%` | 473 | range | `idx_patient_name` |
| `Barnes%` | 40 | range | `idx_patient_name` |
| `Abate%` | 1 | range | `idx_patient_name` |
| `Ma%` | 1,552 | range | `idx_patient_name` |
| `Wil%` | 700 | range | `idx_patient_name` |
| `Smith%` and `Michael%` | 473 | range | `idx_patient_name` |
| Absent prefix | 1 | range | `idx_patient_name` |

Count queries used the same index with `Using where; Using index`, allowing the count to be satisfied from index entries without retrieving full table rows.

## First-page database results

Each scenario contained 100 measured executions.

| Scenario | Average ms | P95 ms | Average rows examined | Average rows sent |
|---|---:|---:|---:|---:|
| Common surname `Smith%` | 1.580 | 2.022 | 100 | 100 |
| Medium surname `Barnes%` | 0.846 | 1.028 | 40 | 40 |
| Rare surname `Abate%` | 0.325 | 0.423 | 1 | 1 |
| Broad prefix `Ma%` | 1.662 | 2.101 | 100 | 100 |
| Broad prefix `Wil%` | 1.593 | 1.945 | 100 | 100 |
| Full name `Michael Smith` | 0.645 | 0.808 | 12 | 12 |
| Absent prefix | 0.278 | 0.378 | 0 | 0 |

No scenario reported `NO_INDEX_USED` or `NO_GOOD_INDEX_USED`.

## Pagination results

Offset pagination remained index-supported, but rows examined increased with the requested offset because MariaDB had to advance through earlier matching entries before returning the requested page.

| Prefix and offset | Average ms | Average rows examined | Rows sent |
|---|---:|---:|---:|
| `Ma%`, 0 | 1.443 | 100 | 100 |
| `Ma%`, 100 | 1.947 | 200 | 100 |
| `Ma%`, 500 | 4.470 | 600 | 100 |
| `Ma%`, 1,000 | 5.656 | 1,100 | 100 |
| `Ma%`, 1,500 | 13.637 | 1,552 | 52 |
| `Smith%`, 0 | 1.857 | 100 | 100 |
| `Smith%`, 100 | 2.630 | 200 | 100 |
| `Smith%`, 400 | 3.753 | 473 | 73 |
| `Wil%`, 600 | 4.859 | 700 | 100 |

Prefix reconciliation confirmed that `Smith%` matched 473 rows: 470 `Smith`, plus one each of `Smitherman`, `Smithers`, and `Smithson`. This reconciled the difference between exact-surname and prefix counts and validated the final 73-row page at offset 400.

The behavior is expected for offset pagination and does not indicate a missing index. If substantially deeper pages become an operational requirement, cursor or keyset pagination should be evaluated at the application-design level.

## Count-query results

Each count scenario contained 100 measurements.

| Prefix | Expected count | Average ms | P95 ms | Rows examined |
|---|---:|---:|---:|---:|
| `Ma%` | 1,552 | 0.699 | 0.934 | 1,552 |
| `Smith%` | 473 | 0.291 | 0.442 | 473 |
| `Wil%` | 700 | 0.309 | 0.363 | 700 |

All counts were correct and index-supported, with no index warnings.

## Isolated OpenEMR browser environment

The live `openemr` schema was protected throughout the browser phase. A new `openemr_ui_performance_lab` schema was created by cloning all 286 OpenEMR tables. Its `patient_data` table was replaced with the deterministic 50,000-patient fixture. Validation showed 101 patients in the default database and 50,000 in the performance database.

The existing `openemr` database account received privileges only on the isolated schema. A separate `performance` site directory was copied from the default site. Comparison after removing the single database-assignment line produced identical SHA-256 values, proving that only the target database assignment differed between the two site configurations.

Both login routes returned HTTP 200:

- `/interface/login/login.php?site=default`
- `/interface/login/login.php?site=performance`

A short, controlled MariaDB general-log capture proved that the performance route connected to `openemr_ui_performance_lab`. The original general-log configuration was restored afterward. The live patient table was not modified.

## Playwright browser qualification

The Playwright workflow performed these user-visible actions:

1. Opened the `performance` site login page.
2. Authenticated with local laboratory credentials supplied through environment variables.
3. Waited for the authenticated OpenEMR shell to become usable.
4. Opened Patient Search.
5. Entered `Smith` in the last-name field.
6. Submitted the finder search.
7. Waited for the finder result frame.
8. Asserted exactly 100 rendered first-page rows.
9. Asserted that every displayed result name began with `Smith,`.
10. Stopped before selecting or modifying a patient.

The initial 30-second authentication attempt timed out. Repeating the same workflow with a 90-second allowance passed, showing that the original failure was a timing boundary on the constrained host rather than rejected credentials. This failure was preserved as evidence.

The first successful Smith pilot reported a 10.329-second finder duration. Four subsequent sequential qualification runs produced:

| Run | Finder duration ms | Result validation |
|---:|---:|---|
| 1 | 8,485 | 100 rows; all names matched |
| 2 | 7,725 | 100 rows; all names matched |
| 3 | 8,518 | 100 rows; all names matched |
| 4 | 7,930 | 100 rows; all names matched |

The repeated-run minimum was 7.725 seconds, the average was 8.165 seconds, and the maximum was 8.518 seconds. The 0.793-second range indicates reasonably stable repeated behavior for this host. Four samples are sufficient to demonstrate repeatability but are not sufficient for defensible browser-layer percentile claims.

## Cross-layer interpretation

The isolated database `Smith%` first-page operation averaged approximately 1.58 milliseconds, while the repeated browser finder workflow averaged approximately 8.165 seconds from search submission to validated result readiness.

These measurements have different boundaries. The database measurement isolates statement execution. The Playwright measurement includes request dispatch, PHP and OpenEMR processing, session handling, HTML generation, network transfer through the local container boundary, iframe attachment, browser parsing, JavaScript behavior, DOM construction, and the wait until the result was assertable.

It is therefore valid to conclude that the indexed SQL statement is not the dominant component within the observed browser interval. It is not valid to assign the remaining time to any single component without additional instrumentation. In particular, this study does not establish an OpenEMR product defect or a production performance expectation.

## Failed approaches and corrections

Failures were retained as engineering evidence rather than discarded:

- A metrics query used `row_number` as an alias and failed under MariaDB syntax rules. Renaming the alias corrected the query.
- An exact SQL-comment filter returned zero Performance Schema events because statement normalization removed the distinguishing comment. A structural query filter recovered the controlled pilot events.
- The rolling statement-history buffer did not reliably preserve the later UI query long enough for correlation.
- A digest search initially matched schema-definition text containing `lname`, demonstrating that broad digest matching was not reliable evidence of a finder SELECT.
- A short MariaDB general-log capture was used instead to prove the performance-site database route, and the original logging configuration was restored.
- Several `docker exec ... sh -lc` multiline scripts were split incorrectly by PowerShell argument handling. Stdin-based execution or discrete container commands corrected the issue.
- BusyBox `sed` did not support GNU-style `-o`; host-side PowerShell comparison was used instead.
- The first Playwright invocation reported no tests because a Windows path was interpreted as a regular expression. A repository-relative filename selector corrected discovery.
- The first authentication run exceeded the default 30-second test timeout. A documented, bounded 90-second authentication allowance succeeded.
- Early HTTP validation used an incorrect `/openemr/` path. The container document root already mapped to OpenEMR, so the correct routes began at `/interface/`.

These corrections strengthened the final method by showing which observation mechanisms were reliable in this environment.

## Evidence integrity

The study recorded command outputs, exit codes, timestamps, file lengths, and SHA-256 values in ignored `artifacts/performance` files. Important evidence included fixture profiling, deterministic-map qualification, scenario and execution-plan matrices, first-page measurements, pagination measurements, count measurements, isolated-database construction, database-route proof, authentication failures and recovery, the successful Smith pilot, and the four-run sequential browser qualification.

Generated evidence remained outside Git because it contains environment-specific runtime output. The tracked report and opt-in Playwright test describe how the conclusions were obtained, while the local evidence manifest preserves file-level integrity.

## Limitations

- Results apply to one local, memory-constrained Windows and Docker environment.
- The fixture models aggregate name frequency and collision behavior; it is not a demographic or epidemiological population model.
- Browser measurements used Chromium, one worker, and a local network path.
- Only one browser-level surname scenario was repeatedly qualified.
- Four repeated browser samples support repeatability but not tail-percentile estimation.
- Background activity was partly controlled, not eliminated.
- Performance Schema history was unsuitable for durable UI-to-query correlation in this run.
- No concurrent-user browser load was applied.
- No production data or production OpenEMR deployment was tested.

## Conclusion

The existing `idx_patient_name (lname, fname)` index is appropriate for the evaluated OpenEMR last-name and combined-name prefix searches. All database scenarios used index-supported range plans, returned correct results, and avoided index warnings. An additional patient-name index is not justified by this evidence.

Deep offset pagination showed the expected increase in rows examined and latency. That behavior should be addressed through pagination design only if real usage demonstrates a need; it should not be treated as proof of an indexing failure.

The isolated browser workflow was correct and repeatable but took approximately eight seconds from search submission to validated results on this host. Because the corresponding SQL work completed in roughly 1.58 milliseconds, any continued investigation should focus above the isolated database statement while preserving cross-layer timing boundaries.

## Recommended next actions

1. Commit the browser qualification as an opt-in Playwright test that cannot run accidentally against an ordinary site.
2. Retain the existing `(lname, fname)` index; do not add a speculative duplicate index.
3. If further diagnosis is warranted, add bounded server-side timing around the patient finder request and result rendering.
4. Correlate one browser run with PHP/application timing and database timing using a unique run identifier designed to survive statement normalization.
5. Evaluate keyset pagination only if production-like evidence shows that users routinely request deep result pages.
6. Repeat browser measurements on a less memory-constrained host before defining any performance threshold.
7. Keep the synthetic fixture, test, report, and evidence-generation procedure deterministic and reviewable.

## Professional significance

This was a legitimate performance-engineering investigation rather than a sequence of disconnected timing tests. It replaced an unrealistic fixture with deterministic frequency-weighted data, validated database integrity, examined execution plans, measured representative and adversarial search cases, controlled execution order, reconciled unexpected counts, protected the live dataset, built an isolated application environment, exercised the real browser workflow, preserved failed approaches, and limited conclusions to what the evidence supported.

The strongest professional outcome is not a claim that an index made OpenEMR faster. It is the demonstrated ability to separate database, application, and browser measurement layers; recognize invalid observation methods; correct them without concealing failures; and decline an unnecessary schema change when the data did not support it. Those are directly transferable quality, reliability, application-support, and performance-engineering skills.
