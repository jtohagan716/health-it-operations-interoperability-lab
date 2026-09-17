# OpenEMR Playwright Patient Chart Validation

## Objective

Validate a deterministic OpenEMR patient-search and chart-selection workflow using Playwright, with assertions that prove the intended synthetic patient becomes the active Medical Record Dashboard.

This increment extends the OpenEMR authentication smoke coverage into a clinician-facing patient workflow while preserving deterministic test data and explicit synchronization with OpenEMR runtime behavior.

## Scope

The Playwright workflow validates:

1. Local OpenEMR administrator authentication.
2. Availability of the authenticated OpenEMR shell.
3. Navigation to Patient -> New/Search.
4. Completion of the OpenEMR patient-search UI.
5. Activation and population of first-name and last-name search criteria.
6. Execution of the OpenEMR patient finder.
7. Identification of the deterministic synthetic patient.
8. Verification of the expected synthetic MRN in finder results.
9. Selection of the patient.
10. Navigation of the patient workspace to the Medical Record Dashboard.
11. Verification of the selected patient dashboard identity.
12. Verification of the deterministic synthetic MRN inside the active patient chart.

## Deterministic Test Patient

- First name: Synthetic001
- Middle name: Test
- Last name: Patient001
- External ID / MRN: SYNTHMRN000001

Expected finder result: Patient001, Synthetic001

Expected dashboard identity: Medical Record Dashboard - Synthetic001 Test Patient001

## Authentication Synchronization

Initial patient-chart testing used a conventional Playwright login-button click followed by URL validation.

Runtime testing showed that OpenEMR authentication could complete the click action while Playwright continued waiting for scheduled navigation. This produced timeout behavior even though OpenEMR was processing the login.

The workflow was changed to synchronize explicitly with the successful authenticated navigation response at /interface/main/tabs/main.php.

The test registers the response wait before clicking Login, requires a navigation GET returning HTTP 200, uses noWaitAfter for the Login click, and independently verifies the authenticated OpenEMR URL and title.

## Patient Search Behavior

OpenEMR patient search requires application-specific interaction. The test waits for the complete search interface rather than assuming that the presence of individual demographic fields means the view is ready.

The #search control is used as the readiness indicator.

OpenEMR also requires demographic fields to be activated as search criteria. The test therefore clicks the first-name and last-name fields before filling them.

The deterministic search criteria are Synthetic001 and Patient001. The populated values are verified before the search is executed.

## Finder Validation

OpenEMR renders the patient finder in a dialog iframe using patient_select.php.

The test verifies that the finder returns Patient001, Synthetic001 and independently verifies SYNTHMRN000001 before selecting the result.

This proves that the intended deterministic patient was returned before chart-selection validation begins.

## Patient Dashboard Synchronization Investigation

An earlier implementation validated patient selection by scanning available frame body text for the first name, last name, and MRN.

Although that implementation passed, diagnostic investigation showed that the assertion was not sufficiently specific to prove that the Medical Record Dashboard had become active. Search or finder content could potentially expose the same identifiers.

The assertion was therefore treated as insufficient despite producing a green test.

Runtime frame sampling after patient selection showed the patient workspace initially remaining at /interface/new/new.php.

The same workspace frame later navigated to /interface/patient_file/summary/demographics.php?set_pid=2.

At that point the frame exposed Medical Record Dashboard - Synthetic001 Test Patient001. As dashboard initialization continued, the same active chart exposed External ID SYNTHMRN000001.

The investigation also showed that OpenEMR reuses the patient workspace iframe. The iframe element original DOM src attribute is therefore not a reliable indication of the document currently loaded in that frame.

## Final Synchronization Strategy

The final test registers a response wait before selecting the patient and requires a successful navigation response whose URL contains /interface/patient_file/summary/demographics.php.

The response must be a navigation GET returning HTTP 200.

After that response, the test identifies the patient dashboard using the Playwright frame current document URL rather than relying on the iframe element original src attribute.

The active dashboard must visibly expose Medical Record Dashboard - Synthetic001 Test Patient001.

The same active dashboard must also visibly expose SYNTHMRN000001.

These assertions prevent patient-search or finder content from satisfying the final active-chart validation.

## Reliability Findings

The investigation distinguished application state from test-runner synchronization behavior.

Observed behavior included:

- OpenEMR authentication navigation completing independently of the Login click generic navigation wait.
- Patient selection reusing an existing workspace iframe.
- The frame current document URL changing even when the iframe original DOM src was not a reliable selector.
- Patient dashboard initialization occurring asynchronously after selection.
- Patient identity information becoming available progressively as the dashboard loaded.

The resulting test synchronizes against observable application events and asserts against intended application state rather than relying on arbitrary fixed waits.

## Validation Results

### Strengthened patient-chart workflow

Command: npx playwright test patient-chart.spec.ts --project=chromium --reporter=line

Result: 1 passed (42.8s)

### Repeatability validation

Command: npx playwright test patient-chart.spec.ts --project=chromium --repeat-each=3 --reporter=line

Result: 3 passed (1.9m)

### Combined OpenEMR Playwright validation

The authentication smoke tests and deterministic patient-chart workflow were executed together with one Playwright worker.

Result: 3 passed (1.2m)

### Synthetic-data regression

Command: python -m pytest -q .\tests\test_data

Result: 135 passed in 3.24s

The existing synthetic-data regression suite remained green after the Playwright patient-chart hardening.

## Failure-Mode Improvement

The original final assertion effectively asked whether the expected patient identifiers appeared somewhere in available frame content.

The hardened test instead proves that OpenEMR successfully navigates the patient workspace to the patient-summary route and that the active Medical Record Dashboard visibly identifies the expected deterministic patient and MRN.

This reduces the risk of a false-positive result caused by stale search, finder, or other non-dashboard content.

## Validation Conclusion

The OpenEMR Playwright patient-chart smoke workflow now provides deterministic browser-level evidence that authentication succeeds, the patient-search workflow becomes usable, the expected synthetic patient is returned, the expected MRN is verified, patient selection produces a successful patient-summary navigation, and the active Medical Record Dashboard identifies the expected patient and MRN.

The workflow passed repeated execution, passed alongside the existing authentication smoke coverage, and did not regress the synthetic clinical-data test suite.

This establishes a stronger browser-level foundation for future end-to-end clinical workflow validation in which interoperability events can be verified through to clinician-visible OpenEMR state.
