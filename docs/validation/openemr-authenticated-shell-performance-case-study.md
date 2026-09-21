# OpenEMR Authenticated-Shell Performance Investigation

## Executive summary

This case study documents a controlled performance investigation of the OpenEMR authenticated shell across clean, isolated Docker environments. The work reproduced a substantial delay in OpenEMR 8.2.0 and 8.3.0, localized most of the server-side time to access-control processing during navigation-menu construction, and verified that OpenEMR 8.4.0 and 8.4.1 no longer exhibit the delay.

The investigation did **not** identify an unresolved defect requiring a new OpenEMR fix. Source comparison showed that OpenEMR 8.4 introduced request-level memoization for the repeatedly evaluated superuser ACL probe. That upstream change is consistent with both the measured bottleneck in 8.3 and the large improvement measured in 8.4.

## Purpose

The original objective was to determine why an automated patient-chart workflow sometimes appeared to pause after authentication. The investigation evolved from browser-level timing into a controlled, version-specific server-side analysis.

The principal questions were:

1. Was the delay real application behavior or a Playwright artifact?
2. Which request and server-side operation accounted for it?
3. Was it caused by test data, background processing, session contention, database activity, or application code?
4. Did later OpenEMR versions retain or resolve the behavior?

## Test design

Four isolated OpenEMR environments were evaluated with separate containers, ports, databases, site-data volumes, and log volumes:

| Environment | Test role |
|---|---|
| OpenEMR 8.2.0 clean | Historical control |
| OpenEMR 8.3.0 clean | Historical control and server-side probe target |
| OpenEMR 8.4.0 clean | First verified fast release |
| OpenEMR 8.4.1 clean | Current comparison release |

The matched Playwright login test used Chromium, one worker, five sequential repetitions, the same local host, and network/performance instrumentation. It measured authenticated-shell loading and the response time of `library/ajax/i18n_generator.php`.

Temporary server-side probes were installed only in the clean 8.3.0 validation container. Original files were backed up before each experiment and restored afterward. Restoration was verified using SHA-256 hashes.

## Repeated version results

| OpenEMR version | Measurements | Median i18n response |
|---|---:|---:|
| 8.2.0 clean | 5 | 17.065 s |
| 8.3.0 clean | 5 | 16.002 s |
| 8.4.0 clean | 5 | 0.411 s |
| 8.4.1 clean | 5 | 0.411 s |

The approximately 39-fold difference between the 8.3.0 and 8.4.0 medians established a version boundary and showed that the delay was reproducible rather than an isolated browser failure.

## Localization results

Progressively narrower server-side probes localized the 8.3.0 delay:

| Scope | Measured time |
|---|---:|
| Instrumented server request | 17.638 s |
| `MainMenuRole::getMenu()` | 15.511 s |
| Internal `getMenu()` probe | 15.048 s |
| `menuApplyRestrictions()` | 14.612 s |

Other observed operations—including menu-file decoding, menu-update processing, event dispatch, and Twig construction—were comparatively small.

The measurements established that most of the delay occurred while OpenEMR recursively applied access restrictions to the authenticated navigation menu.

## Source comparison and root-cause evidence

`MainMenuRole.php` and `MenuRole.php` were identical between the tested 8.3.0 and 8.4.0 images. `AclMain.php`, however, changed.

In 8.3.0, each ordinary `aclCheckCore()` call recursively evaluated whether the user had `admin/super` access. During an ACL-heavy menu traversal, that repeated the same superuser authorization question many times.

OpenEMR 8.4.0 introduced a per-request cache for that specific probe. Once the superuser result is calculated for a user, subsequent checks reuse the Boolean result instead of repeating the underlying ACL lookup. The upstream source comment describes this as removing a large multiplier from ACL-heavy rendering.

This change is consistent with:

- The 14.612 seconds localized to menu restriction processing in 8.3.0
- The identical menu implementation across the compared releases
- The change in `AclMain.php` at the version boundary
- The reduction of median i18n response time from 16.002 seconds to 0.411 seconds

The i18n endpoint was therefore primarily a visible symptom. The authenticated `main.php` request performed lengthy ACL and menu processing while holding the PHP session, and the i18n request waited for access to that session.

## Conclusions

1. The observed delay in the clean 8.2.0 and 8.3.0 environments was real and repeatable.
2. It was not explained by populated clinical data, Playwright timing, the i18n SQL query, background-service execution, or Twig construction.
3. Most measured server time was spent applying ACL restrictions during navigation-menu construction.
4. OpenEMR 8.4.0 and 8.4.1 did not reproduce the delay under the matched test.
5. The request-level superuser ACL memoization introduced in 8.4.0 is the leading causal explanation and matches the measured performance boundary.
6. This case study should be treated as regression validation and root-cause analysis of behavior already corrected upstream—not as a claim of discovering an unresolved OpenEMR defect.

## Engineering practices demonstrated

- Reproducible browser performance testing with Playwright
- Network request instrumentation and median comparison
- Isolated multi-version Docker Compose environments
- Control of persistent databases and application volumes
- Progressive server-side timing instrumentation
- PHP request, session, menu, and ACL-path analysis
- Source and container-image comparison using SHA-256 hashes
- Hypothesis testing across application, database, session, and background-service layers
- Backup, rollback, and post-experiment restoration verification
- Evidence-based reporting with explicit limitations

## Limitations

- Testing was performed in a local Docker Desktop laboratory rather than a production deployment.
- Each matched version series contained five sequential measurements.
- The evidence strongly links the improvement to the ACL memoization change, but an isolated backport experiment would provide the most direct causal confirmation.
- Results should not be generalized to every OpenEMR deployment, dataset, host, or configuration.

## Portfolio summary

Built a reproducible, four-version OpenEMR performance test lab and used Playwright, network telemetry, Docker isolation, PHP phase probes, and source comparison to localize a 16-second authenticated-shell delay in OpenEMR 8.2/8.3 to repeated ACL evaluation during menu construction. Verified that OpenEMR 8.4.x reduced the matched median request time to 0.411 seconds and connected the improvement to upstream request-level superuser ACL memoization. Preserved experimental integrity through clean controls, deterministic runs, backups, SHA-256 restoration checks, and documented limitations.

## Evidence handling

Raw logs and diagnostic artifacts may contain substantial implementation detail. Before publishing any evidence, review it for credentials, session identifiers, CSRF values, authorization headers, cookies, local usernames, and patient information. Only synthetic data and sanitized extracts should be committed to a public repository.
