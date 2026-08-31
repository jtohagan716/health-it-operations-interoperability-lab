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
```

## Role-Aware Authorization Contracts

Runtime testing demonstrated that a granted SMART scope is only one input to the final access decision. OpenEMR also evaluates the authenticated EHR principal and its associated organization policy.

The same registered OAuth client produced different resource-access outcomes when authorized by different EHR users:

| Principal | Organization | Practitioner | DiagnosticReport |
| --- | ---: | ---: | ---: |
| Clinical administrator | HTTP 200 | HTTP 200 | HTTP 200 |
| Restricted provider | HTTP 403 | HTTP 403 | HTTP 403 |

This initially made the combined regression suite dependent on whichever account most recently completed browser authorization. A single temporary token could validate either the administrator workflow or the restricted-provider policy boundary, but not both deterministically.

The test harness now isolates the two identities:

```text
Default token path
  -> clinical administrator
  -> permitted clinical-resource contracts

Restricted token path
  -> provider01 / Physicians
  -> expected EHR-policy denial contracts
```

The PowerShell token-acquisition script accepts an optional output path:

```powershell
.\scripts\get-openemr-fhir-token.ps1 `
    -OutputTokenPath (
        Join-Path `
            $env:TEMP `
            "openemr-fhir-restricted-token.json"
    )
```

The Python authentication helper accepts the corresponding explicit token path and applies the same lifecycle validation to both identities.

This makes the authorization tests:

- role-aware
- deterministic
- independently reproducible
- resistant to browser-session reuse
- explicit about positive and negative access contracts

No bearer tokens, authorization codes, client secrets, or other credential values are committed to the repository or written to test evidence.
