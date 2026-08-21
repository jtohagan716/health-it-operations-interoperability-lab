import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest


ORTHANC_URL = "http://127.0.0.1:8042"

EXPECTED_SERIES_DESCRIPTION = "Synthetic QA Series"


def get_json(path: str):
    with urlopen(
        f"{ORTHANC_URL}{path}",
        timeout=10,
    ) as response:
        return json.load(response)


def post_json(
    path: str,
    payload: dict,
):
    body = json.dumps(
        payload
    ).encode("utf-8")

    request = Request(
        f"{ORTHANC_URL}{path}",
        data=body,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urlopen(
        request,
        timeout=30,
    ) as response:
        content = response.read()

        if not content:
            return None

        return json.loads(
            content.decode("utf-8")
        )


def find_series_id() -> str:
    studies = get_json(
        "/studies"
    )

    assert studies, (
        "No studies found in Orthanc."
    )

    for study_id in studies:
        study = get_json(
            f"/studies/{study_id}"
        )

        for series_id in study.get(
            "Series",
            [],
        ):
            series = get_json(
                f"/series/{series_id}"
            )

            description = (
                series
                .get(
                    "MainDicomTags",
                    {},
                )
                .get(
                    "SeriesDescription",
                    "",
                )
            )

            if (
                description
                == EXPECTED_SERIES_DESCRIPTION
            ):
                return series_id

    raise AssertionError(
        "Synthetic QA Series was not found."
    )


def send_series_to_modality(
    modality_name: str,
):
    series_id = find_series_id()

    return post_json(
        f"/modalities/{modality_name}/store",
        {
            "Resources": [
                series_id
            ],
            "Synchronous": True,
        },
    )


def test_manual_equivalent_route_to_interoplab_succeeds():
    result = send_series_to_modality(
        "interoplab"
    )

    assert result is not None

    assert (
        result.get(
            "FailedInstancesCount",
            0,
        )
        == 0
    )


def test_manual_equivalent_route_to_unavailable_fails():
    with pytest.raises(
        HTTPError,
    ) as exc_info:
        send_series_to_modality(
            "unavailable"
        )

    assert (
        exc_info.value.code
        == 500
    )