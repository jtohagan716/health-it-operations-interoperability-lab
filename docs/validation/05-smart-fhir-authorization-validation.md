# SMART on FHIR Authorization Validation

## Objective

Validate the authentication and authorization behavior of the OpenEMR FHIR endpoint, including SMART discovery, bearer-token handling, token lifecycle prerequisites, granted scopes, runtime resource access, and EHR policy enforcement.

The goal is to distinguish authentication failures, authorization failures, and successful FHIR resource access in a repeatable test environment.

## Environment

- OpenEMR
- FHIR R4 API
- SMART on FHIR / OAuth 2.0 authorization
- Python
- pytest
- requests
- PowerShell
- Docker
- Synthetic healthcare data only

FHIR base:

```text
https://localhost:9300/apis/default/fhir