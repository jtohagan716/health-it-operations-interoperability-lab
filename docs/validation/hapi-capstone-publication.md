# HL7 to HAPI FHIR Capstone Publication

## Status

Implemented on `feature/hapi-capstone-fhir-publication` and merged into `main` through PR #73.

The implementation publishes a synthetic healthcare workflow from HL7 v2 source messages into a local HAPI FHIR R4 server and verifies the persisted resource relationships.

## Purpose

This validation demonstrates an end-to-end interoperability workflow across:

- HL7 v2 ADT patient identity data
- HL7 v2 ORU laboratory-result data
- FHIR Patient resources
- FHIR Observation resources
- FHIR DiagnosticReport resources
- HAPI FHIR persistence and search
- Sequential replay-safe resource reuse
- Automated regression validation

The goal is to prove that patient identity, laboratory result data, order identifiers, and FHIR resource relationships survive transformation and publication.

## Workflow

```mermaid
flowchart TD
    A["HL7 ADT^A04"] --> B["FHIR Patient"]
    C["HL7 ORU^R01"] --> D["FHIR Observation"]
    D --> E["FHIR DiagnosticReport"]
    B --> F["HAPI FHIR"]
    E --> F
    F --> G["Read, search, reconcile"]

    Source Fixtures
fixtures/hl7/adt/adt-a04-lab000001.hl7
fixtures/hl7/oru/oru-r01-lab000001.hl7

The ADT fixture provides:
- Patient identifier: LAB000001
- Assigning authority: INTEROPLAB
- Identifier type: MR
- Patient name: Avery Testpatient
- Date of birth: 19800115
- Administrative sex: M
- Visit number: VISIT000004
The ORU fixture provides:
- Message control ID: LAB-ORU-000001
- Placer order: ORD000001
- Filler order: LABRPT000001
- Observation code: 2345-7
- Observation: Glucose
- Result: 105 mg/dL
- Abnormal flag: H
- Result status: F
Transformation
The implementation reuses the repository's existing parsing and mapping components:
analyze_adt()map_adt_to_fhir_patient()analyze_oru()map_oru_to_fhir_observation()map_oru_to_fhir_diagnostic_report()


The ADT patient identifier is mapped to:
https://example.org/fhir/sid/interoplab-mrn

The resulting FHIR graph preserves:
Patient
 ├── Observation.subject
 └── DiagnosticReport.subject

DiagnosticReport.result
 └── Observation

HAPI FHIR Publication
The publisher is implemented in:
scripts/fhir/publish_capstone_to_hapi.py

It:
1. Parses the ADT fixture.
2. Parses the ORU fixture.
3. Maps the ADT message to a FHIR Patient.
4. Locates or creates the Patient in HAPI.
5. Maps the ORU message to a FHIR Observation.
6. Attaches the persisted Patient reference.
7. Locates or creates the Observation.
8. Maps the ORU message to a DiagnosticReport.
9. Attaches the Patient and Observation references.
10. Locates or creates the DiagnosticReport.
11. Reads the persisted resources back.
12. Searches for the Observation by patient and code.
13. Reconciles the persisted data and relationships.
Run the publisher from the repository root:
python -m scripts.fhir.publish_capstone_to_hapi

Validation Evidence
A successful local publication produced:
Patient/1121
Observation/1122
DiagnosticReport/1123

The publication checks verified:
- Patient identity preservation
- Observation subject-to-Patient linkage
- Observation code preservation
- Observation value preservation
- Observation unit preservation
- DiagnosticReport subject-to-Patient linkage
- DiagnosticReport-to-Observation linkage
- Observation search retrieval
All eight checks passed.
The related automated validation set completed with:
19 passed

The regression test is located at:
tests/interoperability/test_hapi_capstone_publication.py

Replay Behavior
A second execution reused the existing resources:
{
  "patient": "reused",
  "observation": "reused",
  "diagnostic_report": "reused"
}

The resource identifiers remained unchanged and all reconciliation checks passed again.
This demonstrates sequential replay safety for the tested workflow. The current implementation uses identifier lookup before creation; it does not yet claim atomic concurrency-safe idempotency. Conditional-create semantics can be added in a later phase.
Engineering Significance
This capstone demonstrates practical experience with:
- HL7 v2 message parsing
- Healthcare identity preservation
- FHIR R4 resource modeling
- REST-based FHIR publication
- HAPI FHIR server operation
- Resource relationship validation
- Identifier-based lookup
- FHIR search verification
- Replay behavior
- Python automation
- Pytest regression testing
- Dockerized local infrastructure
It connects the project's earlier OpenEMR/Mirth/HL7 laboratory workflow to a modern FHIR repository boundary:
OpenEMR
  → HL7 OML/ORU workflow
  → Mirth Connect
  → Synthetic LIS and interoperability state
  → OpenEMR result persistence
  → HL7/FHIR transformation
  → HAPI FHIR repository
  → Resource reconciliation

Environment Boundaries
This validation uses synthetic clinical data and local Docker infrastructure only.
It does not use:
- Production patient information
- Production healthcare systems
- Production credentials
- Production databases
- A production HAPI deployment
This work demonstrates interoperability engineering and validation technique. It is not a production compliance assessment.
Future Extensions
The next natural phases are:
1. Add conditional-create behavior for stronger concurrent replay protection.
2. Capture publication and read-back timings.
3. Measure response time, throughput, and error behavior.
4. Add structured runtime logging.
5. Add CI execution for the mapping and publication contracts.
6. Add observability around HAPI, PostgreSQL, and resource publication.
7. Produce a performance and reliability report for the complete workflow.

After saving, stage the corrected file again:

```powershell
git add .\docs\validation\hapi-capstone-publication.md
git diff --cached --check
git diff --cached --stat