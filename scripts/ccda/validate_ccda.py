from __future__ import annotations

import argparse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


NS = {
    "cda": "urn:hl7-org:v3",
}


@dataclass
class Finding:
    name: str
    passed: bool
    detail: str


def validate_ccda(path: Path) -> list[Finding]:
    findings: list[Finding] = []

    try:
        tree = ET.parse(path)
        root = tree.getroot()

        findings.append(
            Finding(
                name="XML well-formed",
                passed=True,
                detail="Document parsed successfully.",
            )
        )
    except ET.ParseError as exc:
        return [
            Finding(
                name="XML well-formed",
                passed=False,
                detail=str(exc),
            )
        ]

    expected_root = "{urn:hl7-org:v3}ClinicalDocument"

    findings.append(
        Finding(
            name="CDA ClinicalDocument root",
            passed=root.tag == expected_root,
            detail=f"Found root element: {root.tag}",
        )
    )

    patient = root.find(
        ".//cda:recordTarget/"
        "cda:patientRole/"
        "cda:patient",
        NS,
    )

    findings.append(
        Finding(
            name="Patient present",
            passed=patient is not None,
            detail=(
                "recordTarget/patientRole/patient found."
                if patient is not None
                else "Patient element not found."
            ),
        )
    )

    medication = root.find(
        ".//cda:substanceAdministration",
        NS,
    )

    findings.append(
        Finding(
            name="Medication entry present",
            passed=medication is not None,
            detail=(
                "Medication substanceAdministration found."
                if medication is not None
                else "Medication substanceAdministration not found."
            ),
        )
    )

    if medication is None:
        return findings

    medication_code = medication.find(
        "cda:consumable/"
        "cda:manufacturedProduct/"
        "cda:manufacturedMaterial/"
        "cda:code",
        NS,
    )

    rxnorm_ok = (
        medication_code is not None
        and medication_code.attrib.get("codeSystemName") == "RXNORM"
    )

    findings.append(
        Finding(
            name="Medication coding system",
            passed=rxnorm_ok,
            detail=(
                f"Found code system: "
                f"{medication_code.attrib.get('codeSystemName')}"
                if medication_code is not None
                else "Medication code element not found."
            ),
        )
    )

    route = medication.find(
        "cda:routeCode",
        NS,
    )

    expected_route_code = "C38288"

    actual_route_code = (
        route.attrib.get("code")
        if route is not None
        else None
    )

    findings.append(
        Finding(
            name="Medication route",
            passed=actual_route_code == expected_route_code,
            detail=(
                f"Expected {expected_route_code}, "
                f"found {actual_route_code}"
            ),
        )
    )

    dose = medication.find(
        "cda:doseQuantity",
        NS,
    )

    expected_dose_value = "10"
    expected_dose_unit = "mg"

    dose_ok = (
        dose is not None
        and dose.attrib.get("value") == expected_dose_value
        and dose.attrib.get("unit") == expected_dose_unit
    )

    findings.append(
        Finding(
            name="Medication dose",
            passed=dose_ok,
            detail=(
                f"Expected {expected_dose_value} {expected_dose_unit}, "
                f"found "
                f"{dose.attrib.get('value') if dose is not None else None} "
                f"{dose.attrib.get('unit') if dose is not None else None}"
            ),
        )
    )

    return findings


def print_findings(findings: list[Finding]) -> None:
    for finding in findings:
        status = "PASS" if finding.passed else "FAIL"
        print(f"{status:<4}  {finding.name}")
        print(f"      {finding.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate selected structural and semantic C-CDA contracts."
    )

    parser.add_argument(
        "ccda_file",
        type=Path,
        help="Path to the C-CDA XML document.",
    )

    args = parser.parse_args()

    findings = validate_ccda(args.ccda_file)

    print_findings(findings)

    return 0 if all(finding.passed for finding in findings) else 1


if __name__ == "__main__":
    raise SystemExit(main())