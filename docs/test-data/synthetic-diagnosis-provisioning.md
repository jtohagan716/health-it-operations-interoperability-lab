# Synthetic condition and encounter-diagnosis provisioning

This issue #31 increment adds clinically coherent ICD-10-CM conditions to the deterministic OpenEMR population. It deliberately distinguishes ongoing problem-list conditions from diagnoses associated with a particular encounter.

## Population model

* 100 encounter diagnoses: one for every synthetic patient's historical encounter
* 50 longitudinal problems: one for each patient in the prediabetes, diabetes, hypertension, cardiovascular, and respiratory cohorts
* 150 total `medical_problem` source records
* 100 `issue_encounter` relationships
* no billing or charge rows

The one-patient probe uses `SYNTHMRN000002`, a hypertension patient in the generated population, so it exercises both the unlinked problem-list and linked encounter-diagnosis paths.

Cohort membership is resolved from the persisted synthetic patient record rather than inferred from patient numbering. Stable external identifiers allow the population process to distinguish previously provisioned records from records that still require creation.

## Native OpenEMR behavior

`ConditionService::insert()` creates the source record in `lists`, assigns its UUID, and applies OpenEMR validation.

`PatientIssuesService::linkIssueToEncounter()` creates the encounter relationship and its UUID without replacing unrelated issue links.

OpenEMR's FHIR Condition implementation separates:

* unlinked `medical_problem` records into the `problem-list-item` category
* records linked through `issue_encounter` into the `encounter-diagnosis` category

The provisioning model maintains separate records when both longitudinal and encounter-specific clinical concepts are required.

Problem-list records use an onset date before the patient's historical encounter. Encounter-diagnosis records use the associated encounter date and retain an explicit `issue_encounter` relationship.

The implementation does not infer an encounter relationship merely because dates happen to match.

## Safety controls

* local synthetic environment only
* dry run by default
* one-patient representative probe
* exact commit-count confirmation
* synthetic patient and encounter preconditions
* active ICD-10-CM code validation
* stable external identifiers
* post-write relationship verification
* idempotent replay
* reverse-order compensating cleanup
* no billing-table writes

The receiver rejects writes outside the explicitly identified local-lab environment. Commit mode requires the caller to provide the expected patient count, preventing an accidental population run against an unexpected database.

Verification independently reconciles source records, unique external identifiers, UUIDs, patient coverage, condition categories, encounter relationships, diagnosis dates, longitudinal onset dates, and billing-table boundaries.

## Commands

Dry run:

```powershell
python -m scripts.synthetic.diagnoses
```

One-patient probe:

```powershell
python -m scripts.synthetic.diagnoses --probe --commit --environment local-lab --confirm-patient-count 1
```

Verify the probe:

```powershell
python -m scripts.synthetic.diagnoses --probe --verify
```

Full population:

```powershell
python -m scripts.synthetic.diagnoses --commit --environment local-lab --confirm-patient-count 100
```

Full verification:

```powershell
python -m scripts.synthetic.diagnoses --verify
```

A successful full verification confirms:

* 150 conditions
* 150 unique external identifiers
* 150 unique UUIDs
* 100 covered patients
* 100 encounter-diagnosis records
* 50 problem-list records
* 100 unique encounter links
* 100 linked patients
* zero missing encounter links
* zero incorrectly linked problems
* zero patient or encounter mismatches
* 100 diagnosis dates matching their encounters
* 50 chronic problems with prior onset dates
* zero synthetic billing rows

Replaying the population command is idempotent: all expected records resolve as existing, and no duplicate conditions or relationships are created.

## FHIR client authorization

The registered OpenEMR SMART/FHIR client requests `user/Condition.rs` in addition to the scopes required by the existing patient, encounter, observation, diagnostic report, medication, practitioner, and organization validations.

The OpenEMR 8.3.0 runtime test used a separate client registration and token file from the OpenEMR 8.2.0 environment. This prevented credentials, authorization endpoints, redirect metadata, and access tokens from being mixed between the installations.

