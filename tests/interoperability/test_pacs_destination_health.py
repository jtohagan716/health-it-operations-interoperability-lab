from scripts.dicom.pacs_destination_health import (
    build_destination_health_report,
)


def get_destination(
    report: dict,
    name: str,
) -> dict:
    for destination in report["destinations"]:
        if destination["name"] == name:
            return destination

    raise AssertionError(
        f"Destination not found: {name}"
    )


def test_interoplab_destination_is_healthy():
    report = (
        build_destination_health_report()
    )

    destination = get_destination(
        report,
        "interoplab",
    )

    assert destination["ae_title"] == "INTEROPLAB"
    assert destination["port"] == 11112
    assert destination["healthy"] is True
    assert destination["http_status"] == 200


def test_unavailable_destination_is_detected_as_unhealthy():
    report = (
        build_destination_health_report()
    )

    destination = get_destination(
        report,
        "unavailable",
    )

    assert destination["ae_title"] == "UNAVAILABLE"
    assert destination["port"] == 11113
    assert destination["healthy"] is False
    assert destination["http_status"] == 500


def test_pacs_destination_health_reports_degraded_state():
    report = (
        build_destination_health_report()
    )

    assert report["healthy_count"] == 1
    assert report["unhealthy_count"] == 1
    assert report["overall"] == "DEGRADED"