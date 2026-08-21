import json
from urllib.request import urlopen


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


def main() -> None:
    print()
    print("PACS DICOM MODALITY INVENTORY")
    print("-----------------------------")

    modalities = get_json(
        "/modalities"
    )

    if not modalities:
        print(
            "No remote modalities configured."
        )
        print("OVERALL: FAIL")
        raise SystemExit(1)

    print(
        f"Configured modalities: "
        f"{len(modalities)}"
    )
    print()

    for modality_name in modalities:
        configuration = (
            get_modality_configuration(
                modality_name
            )
        )

        print(
            f"Name:        {modality_name}"
        )
        print(
            f"AE Title:    "
            f"{configuration.get('AET', '')}"
        )
        print(
            f"Host:        "
            f"{configuration.get('Host', '')}"
        )
        print(
            f"Port:        "
            f"{configuration.get('Port', '')}"
        )
        print(
            f"Allow Echo:  "
            f"{configuration.get('AllowEcho', '')}"
        )
        print(
            f"Allow Find:  "
            f"{configuration.get('AllowFind', '')}"
        )
        print(
            f"Allow Move:  "
            f"{configuration.get('AllowMove', '')}"
        )
        print(
            f"Allow Store: "
            f"{configuration.get('AllowStore', '')}"
        )
        print(
            f"DICOM TLS:   "
            f"{configuration.get('UseDicomTls', '')}"
        )
        print()

    print("OVERALL: PASS")


if __name__ == "__main__":
    main()