The OpenEMR 8.3.0 authorization flow demonstrated:

* successful dynamic client registration
* explicit API-client approval in OpenEMR
* successful authorization-code issuance
* successful OAuth state validation
* successful token exchange
* a bearer token containing `user/Condition.rs`
* an authenticated patient-based Condition search returning HTTP `200`

The registration and temporary token files contain credentials and must not be committed or included in evidence output.

## FHIR Condition validation

An authenticated patient-based Condition search returned the expected problem-list and encounter-diagnosis resources from the deterministic population and preserved:

* patient references
* encounter references for encounter diagnoses
* `problem-list-item` and `encounter-diagnosis` categories
* clinical and verification statuses
* onset dates
* abatement dates for ended conditions
* human-readable condition descriptions
* stable logical resource identities across repeated reads

Database-to-FHIR reconciliation identified a structured-coding preservation issue in the tested OpenEMR environments.

Synthetic records retained values such as `ICD10:I10` in `lists.diagnosis`, while the resulting FHIR resources populated `Condition.code.text` without exposing `Condition.code.coding`.

## OpenEMR 8.2.0 native control

A separate control condition was created through OpenEMR 8.2.0's native issue editor by selecting Essential (primary) hypertension from its ICD-10 terminology search.

OpenEMR stored the selected code as `ICD10:I10.` and produced the same text-only FHIR representation observed for the synthetic records.

The returned `Condition.code` contained:

```json
{
  "text": "Essential (primary) hypertension"
}
```

The `coding` property was absent even though the diagnosis had been selected through OpenEMR's native terminology interface.

Ending the native control condition correctly produced:

* `clinicalStatus` of `inactive`
* the original `onsetDateTime`
* the expected `abatementDateTime`
* the human-readable condition description

This demonstrated that lifecycle semantics were preserved even though the structured ICD-10 coding was not exposed.

## OpenEMR 8.3.0 isolated validation environment

A clean OpenEMR 8.3.0 environment was created alongside the existing OpenEMR 8.2.0 lab without modifying or reusing its containers, database, volumes, ports, or OAuth credentials.

The isolated environment used:

* Compose project `health-it-openemr-830-validation`
* OpenEMR image `openemr/openemr:8.3.0`
* pinned image digest `sha256:999fbeb1f88976c18a97067a7b98dfd7912d5174f51f5939b4b9a56f10c5c79c`
* MariaDB 11.8.8 pinned by digest
* HTTP port `8400`
* HTTPS port `9400`
* separate database, site-data, and log volumes
* a fresh OpenEMR database
* a separately registered SMART/FHIR client
* separate registration and token files

Inspection of `version.php` inside the running container confirmed:

* major version `8`
* minor version `3`
* patch version `0`

The fresh environment initially contained zero patients, zero medical problems, and zero ICD-10 diagnosis rows. This established that the validation stack was isolated from the populated OpenEMR 8.2.0 environment.

The following OpenEMR connector settings were configured:

* Standard REST API enabled
* Standard FHIR REST API enabled
* Site Address Override set to `https://localhost:9400`
* FHIR system scopes left disabled
* patient portal REST API left disabled
* OAuth2 password grant left disabled

The official ICD-10 terminology package was installed through OpenEMR's External Data Loads interface.

Database verification then confirmed:

* 98,186 ICD-10 diagnosis rows
* active ICD-10 code type
* active hypertension code `I10`
* formatted OpenEMR code `I10.`
* description `Essential (primary) hypertension`

These checks rule out missing or inactive terminology as the cause of the FHIR coding behavior.

## OpenEMR 8.3.0 native control

A new control patient and condition were created through the clean OpenEMR 8.3.0 user interface.

The condition was created through the native issue editor by selecting Essential (primary) hypertension from the installed ICD-10 terminology search.

Database inspection showed:

