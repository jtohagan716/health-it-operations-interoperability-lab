# LOINC and UCUM Terminology Validation Deep Dive

## Objective

Extend the interoperability lab beyond structural HL7-to-FHIR
mapping and add terminology-aware semantic validation for laboratory
results.

The target workflow is:

```text
HL7 v2 ORU^R01
→ parsed laboratory context
→ terminology validation
→ FHIR R4 Observation
→ source-to-target reconciliation
```

The key engineering goal is to detect cases where a message is
syntactically valid and structurally mappable but the coded clinical
meaning is inconsistent.

## Baseline Workflow

The laboratory fixture contains:

```text
OBR|1|ORD000001|LABRPT000001|2345-7^Glucose^LN|||20260820150000-0400||||||||||||||||||F
OBX|1|NM|2345-7^Glucose^LN||105|mg/dL|70-99|H|||F
```

The ORU analyzer extracts:

- LOINC code: `2345-7`
- display: `Glucose`
- HL7 v2 coding system: `LN`
- value: `105`
- units: `mg/dL`
- reference range: `70-99`
- abnormal flag: `H`
- result status: `F`

The existing FHIR mapper preserved those source values into a FHIR
Observation.

## Gap Identified

The original mapper verified that:

- the coding system was `LN`
- the observation was numeric
- the result status was supported
- the abnormal flag was supported

Existing tests also verified that the source LOINC code, display, value,
units, and reference range were preserved into FHIR.

That did not prove that the code and display represented the same
clinical concept.

For example, this is syntactically plausible HL7:

```text
2345-7^Potassium^LN
```

A structural mapper could preserve that data faithfully even though the
code and claimed clinical meaning are inconsistent.

This is the same general failure class encountered during the US Core
Patient terminology investigation: structurally valid coded data can
still carry incorrect clinical semantics.

## Terminology Contract

A reusable terminology module was added:

```text
scripts/terminology/lab_terminology.py
```

The current supported laboratory concept is:

- LOINC code: `2345-7`
- expected display: `Glucose`
- allowed UCUM unit: `mg/dL`

The module validates:

1. the HL7 v2 coding system represents LOINC,
2. the LOINC code is supported by the lab contract,
3. the display matches the expected clinical concept,
4. the unit is allowed for that supported concept.

This is intentionally a deterministic project contract rather than a
replacement for a full terminology server.

## Mapper Integration

Terminology validation is now enforced inside:

```text
scripts/fhir/map_oru_to_observation.py
```

The mapper performs terminology validation before producing the FHIR
Observation.

This means terminology inconsistency is rejected at the interoperability
boundary rather than being propagated into downstream FHIR output.

## Negative Semantic Test

A regression test deliberately modifies the valid source message from:

```text
2345-7^Glucose^LN
```

to:

```text
2345-7^Potassium^LN
```

The message remains parseable and continues to identify the coding
system as LOINC.

The mapper rejects it with a terminology semantic mismatch rather than
creating a FHIR Observation.

Additional terminology tests verify rejection of:

- an incorrect LOINC display,
- an incorrect coding system,
- an incompatible UCUM unit.

## Validation Result

The focused terminology and ORU-to-FHIR regression suite completed with:

```text
9 passed
```

Evidence:

```text
docs/validation/evidence/terminology/loinc-ucum-semantic-contract.txt
```

## HL7-to-FHIR Reconciliation

The ORU-to-FHIR regression suite now performs explicit
source-to-target reconciliation after transformation.

The test compares the parsed HL7 source values against the generated
FHIR Observation and verifies preservation of:

- LOINC code,
- LOINC display,
- LOINC system,
- numeric observation value,
- UCUM unit,
- UCUM system,
- reference range,
- patient identifier,
- result identifier derived from the filler order number and OBX set ID.

This provides a stronger guarantee than checking a hard-coded expected
FHIR payload alone.

The reconciliation contract proves that clinically important source
semantics survive the transformation boundary unchanged.

The resulting workflow is:

```text
HL7 source
→ parse
→ terminology validation
→ FHIR transformation
→ source-to-target reconciliation
→ regression evidence
```

This pattern is directly applicable to production interoperability
work where successful message processing is not sufficient evidence
that the downstream representation preserved the intended clinical
meaning and identity relationships.

## Engineering Lesson

Three different properties must not be treated as equivalent:

**Syntactic validity**

The HL7 message can be parsed and its expected fields are populated.

**Structural interoperability**

The source fields can be mapped into the expected FHIR resource
structure.

**Semantic terminology integrity**

The coded representation still carries the intended clinical meaning.

A reliable healthcare integration pipeline must preserve all three.

A transformation that faithfully transports incorrect coded meaning is
still an interoperability defect.

Source-to-target reconciliation adds another important control: even
when the source terminology is correct, the transformation itself must
not alter or lose clinically significant meaning, values, units, or
identity relationships.

## Reusable Pattern

The terminology-validation and reconciliation pattern established here
is:

```text
source clinical meaning
→ source terminology representation
→ terminology validation
→ transformation
→ target terminology representation
→ source-to-target reconciliation
→ regression evidence
```

The same pattern can be extended to additional terminology systems
already represented in the interoperability lab, including:

- SNOMED CT
- LOINC
- UCUM
- RxNorm
- ICD-10

## Portfolio Significance

This increment demonstrates terminology-aware interoperability testing
rather than field-level mapping alone.

It provides evidence of:

- HL7 v2 ORU analysis,
- FHIR R4 Observation mapping,
- LOINC handling,
- UCUM handling,
- semantic contract testing,
- negative-path validation,
- source-to-target reconciliation,
- patient and result identity preservation,
- deterministic failure behavior,
- healthcare data integrity testing,
- regression automation.

The result is a reusable semantic validation and reconciliation layer
that can be expanded as additional clinical concepts and terminology
systems are introduced into the lab.