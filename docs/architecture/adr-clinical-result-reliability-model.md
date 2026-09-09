# ADR: Clinical Result Reliability Model

- **Status:** Proposed
- **Date:** 2026-09-09
- **Decision owners:** Health IT Operations Interoperability Lab
- **Initial proving workflow:** Multi-analyte laboratory `ORU^R01`

## Context

The current interoperability lab proves a closed-loop laboratory workflow:

```text
OpenEMR order
  -> OML^O21 over MLLP
  -> Mirth Connect
  -> persistent synthetic LIS
  -> ORU^R01 over MLLP
  -> Mirth audit persistence
  -> guarded OpenEMR delivery
  -> OpenEMR laboratory result
```

The first implementation intentionally constrained the clinical result profile
to one OBR and one numeric OBX. That constraint allowed the project to prove
transport, correlated acknowledgments, durable persistence, clinical chronology,
duplicate protection, recovery after ambiguous ACK outcomes, and end-to-end
OpenEMR reconciliation.

The constraint now appears across multiple layers:

- the synthetic LIS creates a singular `observation` object;
- Mirth extracts singular observation values into the channel map;
- validation evaluates one OBX;
- persistence performs one observation insert;
- the delivery claim selects one observation with `LIMIT 1`;
- reconstruction emits one OBX;
- analyzers and tests expose singular result fields;
- the current laboratory profile requires OBR-4 and OBX-3 to contain the same
  code.

The existing `audit.oru_observations` child table indicates an intended
one-to-many relationship, but the active workflow currently collapses the
message to one observation.

Adding panels through isolated patches would solve the immediate case but
would likely require repeated restructuring for multiple OBR groups, specimens,
contextual notes, typed values, corrections, and other diagnostic domains.

## Decision

Adopt a layered, loss-aware clinical result reliability model that separates:

1. immutable transport evidence;
2. lossless HL7 wire structure;
3. versioned canonical clinical meaning;
4. versioned validation and terminology policy;
5. durable accepted clinical events;
6. destination-specific projections;
7. semantic reconciliation evidence.

No layer may silently replace or discard the evidence retained by an earlier
layer.

## Architectural goals

The model will:

- preserve the exact inbound message and its transport context;
- represent repeating reports, observations, specimens, and notes;
- retain both source terminology and normalized terminology assertions;
- represent result values by type without discarding their raw form;
- distinguish structural validation from profile and destination policy;
- produce structured, location-aware validation findings;
- distinguish exact replay, identifier conflict, and semantic redelivery;
- preserve clinical event history separately from current clinical state;
- disclose destination mapping loss;
- support deterministic reconstruction and reconciliation;
- preserve existing single-glucose behavior while allowing additive growth.

The model will not attempt to support every optional HL7 segment in the first
implementation.

## Reference structure

HL7 `ORU^R01` represents a hierarchy rather than a flat list of fields. The
relevant conceptual structure is:

```text
Patient result
└── Order observation / report group (repeating)
    ├── OBR
    ├── Report notes (repeating)
    ├── Observation group (repeating)
    │   ├── OBX
    │   └── Observation notes (repeating)
    └── Specimen group (repeating)
```

The canonical model will preserve this hierarchy without reproducing every
HL7-version-specific implementation detail.

## Layer 1: Immutable inbound event

Every receive attempt will retain:

- raw payload;
- payload digest;
- sender and receiving endpoint identity;
- transport type;
- operational receipt timestamp;
- declared message-control ID;
- HL7 version and message structure when detectable;
- processing-attempt identity;
- relationship to earlier attempts when classified as replay or conflict.

The raw payload is append-only evidence. Corrections and retransmissions create
new events or attempts; they do not overwrite the received payload.

### Transport identity

Two complementary identities will be used:

```text
Declared identity = sender + sending facility + message-control ID
Content identity  = digest of canonicalized wire content
```

Initial classifications:

| Declared identity | Content identity | Classification |
| --- | --- | --- |
| New | New | `FIRST_DELIVERY` |
| Existing | Same | `EXACT_REPLAY` |
| Existing | Different | `IDENTITY_CONFLICT` |
| New | Previously observed | `SEMANTIC_REDELIVERY_CANDIDATE` |

The last classification is evidence, not an automatic duplicate decision.
Clinical equivalence requires semantic evaluation.

## Layer 2: Lossless HL7 structure

