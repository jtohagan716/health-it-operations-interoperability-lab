# HAPI FHIR Foundation Validation

Date: 2026-10-02

## Purpose

This validation adds an isolated HAPI FHIR R4 server backed by PostgreSQL to the healthcare interoperability lab.

The goal is to demonstrate hands-on experience operating a database-backed FHIR server, validating REST behavior, testing resource persistence, and handling application startup readiness.

## Architecture

| Component | Responsibility |
| --- | --- |
| OpenEMR | Clinical source-system workflows in the broader lab |
| Mirth Connect | HL7 v2 routing and transformation in the broader lab |
| HAPI FHIR | FHIR R4 REST server and resource repository |
| PostgreSQL | Durable HAPI persistence layer |
| pytest | Repeatable FHIR runtime contract validation |
| Docker Compose | Isolated local deployment and service configuration |

The HAPI stack is intentionally isolated from the existing OpenEMR and Mirth environments.

## Runtime Configuration

- HAPI FHIR server: 8.12.0
- FHIR version: R4
- Database: PostgreSQL 16
- HAPI endpoint: `http://localhost:8090/fhir`
- Database service: PostgreSQL container on the internal Compose network
- Deployment: Docker Compose
- Test framework: Python pytest
- Test file: `tests/interoperability/test_hapi_fhir_runtime_contract.py`

The HAPI application uses JPA/Hibernate persistence with PostgreSQL.

## Automated Validation

The runtime contract verifies:

1. The HAPI CapabilityStatement is available.
2. The server reports FHIR R4 support.
3. JSON is listed as a supported response format.
4. A synthetic Patient resource can be created.
5. The created Patient can be read by logical ID.
6. The Patient can be located using an identifier search.
7. The returned resource matches the expected identifier and demographic values.
8. HAPI startup readiness is handled explicitly rather than inferred only from container status.
9. A read for a nonexistent Patient returns HTTP 404 with a FHIR `OperationOutcome`.
10. A synthetic Observation can reference a Patient, be read back, and be searched by Patient reference.

Each runtime test creates a synthetic Patient with a unique identifier. No production or personally identifiable health information is used.

## Startup Readiness

HAPI may require several minutes to complete initialization after a cold application start.

The pytest module includes a bounded readiness fixture that:

- Polls the `/metadata` endpoint.
- Handles connection failures during startup.
- Waits for the endpoint to return HTTP 200.
- Fails with the last observed error if readiness is not achieved within 240 seconds.

This prevents a running container from being incorrectly treated as a ready FHIR service.

## Validation Results

After restarting only the HAPI application container, the runtime contract completed successfully:

```text
2 passed in 22.86s

The result demonstrates that the test suite can wait through application startup and then validate the FHIR endpoint.
A separate manual persistence check also confirmed that Patient/1000 remained available after restarting HAPI. The resource was read successfully with:
- Resource type: Patient
- Logical ID: 1000
- Family name: Interoperability
- Given name: Synthetic
- Version: 1
Reproduction
Start the isolated stack:
docker compose `
  --env-file .\infrastructure\hapi\.env.example `
  -f .\infrastructure\hapi\compose.yaml `
  up -d --wait

Run the HAPI runtime contract:
python -m pytest `
  .\tests\interoperability\test_hapi_fhir_runtime_contract.py `
  -q

To validate application restart readiness:
docker compose `
  --env-file .\infrastructure\hapi\.env.example `
  -f .\infrastructure\hapi\compose.yaml `
  restart fhir

Then immediately rerun the pytest command.
## Linked Patient and Observation Validation

The runtime contract creates a synthetic Patient and a linked Observation.

The Observation uses:

- Status: `final`
- Code: LOINC `2345-7`
- Display: `Glucose`
- Value: `96 mg/dL`
- Subject reference: `Patient/{id}`

The test verifies that:

- The Patient is created successfully.
- The Observation is created successfully.
- The Patient reference is preserved.
- The Observation can be read by logical ID.
- The Observation can be searched using the Patient reference.
- The glucose value and coding remain intact after persistence.

Scope and Limitations
This validation is a local synthetic interoperability foundation. It does not claim:
- Commercial production HAPI administration experience
- Java or Spring application development experience
- Production cloud deployment
- Kubernetes or OpenShift operation
- SMART on FHIR authentication
- Implementation Guide conformance validation
- Load or stress testing
- Production security hardening
Those areas can be added as separate, bounded validation activities.
Engineering Significance
This work extends the lab from testing FHIR clients and clinical-system endpoints to operating and validating a persistent FHIR server.
The resulting evidence covers:
- FHIR R4 capability discovery
- REST resource lifecycle behavior
- Identifier-based search
- PostgreSQL-backed persistence
- Docker service isolation
- Runtime readiness and failure handling
- Repeatable automated validation

The negative-path contract also passed. A request for a nonexistent Patient returned:

- HTTP status: `404`
- Resource type: `OperationOutcome`
- Issue severity: `error`
- HAPI diagnostic code: `HAPI-2001`