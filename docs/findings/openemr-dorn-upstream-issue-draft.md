# Proposed OpenEMR Issue

## Title

[DORN] Multi-test lab orders associate diagnoses with every OBR

## Description

I reproduced a diagnosis-association problem in the DORN HL7 laboratory-order generator using OpenEMR 8.2.0.

When a single order contains multiple tests with different per-test diagnoses, the generated OML^O21 message places the diagnoses from all ordered tests beneath each OBR rather than preserving the diagnosis associated with the individual test.

The reproduction used synthetic local data and the actual OpenEMR DORN HL7 generator. No external laboratory transmission was performed.

## Reproduction

Create one DORN laboratory order containing two tests with different diagnoses:

    DORNTESTA -> ICD10:E11.9
    DORNTESTB -> ICD10:I10

Leave the order-level diagnosis empty so the per-test diagnosis source is unambiguous.

Generate the DORN OML^O21 message.

## Expected Result

The diagnosis associated with each ordered test remains associated with that test's OBR:

    OBR ... DORNTESTA
    DG1 ... E11.9

    OBR ... DORNTESTB
    DG1 ... I10

## Actual Result

The generated message contains both diagnoses beneath both OBRs:

    OBR ... DORNTESTA
    DG1 ... E11.9
    DG1 ... I10

    OBR ... DORNTESTB
    DG1 ... E11.9
    DG1 ... I10

The generator returns success while producing the message.

## Source Observation

Relevant source:

    interface/modules/custom_modules/oe-module-dorn/src/DornGenHl7Order.php

The generator loops through the procedure-code rows to produce each OBR.

Inside that loop, the per-test diagnosis logic iterates over the complete procedure-diagnosis row collection rather than restricting diagnosis processing to the current procedure row.

The same nested iteration pattern is present in the current OpenEMR master source as inspected in August 2026.

I have runtime-confirmed the behavior against OpenEMR 8.2.0. I have not yet runtime-tested current master, so I am not claiming runtime confirmation against master.

## Environment

- OpenEMR 8.2.0
- oe-module-dorn
- OML^O21
- HL7 2.5.1
- Synthetic local test data
- External DORN transmission disabled

## Additional Validation

I created deterministic regression coverage around the reproduced behavior, including:

- captured runtime-generated HL7
- a positive-control message preserving correct OBR-to-DG1 association
- an OBR/DG1 semantic analyzer
- pytest contract tests comparing expected and observed diagnosis associations

The controlled source relationship was:

    DORNTESTA -> E11.9
    DORNTESTB -> I10

The OpenEMR-generated relationship was:

    DORNTESTA -> E11.9, I10
    DORNTESTB -> E11.9, I10

## Impact

The generated message remains structurally plausible, but the diagnosis-to-ordered-test relationship represented by the source order is not preserved.

The downstream effect will depend on the receiving laboratory and workflow. I am not assuming a specific billing, clinical, or patient-safety consequence without evidence from a receiving system.