Parsing will preserve enough wire information to reinterpret the original
message later:

- segment occurrence and sequence;
- field, repetition, component, and subcomponent values;
- empty fields where position is meaningful;
- escape sequences or their reversible representation;
- unknown and custom Z-segments;
- the structural group path assigned to each segment;
- the original raw segment.

This representation describes what arrived. It does not claim that the content
is clinically valid.

## Layer 3: Versioned canonical clinical event

The semantic representation will be independent of Mirth channel-map fields,
PostgreSQL row layouts, OpenEMR tables, and any single HL7 version.

```text
ClinicalResultEvent
├── model name and version
├── event identity and provenance
├── subject identity
├── encounter identity
├── request references[]
└── reports[]
    ├── report identity and sequence
    ├── placer and filler identifiers
    ├── service concepts[]
    ├── status and lifecycle event
    ├── effective and issued times
    ├── performers[]
    ├── specimens[]
    ├── notes[]
    └── observations[]
        ├── observation identity and sequence
        ├── source and normalized concepts
        ├── typed value
        ├── interpretations[]
        ├── reference ranges[]
        ├── status and effective time
        ├── method and device
        ├── parent/child relationships
        └── notes[]
```

Every canonical event will identify the model version that produced it.

### Identity and ordering

Separate identifiers will be preserved for:

- receive attempt;
- declared HL7 message;
- patient-result group;
- report/order-observation group;
- specimen;
- observation;
- destination projection and delivery attempt.

Wire sequence and semantic identity are different. `OBX-1` and database row
order help reconstruct sequence but are not, by themselves, sufficient clinical
identifiers.

## Typed result values

The canonical model will use an explicit value union rather than treating every
OBX-5 value as interchangeable text.

Initial implemented types:

- `NumericValue`;
- `TextValue`.

Reserved extensions:

- `CodedValue`;
- `DateTimeValue`;
- `QuantityValue`;
- `RangeValue`;
- `RatioValue`;
- `CompositeValue`;
- `AttachmentValue`;
- `AbsentValue`;
- `UnsupportedValue`.

Every representation retains the source value. A normalized or parsed value is
an additional assertion, not a destructive replacement.

## Terminology model

Source terminology will be preserved alongside normalized terminology:

```text
Source assertion
  -> mapping assertion
  -> normalized concept
```

A mapping assertion records:

- source system, code, and display;
- canonical system, code, and display;
- mapping authority;
- mapping/profile version;
- verification status;
- effective period;
- optional explanatory evidence.

Panel membership will be versioned policy data rather than inferred from string
equality.

For the existing single-analyte glucose profile, OBR-4 and OBX-3 may be required
to agree. For a panel profile, OBR-4 identifies the ordered panel and OBX-3
identifies an allowed panel member.

The first implementation will use a small repository-owned terminology fixture.
It will not attempt to build a general-purpose terminology server.

## Validation model

Validation will return structured findings rather than only a Boolean result or
concatenated error string.

Each finding contains:

```text
rule identifier
rule/profile version
severity
category
canonical location
HL7 location when applicable
expected condition
observed value or condition
human-readable explanation
```

Initial categories:

- `SYNTAX`;
- `STRUCTURE`;
- `TERMINOLOGY`;
- `PROFILE`;
- `CLINICAL_CONSISTENCY`;
- `DESTINATION_CAPABILITY`;
- `SECURITY`;
- `OPERATIONAL_DEPENDENCY`.

Example:

```json
{
  "rule_id": "LAB-NM-001",
  "profile_version": "lab-result-1.0.0",
  "severity": "ERROR",
  "category": "PROFILE",
  "location": "reports[0].observations[2].value",
  "hl7_location": "OBR[1]/OBX[3]-5",
  "expected": "Numeric value for NM observation",
  "observed": "ABC",
  "message": "OBX[3]-5 must contain a numeric value"
}
```

Policy converts findings into a disposition:

- `ACCEPT`;
- `ACCEPT_WITH_WARNING`;
- `QUARANTINE`;
- `REJECT`;
- `HOLD_FOR_REVIEW`.

## Structural rules versus profile policy

Structural processing determines what the message contains and how repetitions
are grouped.

Profile policy determines what a particular workflow permits, including:

- required identifiers;
- supported message versions;
- allowed value types;
- terminology requirements;
- permitted panel membership;
- status-transition rules;
- atomicity rules;
- sender-specific constraints;
- destination capability requirements.

