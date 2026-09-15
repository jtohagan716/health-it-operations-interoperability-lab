from pathlib import Path

from scripts.ccda.migration.reconcile_source_to_ccda import reconcile


SOURCE_PATH = Path(
    "examples/ccda/migration/avery-source.xml"
)

VALID_TARGET_PATH = Path(
    "examples/ccda/migration/avery-target-ccda.xml"
)

MISSING_ROUTE_TARGET_PATH = Path(
    "tests/ccda/fixtures/avery-target-ccda-missing-route.xml"
)


def test_valid_migration_reconciles_successfully():
    result = reconcile(
        SOURCE_PATH,
        VALID_TARGET_PATH,
    )

    assert result["status"] == "PASS"

    assert all(
        check["status"] == "PASS"
        for check in result["checks"]
    )


def test_missing_medication_route_is_quarantined():
    result = reconcile(
        SOURCE_PATH,
        MISSING_ROUTE_TARGET_PATH,
    )

    assert result["status"] == "QUARANTINE"

    failures = {
        check["field"]: check
        for check in result["checks"]
        if check["status"] == "FAIL"
    }

    assert "medication.route.code" in failures

    assert (
        failures["medication.route.code"]["expected"]
        == "C38288"
    )

    assert (
        failures["medication.route.code"]["actual"]
        is None
    )
