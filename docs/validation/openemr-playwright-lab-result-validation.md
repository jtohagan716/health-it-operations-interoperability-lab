# OpenEMR Playwright Laboratory Result Validation

## Objective

Validate that deterministic laboratory data persisted in OpenEMR can be located
through the clinician-facing user interface and verified with browser automation.

This increment establishes the UI validation layer needed for a later
closed-loop workflow connecting HL7 ORU delivery through Mirth Connect,
OpenEMR persistence, and clinician-visible Playwright validation.

## Test State

The validation uses the deterministic synthetic patient:

- MRN: `SYNTHMRN000001`
- Patient: `Synthetic001 Test Patient001`

The existing OpenEMR laboratory state contains:

- LOINC: `2345-7`
- Test: `Glucose`
- Result: `96`
- Unit: `mg/dL`
- Reference range: `70-99`

The test does not create or directly insert this laboratory result.

## Automated Workflow

`tests/ui/openemr/patient-lab-result.spec.ts` performs the following workflow:

1. Authenticates to OpenEMR.
2. Synchronizes on successful application navigation rather than relying only
   on browser load events.
3. Opens the patient search workflow.
4. Locates the deterministic synthetic patient.
5. Confirms the selected patient using the exact MRN.
6. Waits for the asynchronous Labs dashboard widget to become clinically ready.
7. Opens the clinician-facing laboratory data view.
8. Selects the LOINC `2345-7` result.
9. Uses the matrix laboratory presentation.
10. Performs row-scoped assertions for:
    - `Glucose`
    - `70-99`
    - `mg/dL`
    - `96`

The assertions are intentionally scoped to the laboratory result row so that
unrelated text elsewhere in the page cannot satisfy the clinical validation.

## Synchronization Finding

During development, the OpenEMR patient dashboard could complete primary
navigation while asynchronous clinical widgets remained in a `Loading...`
state.

Increasing generic browser navigation timeouts would not establish that the
laboratory widget was clinically ready.

The test therefore synchronizes on the application-level readiness signal:

`Click here to view and graph all labdata.`

This separates successful patient-dashboard navigation from completion of the
asynchronously populated laboratory widget.

## Validation Results

Targeted headed execution:

- PASS

Repeated headed execution:

- 3 consecutive passes

Combined OpenEMR Playwright suite:

- 4 passed

Full Python regression suite after runtime readiness validation:

- 545 passed
- 1 skipped
- 1 xfailed
- 34 warnings

The Python regression warnings are associated with unverified HTTPS requests
against the local laboratory environment and were not failures.

## Runtime Readiness

The full Python regression was executed after the runtime readiness preflight
reported:

`RUNTIME READINESS: PASS`

Both normal and restricted FHIR authentication contexts were refreshed before
the successful regression run.

A prior regression attempt exposed expired FHIR authentication prerequisites.
A subsequent attempt exposed stale Windows pytest runtime-directory state.
Neither condition represented an application regression. After restoring
runtime prerequisites and removing the stale `.pytest_runtime` directory, the
complete Python suite passed.

## Validated Claim

This increment supports the following claim:

> Automated a clinician-visible OpenEMR laboratory workflow against
> deterministic patient state, including authenticated navigation, patient
> identification, asynchronous clinical-widget synchronization, LOINC-specific
> result selection, and row-scoped validation of Glucose 96 mg/dL with
> reference range 70-99.

## Scope Boundary

This increment proves clinician-visible UI validation of an existing
deterministic OpenEMR laboratory result.

It does **not** yet prove that the same Playwright execution is driven by a
newly delivered Mirth ORU transaction.

That closed-loop integration is the next increment:

`ORU -> Mirth -> accepted audit state -> guarded OpenEMR delivery -> native persistence -> Playwright clinical UI validation`