Rules will be independently identifiable and versioned. The initial
implementation may execute them in Python and Mirth, but their identity and
expected behavior must not depend on anonymous script position.

## Atomicity

The initial laboratory policy will use report-level atomic acceptance:

> If any required observation in a report group contains an error-level
> structural, terminology, profile, or clinical-consistency finding, none of
> that report group's clinical observations are accepted for delivery.

For the first implementation, a message containing one report group therefore
behaves atomically as a whole.

Future profiles may permit different atomicity boundaries, but partial delivery
must never occur implicitly.

## Durable persistence model

The target logical hierarchy is:

```text
inbound_events
└── processing_attempts
    └── clinical_result_events
        └── result_reports
            ├── result_specimens
            ├── result_notes
            └── result_observations
                └── result_notes
```

Existing tables and migrations will be evolved rather than replaced without
evidence. Physical table names may continue to use the established `audit.oru_*`
names.

Required durable properties include:

- foreign-key ownership at each level;
- explicit report and observation sequence;
- preservation of OBR and OBX set IDs;
- unique constraints scoped to the correct parent;
- immutable raw evidence;
- transactional persistence of accepted report content;
- versioned model and profile identifiers;
- queryable processing disposition and validation findings.

## Clinical history and current state

Inbound clinical events and current destination state are separate concerns.

```text
Immutable result events
  -> deterministic lifecycle projection
  -> current clinical result state
```

A future preliminary, final, or corrected result will append a clinical event.
It will not overwrite the only evidence of the prior state.

Lifecycle implementation is deferred from the initial panel increment, but the
identity and versioning model must not prevent it.

## Destination projection

OpenEMR is the first destination adapter. Its schema does not define the
canonical model.

Before delivery, the adapter will create a projection plan containing:

- supported content;
- mapped fields;
- expected report and result counts;
- unsupported or unmapped content;
- loss warnings;
- blocking capability conflicts;
- expected destination-state fingerprint.

Policy determines whether identified loss is acceptable. Clinically significant
loss must not be silent.

## Reconciliation

Reconciliation will compare:

1. the accepted canonical clinical event;
2. the expected destination projection;
3. the observed destination state.

Possible outcomes:

- `EQUIVALENT`;
- `EQUIVALENT_AFTER_PERMITTED_NORMALIZATION`;
- `INCOMPLETE`;
- `DUPLICATED`;
- `CONFLICTING`;
- `UNVERIFIABLE`.

Counts remain useful evidence, but semantic comparison will include stable
clinical attributes such as patient, order identifiers, report service,
observation code, effective time, typed value, units, and status.

## First implementation slice

The first implementation will prove the architecture with:

1. the existing one-OBR/one-OBX glucose scenario;
2. one OBR containing a four-analyte synthetic chemistry panel;
3. numeric and text value representation where required by fixtures;
4. iterative and location-aware observation validation;
5. atomic rejection when one panel observation is invalid;
6. transactional persistence of the complete panel;
7. deterministic retrieval and reconstruction of all observations;
8. one OpenEMR report containing the expected result rows;
9. exact-replay behavior with unchanged destination counts;
10. same-control-ID/different-content conflict detection;
11. database and OpenEMR user-interface reconciliation.

## Design-pressure fixtures

The architecture will be evaluated against four message shapes:

| Fixture | Purpose | Initial runtime support |
| --- | --- | --- |
| One OBR, one numeric OBX | Backward compatibility | Required |
| One OBR, four OBXs | Multi-analyte panel | Required |
| Two OBR groups with separate OBXs | Repeating report groups | Representable; runtime may be deferred |
| OBR with SPM, report NTE, and OBX NTE | Context preservation | Representable; runtime may be deferred |

A deferred fixture must parse or map into the designed representation without
forcing a destructive model change, even if delivery is not yet supported.

## Deferred capabilities

The following are explicitly outside the first implementation:

- complete support for multiple OBR groups;
- preliminary-to-final transitions;
- corrected and cancelled results;
- complete specimen workflow;
- complete NTE delivery;
- coded, composite, ratio, attachment, and encapsulated values;
- microbiology isolate and susceptibility graphs;
- a production terminology service;
- arbitrary vendor profiles;
- cross-destination orchestration;
- production security and scale claims.

These capabilities inform the extension points but do not justify speculative
implementation.

## Compatibility strategy

