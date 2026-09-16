# OpenEMR Playwright Authentication Smoke Validation

## Validation Status

**PASS**

Playwright browser automation was added to the healthcare interoperability
laboratory and validated against the local containerized OpenEMR environment.

This initial increment establishes deterministic browser-level validation of
the OpenEMR authentication boundary without extending the suite into broader
clinical workflow automation.

## Scope

The Playwright smoke suite validates two behaviors:

1. An unauthenticated browser session is redirected to the OpenEMR login page.
2. Valid local-lab administrator credentials establish an authenticated
   OpenEMR browser session.

The tests are explicitly restricted to localhost targets.

## Test Environment

- OpenEMR running in the local Docker laboratory
- Playwright Test 1.63.0
- Chromium
- Node.js 24.14.0
- Single Playwright worker
- Local credentials loaded from the ignored .env file
- Generated Playwright evidence written beneath the ignored artifacts directory

The Playwright configuration refuses to execute against a base URL that does
not begin with http://localhost: or https://localhost:.

This provides a guard against accidentally directing the UI smoke suite at a
non-local OpenEMR environment.

## Automated Validation

### Unauthenticated Authentication Boundary

The first test opens the OpenEMR root URL without an authenticated session.

The browser is required to reach:

    /interface/login/login.php?site=default

The test also verifies that the expected Username, Password, and Login controls
are visible.

### Authenticated Administrator Session

The second test obtains the local administrator username and password from
environment variables rather than storing credentials in test source.

The test:

1. Opens the OpenEMR login page.
2. Populates the Username and Password controls.
3. Establishes a response waiter for the expected authenticated navigation.
4. Submits the Login form.
5. Requires HTTP 200 from the authenticated main-tabs page.
6. Verifies the authenticated main-tabs URL.
7. Verifies the OpenEMR page title.
8. Verifies that the login Username control is no longer visible.

## Authentication Synchronization Investigation

Initial authenticated executions exposed a browser synchronization problem.

Playwright reported that the Login button was visible, enabled, stable, and
successfully clicked, but the click operation timed out while waiting for
OpenEMR's navigation sequence to complete.

Request and response evidence demonstrated that authentication itself had
succeeded:

    POST /interface/main/main_screen.php?auth=login&site=default
    HTTP 302

    GET /interface/main/tabs/main.php?token_main=...
    HTTP 200

The browser also reached the authenticated OpenEMR main-tabs page.

The observed failure was therefore isolated to browser automation
synchronization rather than failed OpenEMR authentication.

The test was corrected by establishing an explicit response waiter for the
authenticated main-tabs navigation before submitting the Login form.

The Login click uses noWaitAfter so that Playwright does not independently wait
for OpenEMR's complete post-login navigation chain. The test instead validates
the specific authenticated HTTP response and resulting browser state.

## Repeatability Validation

After the synchronization correction, the complete two-test Playwright suite
was executed successfully across five consecutive runs.

Every run validated both behaviors:

- unauthenticated redirect to the OpenEMR login page
- authenticated local-lab administrator login

No failures occurred during the five-run repeatability check.

A subsequent execution through the repository npm command also passed:

    npm run test:ui
    2 passed

## Runtime Readiness

Before final repository regression validation, the existing interoperability
runtime readiness gate was executed.

Result:

    RUNTIME READINESS: PASS

The readiness gate confirmed:

- required OpenEMR containers ready
- required Mirth containers ready
- required database containers ready
- Orthanc ready
- fresh administrator FHIR token
- fresh restricted FHIR token
- host-side DICOM Storage SCP accepting connections
- successful Orthanc C-ECHO to INTEROPLAB

## Full Repository Regression

With runtime prerequisites confirmed ready, the complete Python regression
suite was executed.

Command:

    python -m pytest -q

Result:

    545 passed
    1 skipped
    1 xfailed
    0 failed
    34 warnings

The warnings were local-laboratory HTTPS certificate verification warnings and
did not represent test failures.

An earlier regression execution produced 17 failures associated with an
expired FHIR authentication prerequisite.

Fresh FHIR credentials were acquired through the laboratory's existing OAuth
workflow. Runtime readiness subsequently returned PASS, and the complete
regression suite passed with zero failures.

This evidence separates the expired runtime prerequisite from the Playwright
implementation.

## Repository Hygiene

The following sensitive, dependency, and generated paths are excluded from
version control:

    .env
    node_modules/
    artifacts/

This prevents credentials, installed Node dependencies, Playwright traces,
screenshots, videos, and generated HTML reports from entering source control.

## Engineering Outcome

This increment adds a browser-level functional testing layer to the existing
healthcare interoperability and systems-reliability laboratory.

The validation goes beyond confirming that a page renders. It exercises the
OpenEMR authentication boundary from an unauthenticated browser session through
successful authenticated application navigation.

The increment also preserves a representative automation troubleshooting case.
A successful application transaction initially appeared to be a failed test
because the browser synchronization strategy did not match OpenEMR's navigation
behavior.

Request and response evidence was used to distinguish application behavior from
automation behavior, and the synchronization strategy was corrected.

The resulting smoke suite provides a deterministic starting point for future
OpenEMR functional workflow automation while preserving the laboratory's
existing emphasis on evidence, repeatability, runtime readiness, and regression
validation.
