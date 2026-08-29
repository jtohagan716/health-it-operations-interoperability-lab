from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


NS = {
    "cda": "urn:hl7-org:v3",
}


def find_section_by_loinc(
    root: ET.Element,
    loinc_code: str,
) -> ET.Element | None:
    sections = root.findall(
        ".//cda:structuredBody/cda:component/cda:section",
        NS,
    )

    for section in sections:
        code = section.find("cda:code", NS)

        if code is None:
            continue

        if (
            code.attrib.get("code") == loinc_code
            and code.attrib.get("codeSystemName") == "LOINC"
        ):
            return section

    return None


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract a C-CDA section by LOINC code."
    )

    parser.add_argument(
        "ccda_file",
        type=Path,
        help="Path to the C-CDA document.",
    )

    parser.add_argument(
        "loinc_code",
        help="LOINC section code, for example 10160-0.",
    )

    args = parser.parse_args()

    root = ET.parse(args.ccda_file).getroot()

    section = find_section_by_loinc(
        root,
        args.loinc_code,
    )

    if section is None:
        raise SystemExit(
            f"No C-CDA section found for LOINC {args.loinc_code}"
        )

    title = section.find("cda:title", NS)
    code = section.find("cda:code", NS)

    print("SECTION FOUND")
    print("=" * 60)
    print(
        "Title:",
        title.text if title is not None else None,
    )
    print(
        "LOINC:",
        code.attrib.get("code") if code is not None else None,
    )

    template_ids = section.findall("cda:templateId", NS)

    print("Template IDs:")

    for template_id in template_ids:
        print(
            " ",
            template_id.attrib.get("root"),
            template_id.attrib.get("extension"),
        )

def section_has_template_id(
    section: ET.Element,
    expected_root: str,
) -> bool:
    template_ids = section.findall("cda:templateId", NS)

    return any(
        template_id.attrib.get("root") == expected_root
        for template_id in template_ids
    )

def find_section_by_loinc_and_template(
    root: ET.Element,
    loinc_code: str,
    template_root: str,
    template_extension: str | None = None,
) -> ET.Element | None:
    sections = root.findall(
        ".//cda:structuredBody/cda:component/cda:section",
        NS,
    )

    for section in sections:
        code = section.find("cda:code", NS)

        if code is None:
            continue

        if code.attrib.get("code") != loinc_code:
            continue

        if not section_has_template(
            section,
            template_root,
            template_extension,
        ):
            continue

        return section

    return None

def section_has_template(
    section: ET.Element,
    expected_root: str,
    expected_extension: str | None = None,
) -> bool:
    template_ids = section.findall("cda:templateId", NS)

    for template_id in template_ids:
        root_value = template_id.attrib.get("root")
        extension_value = template_id.attrib.get("extension")

        if root_value != expected_root:
            continue

        if expected_extension is None:
            return True

        if extension_value == expected_extension:
            return True

    return False
if __name__ == "__main__":
    main()