* source table `lists`
* type `medical_problem`
* title `Essential (primary) hypertension`
* diagnosis `ICD10:I10.`
* verification status `confirmed`
* activity value `1`
* no end date

The authenticated FHIR request used the control patient's UUID as the `patient` search parameter and returned HTTP `200` with one Condition resource.

The response preserved:

* the database condition UUID as `Condition.id`
* the control patient UUID as `Condition.subject.reference`
* category `problem-list-item`
* clinical status `active`
* verification status `confirmed`
* the original onset date
* the human-readable description

Database-to-FHIR reconciliation produced an exact identity match:

```text
Database condition UUID:
a2a742d5-2d87-4384-bf58-d2799b69dbcf

FHIR Condition.id:
a2a742d5-2d87-4384-bf58-d2799b69dbcf
```

However, the returned code remained text-only:

```json
{
  "text": "Essential (primary) hypertension"
}
```

The null-safe validation result was:

```text
CodingPropertyExists: False
NonNullStructuredCodings: 0
```

The non-null check is important because wrapping a missing PowerShell property directly in an array can produce a misleading count for `$null`. The final validation explicitly filtered null values before calculating the structured-coding count.

## Source analysis

Source inspection explains the observed behavior.

The FHIR Condition services select `lists.diagnosis` as a string. The shared `FhirConditionTrait::populateCode()` implementation creates structured `FHIRCoding` elements only when the supplied diagnosis value is a non-empty array.

When `diagnosis` is not an array, the implementation follows its fallback path and creates a `FHIRCodeableConcept` containing only the issue title as text:

```php
if (!empty($dataRecord['diagnosis']) && is_array($dataRecord['diagnosis'])) {
    // Populate Condition.code.coding.
} else {
    // Fall back to Condition.code.text.
}
```

A read-only source comparison found that the shared Condition coding implementation is byte-for-byte identical in the tested OpenEMR 8.2.0 and OpenEMR 8.3.0 images.

The version-specific differences found in the problem-list and encounter-diagnosis services were limited to Provenance construction and handling. They did not change diagnosis parsing or `Condition.code` population.

## Finding and interpretation

The clean OpenEMR 8.3.0 native-control reproduction rules out the following project or operator errors:

* synthetic provisioning logic
* direct database insertion by the synthetic tooling
* missing ICD-10 terminology
* inactive ICD-10 code configuration
* manually typed rather than terminology-selected diagnosis data
* an invalid patient UUID
* a condition UUID mismatch
* use of an OpenEMR 8.2.0 access token against OpenEMR 8.3.0
* missing `user/Condition.rs` authorization
* failure to enable the FHIR API
* an unauthorized FHIR request
* differences between the tested 8.2.0 and 8.3.0 shared coding method

The evidence therefore establishes a reproducible OpenEMR 8.3.0 FHIR interoperability limitation: a diagnosis selected through OpenEMR's native ICD-10 terminology interface can be stored as a structured source value such as `ICD10:I10.` but exported as only `Condition.code.text`, without a corresponding `Condition.code.coding` element.

The finding was reported upstream as [OpenEMR issue #13828: FHIR Condition omits code.coding for native ICD-10 diagnosis in OpenEMR 8.3.0](https://github.com/openemr/openemr/issues/13828). The report includes the native user-interface reproduction, database-to-FHIR reconciliation, authenticated request evidence, expected and actual FHIR representations, environment details, and relevant source analysis.

Other Condition semantics remain correctly represented, so this finding is narrowly scoped to the preservation of structured diagnosis coding. It does not imply that the complete Condition resource, Condition search operation, or synthetic provisioning workflow is generally defective.

## Scope boundary

This increment provisions clinical condition records and encounter relationships. It does not create charges, claims, medications, laboratory results, or radiology results.

The isolated OpenEMR 8.3.0 work validates compatibility and investigates native FHIR behavior. It does not modify OpenEMR application source code or introduce a workaround that rewrites the product's FHIR output.
