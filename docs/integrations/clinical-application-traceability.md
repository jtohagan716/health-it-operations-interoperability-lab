# Clinical Application Validation Traceability

This matrix summarizes the evidence in the synthetic ORU source-onboarding case study. The source-specific path is documented in [`warren-oru-openemr-case-study/README.md`](warren-oru-openemr-case-study/README.md).

| ID | Requirement | Evidence | Status |
|---|---|---|---|
| APP-001 | Identify the sending application and facility. | Synthetic source metadata is asserted by `test_meditech_style_source_contract.py`. | Evidenced |
| APP-002 | Validate a conformant synthetic ORU^R01 source scenario. | Source contract and live scenario tests; accepted ORU runtime scenarios. | Evidenced |
| APP-003 | Preserve patient identity and demographics. | Source contract and accepted audit context for synthetic patient `LAB000001`. | Evidenced |
| APP-004 | Preserve placer and filler order identity. | Scenario, Mirth runtime context, and OpenEMR target reconciliation. | Evidenced |
| APP-005 | Preserve result code and clinical result semantics. | LOINC `2345-7`, `92 mg/dL`, range `70-99`, normal flag, final status; OpenEMR database and provider view agree. | Evidenced |
| APP-006 | Return the expected MLLP acknowledgment to the sender. | Mirth logged ACK policy `AA`, but the sender timed out without receiving response bytes. | In progress; transport defect unresolved |
| APP-007 | Publish this source-specific result to FHIR. | FHIR mapping/runtime capabilities exist in separate workflows; this case study did not publish the order-109 message to FHIR. | Out of scope |
| APP-008 | Demonstrate source-specific replay and conflict handling. | Related replay safeguards exist, but source-specific replay/conflict evidence for this case is not included. | In progress |
| APP-009 | Triage the observed failure and document recovery. | Sender timeout was correlated with Mirth acceptance/persistence; guarded delivery later completed. ACK root cause remains open. | Partial evidence |
| APP-010 | Reconcile source, interface, and persisted result semantics. | Mirth context, delivery response, OpenEMR database row, and provider view agree on patient/order/result identifiers and values. | Evidenced |
| APP-011 | Check existing behavior after adding the source scenario. | October 13, 2026 focused run: 8 tests passed in 5.95 seconds. | Evidenced |
| APP-012 | Record scope, expected outcomes, test results, and limitations. | Case study, this matrix, runbook, and evidence screenshots. | Evidenced |
| APP-013 | Provide reproducible operational instructions. | [`clinical-interface-operations-runbook.md`](clinical-interface-operations-runbook.md). | Evidenced |
| APP-014 | Protect privacy in the portfolio exercise. | Synthetic patient and order data; no production endpoint or real patient record. | Evidenced for this local test scope |
| APP-015 | Govern AI-enabled clinical functionality. | No AI functionality is part of this exercise. | Out of scope |

## Recorded regression run

```text
python -m pytest -q .\tests\interoperability\test_live_oru_scenario_contract.py .\tests\interoperability\test_meditech_style_source_contract.py
........ [100%]
8 passed in 5.95s
```

This test run is separate from the later order-109 delivery evidence. The source-specific sender did not receive ACK bytes, even though Mirth logged an `AA` policy decision and persisted the message. The guarded OpenEMR delivery and clinical result reconciliation succeeded independently.

## Boundaries

The source is a synthetic MEDITECH Expanse-style simulation. The evidence does not establish direct MEDITECH administration, production deployment, Warren Hospital connectivity, formal end-user UAT, or source-specific FHIR publication.