Existing single-observation fixtures and APIs will remain operational during the
transition.

Compatibility may be provided through adapters that convert:

```text
legacy singular observation
  -> one report containing one observation
```

New code will consume collections. Singular compatibility accessors must not be
used in the new processing path and should be marked for eventual retirement.

## Implementation sequence

1. Complete the current implementation and schema inventory.
2. Define canonical Python types and serialization fixtures.
3. Add design-pressure tests before modifying runtime behavior.
4. Add or evolve report/observation persistence with a numbered migration.
5. Generalize ORU construction and parsing.
6. Implement structured validation findings and the first laboratory profile.
7. Generalize Mirth extraction and transactional persistence.
8. Generalize delivery retrieval and deterministic reconstruction.
9. Validate OpenEMR projection and reconciliation.
10. Exercise replay, conflict, malformed-child, outage, and recovery cases.
11. Document observed evidence and remaining limitations.

## Verification requirements

The decision is successfully demonstrated when:

- existing single-glucose contracts continue to pass;
- no repeated OBR or OBX is silently discarded by the structural model;
- a four-observation panel is retained end to end;
- one invalid required observation prevents partial clinical persistence;
- exact replay produces no duplicate report or result rows;
- an identity conflict is rejected or quarantined with a structured finding;
- source and normalized terminology remain separately inspectable;
- OpenEMR contains one report and the expected multiple results;
- clinical timestamps remain distinct from operational timestamps;
- reconciliation reports semantic equivalence or a specific discrepancy;
- every unsupported capability is disclosed rather than silently lost.

## Consequences

### Benefits

- likely future result structures become additive extensions;
- failures can be localized to parsing, semantics, policy, persistence,
  projection, or reconciliation;
- raw evidence remains available when mappings evolve;
- validation becomes explainable to operators and implementers;
- destination limitations cannot silently redefine clinical meaning;
- the architecture supports laboratory and radiology profiles without treating
  their clinical rules as identical;
- the project demonstrates healthcare integration reliability rather than only
  message transmission.

### Costs and risks

- more explicit types and tables increase initial complexity;
- model and profile versions require governance;
- maintaining raw, canonical, and projected representations consumes storage;
- Mirth JavaScript may be an awkward location for complex domain logic;
- compatibility adapters can become permanent unless retirement is managed;
- excessive abstraction could delay delivery of tested clinical workflows.

These risks will be controlled by requiring every implemented abstraction to be
justified by a fixture or operational scenario.

## Alternatives considered

### Patch the existing singular workflow

Rejected as the long-term direction. It would deliver the panel quickly but
repeat the same restructuring for multiple reports, specimens, notes, typed
values, and lifecycle events.

### Mirror OpenEMR tables as the canonical model

Rejected. OpenEMR is one destination and may not preserve every source concept
or future workflow requirement.

### Store only raw HL7

Rejected. Raw preservation is necessary but does not provide queryable clinical
meaning, explainable validation, or destination reconciliation.

### Use FHIR resources as the only internal model

Deferred. FHIR provides valuable semantic guidance, but immediate conversion
could obscure HL7 wire evidence and introduce mapping questions unrelated to the
first result-processing goal.

### Build a complete terminology service

Rejected for the current scope. A small versioned terminology fixture provides
the required mapping and panel-membership behavior without creating an unrelated
platform project.

## References

- HL7 Version 2.5.1, Chapter 7, Observation Reporting:
  https://www.hl7.eu/HL7v2x/v251/std251/ch07.html
- HL7 refactored ORU_R01 message description:
  https://www.hl7.eu/refactored/msgORU_R01.html
- HAPI HL7v2 ORU_R01 generated structures:
  https://hapifhir.github.io/hapi-hl7v2/v25/apidocs/ca/uhn/hl7v2/model/v25/message/ORU_R01.html
- FHIR DiagnosticReport examples:
  https://fhir.hl7.org/fhir/diagnosticreport-examples.html
- FHIR Observation definitions:
  https://fhir.hl7.org/fhir/observation-definitions.html
- OpenELIS Global:
  https://github.com/DIGI-UW/OpenELIS-Global-2
- OpenEMR HL7 result receiver:
  https://github.com/openemr/openemr/blob/master/interface/orders/receive_hl7_results.inc.php
- OpenEMR laboratory testability proposal:
  https://github.com/openemr/openemr/issues/10910

