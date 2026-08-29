from pathlib import Path
import argparse
import xml.etree.ElementTree as ET


NS = {
    "cda": "urn:hl7-org:v3",
}


MEDICATION_SECTION_LOINC = "10160-0"


def find_medication_section(root: ET.Element) -> ET.Element | None:
    sections = root.findall(
        ".//cda:structuredBody/cda:component/cda:section",
        NS,
    )

    for section in sections:
        code = section.find("cda:code", NS)

        if code is not None and code.attrib.get("code") == MEDICATION_SECTION_LOINC:
            return section

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect medication entry templates in a C-CDA document."
    )

    parser.add_argument(
        "ccda_file",
        type=Path,
    )

    args = parser.parse_args()

    root = ET.parse(args.ccda_file).getroot()

    section = find_medication_section(root)

    if section is None:
        raise SystemExit("Medication section not found")

    activities = section.findall(
        ".//cda:substanceAdministration",
        NS,
    )

    print("MEDICATION ENTRIES")
    print("=" * 70)
    print(f"Count: {len(activities)}")
    print()

    for index, activity in enumerate(activities, start=1):
        print(f"[{index}]")

        template_ids = activity.findall("cda:templateId", NS)

        print("  Template IDs:")

        for template_id in template_ids:
            print(
                "   ",
                template_id.attrib.get("root"),
                template_id.attrib.get("extension"),
            )

        medication_code = activity.find(
            "cda:consumable/"
            "cda:manufacturedProduct/"
            "cda:manufacturedMaterial/"
            "cda:code",
            NS,
        )

        if medication_code is not None:
            print(
                "  Medication:",
                medication_code.attrib.get("displayName"),
            )
            print(
                "  Code:",
                medication_code.attrib.get("code"),
            )
            print(
                "  Code system:",
                medication_code.attrib.get("codeSystemName"),
            )

        route = activity.find("cda:routeCode", NS)

        if route is not None:
            print(
                "  Route:",
                route.attrib.get("displayName"),
                route.attrib.get("code"),
            )

        dose = activity.find("cda:doseQuantity", NS)

        if dose is not None:
            print(
                "  Dose:",
                dose.attrib.get("value"),
                dose.attrib.get("unit"),
            )

        print()


if __name__ == "__main__":
    main()