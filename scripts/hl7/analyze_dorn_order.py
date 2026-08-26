from __future__ import annotations

from pathlib import Path


def load_segments(path: Path | str) -> list[str]:
    text = Path(path).read_text(
        encoding="utf-8-sig"
    )

    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def get_field(
    segment: str,
    field_number: int,
) -> str:
    fields = segment.split("|")

    if field_number >= len(fields):
        return ""

    return fields[field_number]


def get_component(
    field: str,
    component_number: int,
) -> str:
    components = field.split("^")
    index = component_number - 1

    if index >= len(components):
        return ""

    return components[index]


def analyze_dorn_order(
    fixture_path: Path | str,
) -> dict:
    """
    Analyze OBR-to-DG1 diagnosis associations in a DORN
    OML^O21 laboratory order.

    Each DG1 is associated with the most recently encountered
    OBR, preserving the actual message grouping emitted by
    OpenEMR.
    """

    segments = load_segments(fixture_path)

    order_groups: list[dict] = []
    current_group: dict | None = None

    for segment in segments:
        if segment.startswith("OBR|"):
            obr_4 = get_field(segment, 4)

            current_group = {
                "obr": segment,
                "procedure_code": get_component(
                    obr_4,
                    1,
                ),
                "procedure_text": get_component(
                    obr_4,
                    2,
                ),
                "diagnoses": [],
            }

            order_groups.append(
                current_group
            )

        elif segment.startswith("DG1|"):
            if current_group is None:
                raise ValueError(
                    "DG1 encountered before an OBR."
                )

            dg1_3 = get_field(segment, 3)

            current_group["diagnoses"].append(
                {
                    "segment": segment,
                    "set_id": get_field(
                        segment,
                        1,
                    ),
                    "code": get_component(
                        dg1_3,
                        1,
                    ),
                    "description": get_component(
                        dg1_3,
                        2,
                    ),
                    "coding_system": get_component(
                        dg1_3,
                        3,
                    ),
                    "diagnosis_type": get_field(
                        segment,
                        6,
                    ),
                }
            )

    return {
        "fixture": str(fixture_path),
        "order_groups": order_groups,
    }
