Interoperability Runtime Readiness Preflight

Objective

Validate that the Healthcare IT Operations & Interoperability Lab has satisfied its external runtime prerequisites before authenticated FHIR, HL7, database, PACS-routing, or DICOM-retrieval tests begin.

The preflight distinguishes environment-readiness failures from interoperability defects and prevents one missing dependency from producing multiple misleading downstream failures.

Operator Command

Run from the repository root:

python -m scripts.preflight.readiness

A ready environment ends with:

RUNTIME READINESS: PASS

A missing or unhealthy prerequisite ends with:

RUNTIME READINESS: FAIL

The command returns:

exit code 0 when every required check passes

exit code 1 when any required check fails

The exit code allows the preflight to be used as a local quality gate or as a prerequisite for automated regression execution.

Readiness Checks

The preflight validates:

Component

Contract

OpenEMR environment

Root .env exists and required variables are nonblank

OpenEMR

Container is running and healthy

MariaDB

Container is running and healthy

Mirth Connect

Container is running

Mirth database

Container is running and healthy

Interoperability database

Container is running and healthy

Orthanc

Container is running

Administrator FHIR token

Token exists and has sufficient remaining lifetime

Restricted-provider FHIR token

Token exists and has sufficient remaining lifetime

DICOM Storage SCP

TCP port 11112 accepts connections

Orthanc interoplab destination

DICOM C-ECHO succeeds

Role-Aware FHIR Tokens

The default administrator token is expected at:

%TEMP%\openemr-fhir-token.json

The restricted-provider token is expected at:

%TEMP%\openemr-fhir-restricted-token.json

Each token is evaluated independently using the shared lifecycle contract.

The preflight reports only lifecycle state and remaining lifetime. It does not display bearer-token values, client secrets, authorization codes, or environment-variable values.

DICOM Destination Behavior

Orthanc contains two configured destinations:

interoplab — required operational destination

unavailable — intentional negative-control destination

The preflight requires interoplab to pass C-ECHO.

The intentionally unavailable destination does not make readiness fail. Its purpose is to support controlled failure-state and degraded-health testing.

Typical Recovery Sequence

After a workstation reboot:

Start Docker Desktop.

Confirm OpenEMR, Mirth, Orthanc, and database containers are running.

Start the host-side DICOM Storage SCP:

python .\scripts\dicom\storage_scp.py

Acquire a fresh administrator FHIR token:

.\scripts\get-openemr-fhir-token.ps1

Log out of OpenEMR and acquire the restricted-provider token:

.\scripts\get-openemr-fhir-token.ps1 `
    -OutputTokenPath (
        Join-Path `
            $env:TEMP `
            "openemr-fhir-restricted-token.json"
    )

Run the readiness gate:

python -m scripts.preflight.readiness

Example Passing Report

OPENEMR_ENV                   READY
FHIR_ADMIN_TOKEN              READY
FHIR_RESTRICTED_TOKEN         READY
INTEROPLAB_SCP                READY
ORTHANC_INTEROPLAB            READY

RUNTIME READINESS: PASS

Validation

Focused unit tests cover:

required environment variables

missing environment configuration

healthy and unhealthy container states

explicit role-token selection

expired-token rejection

required PACS-destination behavior

intentional negative-control handling

protection against environment-secret disclosure

success exit code

failure exit code

Run:

python -m pytest -q tests/preflight/test_runtime_readiness.py