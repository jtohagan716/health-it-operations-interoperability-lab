from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


CDA_NS = {"cda": "urn:hl7-org:v3"}


def text_or_none(element: ET.Element | None) -> str | None:
    if element is None:
        return None
    return element.text


def inspect_ccda(path: Path) -> None:
    tree = ET.parse(path)
    root = tree.getroot()

    print("C-CDA INSPECTION")
    print("=" * 60)
    print(f"File: {path}")
    print(f"Root element: {root.tag}")
    print()

    given = root.find(
        ".//cda:recordTarget/cda:patientRole/cda:patient/cda:name/cda:given",
        CDA_NS,
    )
    family = root.find(
        ".//cda:recordTarget/cda:patientRole/cda:patient/cda:name/cda:family",
        CDA_NS,
    )
    birth_time = root.find(
        ".//cda:recordTarget/cda:patientRole/cda:patient/cda:birthTime",
        CDA_NS,
    )
    gender = root.find(
        ".//cda:recordTarget/cda:patientRole/cda:patient/cda:administrativeGenderCode",
        CDA_NS,
    )

    print("PATIENT")
    print("-" * 60)
    print(f"Name: {text_or_none(given)} {text_or_none(family)}")
    print(
        "Birth date:",
        birth_time.attrib.get("value") if birth_time is not None else None,
    )
    print(
        "Administrative gender:",
        gender.attrib.get("displayName") if gender is not None else None,
    )
    print()

    medications = root.findall(".//cda:substanceAdministration", CDA_NS)

    print("MEDICATIONS")
    print("-" * 60)
    print(f"Count: {len(medications)}")

    for index, medication in enumerate(medications, start=1):
        code = medication.find(
            "cda:consumable/"
            "cda:manufacturedProduct/"
            "cda:manufacturedMaterial/"
            "cda:code",
            CDA_NS,
        )
        route = medication.find("cda:routeCode", CDA_NS)
        dose = medication.find("cda:doseQuantity", CDA_NS)

        print(f"[{index}]")
        print(
            "  Medication:",
            code.attrib.get("displayName") if code is not None else None,
        )
        print(
            "  Code:",
            code.attrib.get("code") if code is not None else None,
        )
        print(
            "  Code system:",
            code.attrib.get("codeSystemName") if code is not None else None,
        )
        print(
            "  Route:",
            route.attrib.get("displayName") if route is not None else None,
        )
        print(
            "  Route code:",
            route.attrib.get("code") if route is not None else None,
        )
        print(
            "  Dose:",
            (
                f"{dose.attrib.get('value')} {dose.attrib.get('unit')}"
                if dose is not None
                else None
            ),
        )

    print()

    encounters = root.findall(".//cda:encounter", CDA_NS)

    print("ENCOUNTERS")
    print("-" * 60)
    print(f"Count: {len(encounters)}")

    for index, encounter in enumerate(encounters, start=1):
        code = encounter.find("cda:code", CDA_NS)
        effective_time = encounter.find("cda:effectiveTime", CDA_NS)

        print(f"[{index}]")
        print(
            "  Description:",
            code.attrib.get("displayName") if code is not None else None,
        )
        print(
            "  Effective time:",
            (
                effective_time.attrib.get("value")
                if effective_time is not None
                else None
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect selected structured data from a C-CDA document."
    )
    parser.add_argument(
        "ccda_file",
        type=Path,
        help="Path to the C-CDA XML file",
    )
    args = parser.parse_args()

    inspect_ccda(args.ccda_file)


if __name__ == "__main__":
    main()