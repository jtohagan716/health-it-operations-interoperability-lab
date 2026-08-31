# FHIR Medication Dispense Reconciliation Deep Dive

## Objective

Validate that medication semantics are preserved when OpenEMR prescription data is exposed through the FHIR R4 MedicationRequest resource.

The focus of this investigation is the distinction between:

- medication dose quantity
- dispense quantity

These values represent different clinical concepts and must not be conflated during transformation.

## Source Prescription Evidence

The controlled prescription record contains:

- drug: lisinopril 10 MG Oral Tablet
- dosage: 1
- quantity: 30
- size: 10
- unit: 1
- form: 2
- route: bymouth
- refills: 0
- active: 1

The prescription source therefore distinguishes:

- medication size: 10
- dispense quantity: 30

## Unit Resolution

OpenEMR PrescriptionService resolves the prescription unit through the `drug_units` list:

```text
combined_prescriptions.unit
→ list_options
→ list_id = 'drug_units'
→ unit_title

This produces a shared unit_title value for downstream FHIR mapping.

FHIR Mapping Trace

OpenEMR FhirMedicationRequestService.php constructs the dose quantity from:

prescription_drug_size
+
unit_title

For the controlled prescription this produces:

10 mg

The same service constructs dispenseRequest.quantity from:

quantity
+
unit_title

For the same prescription this produces:

30 mg

The same medication unit is therefore reused for two semantically different quantities.

Live FHIR Evidence

The live MedicationRequest resource contains:

"doseQuantity": {
  "value": 10,
  "unit": "mg",
  "system": "http://unitsofmeasure.org",
  "code": "mg"
}

and:

"dispenseRequest": {
  "numberOfRepeatsAllowed": 0,
  "quantity": {
    "value": 30,
    "unit": "mg",
    "system": "http://unitsofmeasure.org",
    "code": "mg"
  }
}

The dose quantity is clinically plausible as 10 mg.

The dispense quantity is not equivalent to a 30 mg medication dose. The source prescription quantity represents a separate dispense amount.

Deterministic Runtime Contract

The medication runtime contract verifies:

authenticated MedicationRequest retrieval
expected medication identity
patient reference
active status
order intent
medication text
10 mg dose quantity
timing
route
dispense quantity value of 30
refills
repeated-read logical identity

A strict expected-failure test additionally verifies that the dispense quantity unit must not be reused from the dose quantity.

Current result:

3 passed, 1 xfailed

The XFAIL represents a known semantic mapping defect rather than an unstable test.

Root Cause

The evidence supports the following transformation path:

OpenEMR prescription
    |
    |-- prescription_drug_size = 10
    |-- quantity = 30
    |-- unit
    v
PrescriptionService
    |
    |-- unit → unit_title
    v
FhirMedicationRequestService
    |
    |-- doseQuantity = 10 + unit_title
    |
    `-- dispenseRequest.quantity = 30 + unit_title

The FHIR transformation reuses the medication dose unit for the dispense quantity.

This is a semantic transformation issue rather than a structural FHIR failure.

The FHIR transformation reuses the medication dose unit for the dispense quantity.

This is a semantic transformation issue rather than a structural FHIR failure.

What Has Not Yet Been Claimed

This investigation does not yet prescribe the exact correct FHIR representation for the dispense unit.

Further validation is required before asserting whether OpenEMR should:

represent a dosage-form count such as tablet
use another coded quantity representation
omit the unit
derive the dispense unit from another prescription field

The proven defect is narrower:

The medication dose unit is reused for the dispense quantity even though those quantities represent different clinical concepts.

Engineering Lesson

FHIR interoperability requires more than producing structurally valid resources.

A transformation can:

return HTTP 200
satisfy the expected FHIR resource shape
preserve numeric values
pass basic runtime contracts

and still corrupt clinical meaning.

Reliable interoperability testing therefore requires reconciliation of source semantics against target semantics.

The reusable validation pattern is:

source clinical data
→ source semantic interpretation
→ transformation logic
→ target FHIR representation
→ source-to-target reconciliation
→ deterministic regression evidence
Evidence

Runtime FHIR resource:

docs/validation/evidence/fhir-foundation/
medication-request-dispense-unit-defect.json

Runtime contract evidence:

docs/validation/evidence/fhir-foundation/
medication-request-dispense-unit-contract.txt

Runtime regression:

tests/interoperability/
test_fhir_medication_request_runtime_contract.py