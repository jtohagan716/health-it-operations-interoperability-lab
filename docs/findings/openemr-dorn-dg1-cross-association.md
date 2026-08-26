# OpenEMR DORN Multi-Test DG1 Cross-Association Finding

## Summary

A controlled OpenEMR 8.2.0 DORN laboratory-order experiment reproduced a diagnosis-association problem in a multi-test OML^O21 message.

Two ordered tests were assigned different per-test diagnoses. The generated HL7 contained both diagnoses beneath both OBR groups rather than preserving the diagnosis associated with each individual ordered test.

The reproduction used the actual OpenEMR DORN HL7 generator with synthetic local test data. No message was transmitted to an external laboratory service.

## Environment

- OpenEMR: 8.2.0
- Module: oe-module-dorn
- Message type: OML^O21
- HL7 version emitted: 2.5.1
- Test data: synthetic/local
- External DORN transmission: disabled

## Controlled Input

A single laboratory order contained two ordered tests with intentionally distinct diagnoses:

- DORNTESTA -> ICD10:E11.9
- DORNTESTB -> ICD10:I10

The order-level diagnosis was left empty so that diagnosis provenance was unambiguous.

## Expected Association

DORNTESTA should contain only its assigned diagnosis:

    OBR ... DORNTESTA
    DG1 ... E11.9

DORNTESTB should contain only its assigned diagnosis:

    OBR ... DORNTESTB
    DG1 ... I10

## Observed OpenEMR Output

The runtime-generated message contained:

    OBR ... DORNTESTA
    DG1 ... E11.9
    DG1 ... I10

    OBR ... DORNTESTB
    DG1 ... E11.9
    DG1 ... I10

The generator returned success while producing this message.

This means the diagnosis-to-ordered-test relationship present in the source order was not preserved in the generated HL7.

## Source-Level Observation

Relevant source:

    interface/modules/custom_modules/oe-module-dorn/src/DornGenHl7Order.php

The generator iterates over procedure-code rows to create each OBR.

Within that OBR loop, the per-test diagnosis-generation logic subsequently iterates over the complete collection of procedure diagnosis rows.

In the reproduced multi-test scenario, this results in diagnoses belonging to other ordered tests being emitted beneath the current OBR.

The same nested iteration pattern is still present in the OpenEMR master source inspected in August 2026.

Current master has not yet been runtime-tested as part of this investigation.

## Regression Evidence

The interoperability lab contains a deterministic reproduction and semantic contract test.

Captured OpenEMR runtime output:

    fixtures/hl7/dorn/dorn-oml-o21-dg1-cross-association.hl7

Positive-control message:

    fixtures/hl7/dorn/dorn-oml-o21-dg1-association-expected.hl7

Semantic analyzer:

    scripts/hl7/analyze_dorn_order.py

Regression tests:

    tests/interoperability/test_dorn_lab_order_contract.py

The test suite verifies both sides of the contract:

- the captured OpenEMR output exposes cross-association
- the positive-control fixture preserves the intended per-OBR diagnosis relationship

## Reproduction Result

Controlled source data:

    DORNTESTA -> E11.9
    DORNTESTB -> I10

Observed generated associations:

    DORNTESTA -> E11.9, I10
    DORNTESTB -> E11.9, I10

Expected associations:

    DORNTESTA -> E11.9
    DORNTESTB -> I10

## Scope

Runtime reproduction has been completed against OpenEMR 8.2.0.

The current OpenEMR master source has been inspected and retains the same relevant nested diagnosis-iteration pattern.

The current master version has not yet been runtime-reproduced, so this finding does not claim runtime confirmation against master or a later release.

## Potential Impact

The generated HL7 remains structurally plausible while failing to preserve the diagnosis-to-ordered-test relationship represented by the source order.

The downstream effect will depend on the receiving laboratory implementation and workflow.

This investigation does not assume or claim a specific billing, clinical, or patient-safety consequence without evidence from a receiving system.
