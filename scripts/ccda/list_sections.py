from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "cda": "urn:hl7-org:v3",
}


def list_sections(path: Path) -> None:
    root = ET.parse(path).getroot()

    sections = root.findall(
        ".//cda:structuredBody/cda:component/cda:section",
        NS,
    )

    print("C-CDA SECTIONS")
    print("=" * 80)

    for index, section in enumerate(sections, start=1):
        title = section.find("cda:title", NS)
        code = section.find("cda:code", NS)
        template_ids = section.findall("cda:templateId", NS)

        print(f"[{index}]")

        print(
            "  Title:",
            title.text if title is not None else None,
        )

        if code is not None:
            print(
                "  Code:",
                code.attrib.get("code"),
            )
            print(
                "  Display name:",
                code.attrib.get("displayName"),
            )
            print(
                "  Code system:",
                code.attrib.get("codeSystemName"),
            )
        else:
            print("  Code: None")

        print("  Template IDs:")

        for template_id in template_ids:
            root_value = template_id.attrib.get("root")
            extension = template_id.attrib.get("extension")

            if extension:
                print(f"    {root_value} | {extension}")
            else:
                print(f"    {root_value}")

        print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List C-CDA sections and their semantic identifiers."
    )

    parser.add_argument(
        "ccda_file",
        type=Path,
        help="Path to a C-CDA XML document.",
    )

    args = parser.parse_args()

    list_sections(args.ccda_file)


if __name__ == "__main__":
    main()