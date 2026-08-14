\# KB-FHIR-002 â€” SMART Scope Granted but EHR Policy Denies FHIR Resource Access



\## Summary



During authenticated SMART-on-FHIR testing in the Healthcare IT Operations \& Interoperability Lab, the OpenEMR FHIR client was granted user-context scopes for multiple resources.



Patient and Encounter operations succeeded with HTTP 200.



Practitioner and Organization operations returned HTTP 403 despite the corresponding SMART scopes being present in the access token.



This demonstrates an authorization boundary between OAuth/SMART scope grants and the resource-level authorization policy associated with the authenticated EHR user.



\## Environment



\- EHR: OpenEMR

\- FHIR: R4

\- OAuth flow: Authorization Code

\- OAuth client: Confidential

\- Client authentication: `client\_secret\_post`

\- Authenticated EHR user: `provider01`

\- User role/access-control group: Physicians

\- Synthetic data only



\## Granted SMART Scopes



The issued access token contained:



\- `user/Patient.rs`

\- `user/Encounter.rs`

\- `user/Practitioner.rs`

\- `user/Organization.rs`

\- `api:fhir`



\## Test Results



| Resource | Scope Granted | HTTP Result | Outcome |

|---|---:|---:|---|

| Patient | Yes | 200 | Permitted |

| Encounter | Yes | 200 | Permitted |

| Practitioner | Yes | 403 | Denied |

| Organization | Yes | 403 | Denied |



\## Policy Response



OpenEMR returned:



> Organization policy does not have permit access resource



\## Observed Authorization Boundary



```text

SMART / OAuth Authorization

&#x20;         |

&#x20;         v

Bearer Access Token

&#x20;         |

&#x20;         v

Granted user/Resource.rs Scope

&#x20;         |

&#x20;         v

Authenticated EHR User Context

&#x20;     provider01

&#x20;         |

&#x20;         v

EHR ACL / Policy Evaluation

&#x20;      /       \\

&#x20;     /         \\

&#x20;PERMIT         DENY

&#x20;  |              |

HTTP 200        HTTP 403
