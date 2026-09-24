# OpenEMR Patient Name-Search Latency Attribution

## Executive summary

This investigation measured the OpenEMR patient finder across browser, HTTP, application-source, and MariaDB layers using an isolated 50,000-patient performance site.

The workflow searched for `Smith%`, validated 473 matching patients, and verified that the first page rendered 100 correct rows.

A controlled four-run comparison found:

| Condition | Average finder time |
|---|---:|
| Normal audit logging | 11,122.5 ms |
| Temporary audit bypass | 2,906.5 ms |
| Observed reduction | 73.9% |

The bypass was temporary and scoped to the finder request. The original finder source was restored byte-for-byte.

This study does not recommend disabling audit logging. It identifies synchronous per-query auditing as a major contributor to the measured latency.  A subsequent post-merge validation phase confirmed that the attribution instrumentation operated consistently on the merged `main` branch across four additional successful Chromium executions.

## Scope

The test used:

- OpenEMR performance site
- MariaDB isolated performance database
- 50,000 synthetic patients
- `Smith%` surname search
- 473 expected prefix matches
- 100 expected first-page rows
- Playwright Chromium
- Browser Navigation Timing
- Browser Long Tasks API
- MariaDB general-log inspection
- Read-only OpenEMR source inspection

No production data was used.

## Browser instrumentation

The Playwright test recorded:

- request observed;
- response headers observed;
- iframe attached;
- first result row visible;
- 100 rows present;
- validation complete;
- response transfer timing;
- DOM lifecycle timing;
- browser long tasks.

The initial instrumentation produced a negative interval because iframe attachment occurred before response-header observation. The interval model was corrected to preserve raw timestamps and report only valid event-order durations.

## Four-run normal baseline

| Metric | Minimum | Average | Maximum |
|---|---:|---:|---:|
| Request to response headers | 618 ms | 2,352 ms | 7,205 ms |
| Request to iframe attached | 1,076 ms | 1,195.5 ms | 1,375 ms |
| Iframe to first row | 124 ms | 1,687.5 ms | 6,230 ms |
| First row to 100 rows | 6,668 ms | 7,659 ms | 10,425 ms |
| Finder total | 8,536 ms | 11,122.5 ms | 18,444 ms |
| Response transfer | 7,082.8 ms | 7,953 ms | 10,342.2 ms |
| Long-task total | 348 ms | 387.8 ms | 422 ms |

Browser long tasks were present but did not explain most of the finder latency.

## Source inspection

The patient finder performs four additional per-patient queries when rendering the default result style:

1. Last encounter with billing.
2. Last encounter without billing.
3. Distinct billing-date count.
4. Total encounter count.

For 100 displayed patients, this creates approximately 400 per-row queries in addition to the primary search and count queries.

This is an N+1 query pattern.

The SQL path was traced as:

```text
patient_select.php
→ QueryUtils
→ ADODB_mysqli_log::Execute()
→ EventAuditLogger::auditSQLEvent()
→ recordLogItem()
→ LogTablesSink
→ log
→ log_comment_encrypt
Audit-path comparison
OpenEMR already supports a scoped SQL-audit bypass through $skipAuditLog.
The temporary experiment inserted:
$skipAuditLog = true;

at the finder request scope.
Metric	Audit enabled	Audit bypassed
Average finder completion	11,122.5 ms	2,906.5 ms
Average response transfer	7,953.0 ms	522.0 ms
Average first row to 100 rows	7,659.0 ms	358.2 ms


All eight measured runs passed functional validation:
- four normal audit-enabled runs;
- four audit-bypass runs;
- 473 expected prefix matches;
- 100 expected first-page rows;
- all rendered names matched Smith%.
MariaDB general-log correlation
A bounded general-log capture was performed for one normal finder request.
Finder window: 17.5647 seconds
Audit log inserts: 145
Audit comment/checksum inserts: 145
Total paired audit writes: 290

The paired writes correspond to:
INSERT INTO log
INSERT INTO log_comment_encrypt

The general log also recorded prepared-statement lifecycle activity. Prepare, Execute, and Close stmt entries represent protocol activity and should not be counted as independent business queries.
Findings
The evidence supports these conclusions:
1. The patient finder uses an N+1 query pattern.
2. Finder SQL passes through synchronous audit processing.
3. Audit processing creates paired writes to log and log_comment_encrypt.
4. Temporarily bypassing SQL audit logging reduced average finder time by 73.9%.
5. Browser main-thread work did not explain most of the latency.
6. Functional behavior remained correct.
7. The original OpenEMR source was restored exactly.
Recommended remediation order
1. Reduce the N+1 query pattern by batching or joining the per-patient encounter and billing data.
2. Re-measure with normal audit logging enabled.
3. Determine whether fewer SQL statements reduce audit overhead.
4. Review whether repetitive read-only enrichment queries require individual audit events.
5. Evaluate batched or asynchronous audit persistence only after compliance requirements are understood.
6. Preserve audit coverage for authentication, security, patient-record, and modification events.
Limitations
This study does not identify the exact percentage of time consumed by each internal audit operation. Additional profiling would be required to separate:
- event classification;
- bind/comment construction;
- checksum generation;
- audit inserts;
- connection behavior;
- database contention;
- repeated finder-query execution.
The results were collected in an isolated synthetic environment and should not be generalized directly to production without additional validation.
Evidence artifacts
- openemr-name-search-latency-attribution-repeat-4.txt
- openemr-name-search-latency-audit-bypass-repeat-4.txt
- openemr-name-search-audit-comparison.txt
- openemr-name-search-finder-window-audit.txt
Evidence hashes:
Audit comparison:
CC057E9E4026B88766681BB1EABE5F2331F6D9CF6C3D63535BA4528FAECF0F96

Finder-window audit:
BA874B9A4928FEB1B8FB13A40865A66B325D332531BE870A5D2D7DC906645437

Original/restored finder source:
7C6D56C813F17949BD53F92D8A5B6D35D00EDC5B9C856EB103053319D57E70E5

## Post-merge validation of latency-attribution instrumentation

After the latency-attribution test was merged to `main`, the instrumented workflow was executed once as a post-merge pilot and three additional times as repeat validation.

All four executions passed functional validation:

- HTTP status: 200
- Expected performance database rows: 50,000
- Expected `Smith%` prefix matches: 473
- Rendered first-page rows: 100
- All rendered names matched the requested prefix
- Browser long tasks greater than 50 ms: 0

| Run | Finder submit-to-validation |
|---|---:|
| Post-merge pilot | 11,494 ms |
| Repeat 1 | 8,839 ms |
| Repeat 2 | 8,261 ms |
| Repeat 3 | 8,369 ms |

The three repeat runs clustered between 8,261 ms and 8,839 ms. Response-transfer time remained between approximately 7,029 ms and 7,362 ms across the repeat runs. The first post-merge run recorded a slower request-to-response-header interval of 3,164 ms, compared with 604–736 ms in the repeat runs. That variability was retained as observed evidence rather than discarded.

The post-merge results confirm that the attribution instrumentation reliably reports the finder lifecycle, including request observation, response-header timing, iframe attachment, first-row visibility, complete 100-row rendering, browser navigation timing, and long-task observations.

These post-merge measurements validate the test instrumentation. They do not replace the audit-enabled versus audit-bypass experiment and should not be interpreted as a second estimate of the 73.9% audit-related reduction.

Validation status
- Playwright baseline: passed
- Playwright audit-bypass comparison: passed
- Finder restoration: passed
- OpenEMR: healthy
- MariaDB: healthy
- General log: disabled
- Log output: restored to FILE
- git diff --check: passed