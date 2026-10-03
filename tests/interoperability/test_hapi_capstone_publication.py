from scripts.fhir.publish_capstone_to_hapi import (
    publish_capstone,
)


def test_capstone_publication_is_replay_safe():
    first_run = publish_capstone()
    second_run = publish_capstone()

    assert first_run["passed"] is True
    assert second_run["passed"] is True

    assert second_run["actions"] == {
        "patient": "reused",
        "observation": "reused",
        "diagnostic_report": "reused",
    }

    assert (
        first_run["resources"]
        == second_run["resources"]
    )

    assert (
        second_run["checks"]
        ["patient_identity_preserved"]
        is True
    )

    assert (
        second_run["checks"]
        ["observation_subject_links_patient"]
        is True
    )

    assert (
        second_run["checks"]
        ["diagnostic_report_links_observation"]
        is True
    )

    assert (
        second_run["checks"]
        ["observation_search_finds_result"]
        is True
    )