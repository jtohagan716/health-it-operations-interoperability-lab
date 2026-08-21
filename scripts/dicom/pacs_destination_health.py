import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ORTHANC_URL = "http://127.0.0.1:8042"


def get_json(path: str):
    with urlopen(
        f"{ORTHANC_URL}{path}",
        timeout=5,
    ) as response:
        return json.load(response)


def get_modality_configuration(
    modality_name: str,
) -> dict:
    return get_json(
        f"/modalities/"
        f"{modality_name}/configuration"
    )


def probe_modality_echo(
    modality_name: str,
) -> dict:
    request = Request(
        f"{ORTHANC_URL}/modalities/"
        f"{modality_name}/echo",
        method="POST",
    )

    try:
        with urlopen(
            request,
            timeout=10,
        ) as response:
            return {
                "healthy": (
                    response.status == 200
                ),
                "http_status": (
                    response.status
                ),
                "error": None,
            }

    except HTTPError as exc:
        return {
            "healthy": False,
            "http_status": exc.code,
            "error": str(exc),
        }

    except URLError as exc:
        return {
            "healthy": False,
            "http_status": None,
            "error": str(exc),
        }


def build_destination_health_report() -> dict:
    modalities = get_json(
        "/modalities"
    )

    results = []

    for modality_name in modalities:
        configuration = (
            get_modality_configuration(
                modality_name
            )
        )

        echo_result = (
            probe_modality_echo(
                modality_name
            )
        )

        results.append(
            {
                "name": modality_name,
                "ae_title": (
                    configuration.get(
                        "AET",
                        "",
                    )
                ),
                "host": (
                    configuration.get(
                        "Host",
                        "",
                    )
                ),
                "port": (
                    configuration.get(
                        "Port",
                        0,
                    )
                ),
                "allow_echo": (
                    configuration.get(
                        "AllowEcho",
                        False,
                    )
                ),
                "healthy": (
                    echo_result[
                        "healthy"
                    ]
                ),
                "http_status": (
                    echo_result[
                        "http_status"
                    ]
                ),
                "error": (
                    echo_result[
                        "error"
                    ]
                ),
            }
        )

    healthy_count = sum(
        1
        for result in results
        if result["healthy"]
    )

    unhealthy_count = (
        len(results)
        - healthy_count
    )

    return {
        "destinations": results,
        "healthy_count": healthy_count,
        "unhealthy_count": unhealthy_count,
        "overall": (
            "HEALTHY"
            if unhealthy_count == 0
            else "DEGRADED"
        ),
    }


def main() -> None:
    report = (
        build_destination_health_report()
    )

    print()
    print("PACS DESTINATION HEALTH")
    print("-----------------------")

    for destination in report[
        "destinations"
    ]:
        status = (
            "PASS"
            if destination["healthy"]
            else "FAIL"
        )

        print()
        print(
            f"Name:      "
            f"{destination['name']}"
        )
        print(
            f"AE Title:  "
            f"{destination['ae_title']}"
        )
        print(
            f"Host:      "
            f"{destination['host']}"
        )
        print(
            f"Port:      "
            f"{destination['port']}"
        )
        print(
            f"C-ECHO:    "
            f"{status}"
        )

        if (
            destination[
                "http_status"
            ]
            is not None
        ):
            print(
                f"HTTP:      "
                f"{destination['http_status']}"
            )

        if destination["error"]:
            print(
                f"Error:     "
                f"{destination['error']}"
            )

    print()
    print(
        f"Healthy:   "
        f"{report['healthy_count']}"
    )
    print(
        f"Unhealthy: "
        f"{report['unhealthy_count']}"
    )
    print(
        f"OVERALL:   "
        f"{report['overall']}"
    )


if __name__ == "__main__":
    main()