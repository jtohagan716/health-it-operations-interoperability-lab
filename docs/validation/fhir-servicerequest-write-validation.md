# OpenEMR FHIR ServiceRequest Write Validation

## Purpose

Validate authenticated ServiceRequest creation, read-back persistence, and OAuth least-privilege enforcement against the isolated OpenEMR FHIR environment.

This was a self-directed interoperability reliability investigation, not a community-requested change.

## Environment

- Endpoint: `https://localhost:9340/apis/default/fhir`
- FHIR version: `4.0.1`
- OpenEMR: pinned image defined in `infrastructure/openemr/compose-fhir-write-validation.yaml`
- Transport: local HTTPS with self-signed certificate
- Data: synthetic patient and synthetic ServiceRequest

## Authorization model

Separate tokens were used:

- Write token: `user/ServiceRequest.cud`
- Read token: `user/ServiceRequest.rs`

OpenEMR did not grant the ServiceRequest read and write scopes together in the observed authorization flow, so the validation used separate least-privilege tokens.
- The automated test attempts cleanup, but OpenEMR does not expose a ServiceRequest DELETE route; synthetic test resources remain in the isolated validation site.

## Results

| Validation | Result |
| --- | --- |
| ServiceRequest create with CUD token | Passed |
| ServiceRequest read-back with RS token | Passed |
| ServiceRequest create with RS-only token | Rejected with HTTP 401 |
| Automated pytest runtime contract | 1 passed |
| ServiceRequest DELETE attempt | HTTP 404; DELETE is not exposed for this resource |
The created resource returned:

- `procedure_order_id`: `2`
- FHIR `uuid`: `a2db22ce-8e79-4988-9617-19592e2d207f`
- `resourceType`: `ServiceRequest`
- `status`: `active`
- `intent`: `order`
- `versionId`: `1`

## Observation

The submitted LOINC coding was returned on read-back as `code.text`:

```text
Glucose [Mass/volume] in Serum or Plasma