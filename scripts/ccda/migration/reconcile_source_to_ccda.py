import json
import xml.etree.ElementTree as ET
from pathlib import Path


SOURCE_PATH = Path(
    "examples/ccda/migration/avery-source.xml"
)

TARGET_PATH = Path(
    "examples/ccda/migration/avery-target-ccda.xml"
)

NS = {
    "cda": "urn:hl7-org:v3",
}


def compare(label, expected, actual):
    return {
        "field": label,
        "expected": expected,
        "actual": actual,
        "status": "PASS" if expected == actual else "FAIL",
    }


def reconcile(source_path=SOURCE_PATH, target_path=TARGET_PATH):
    source_root = ET.parse(source_path).getroot()
    target_root = ET.parse(target_path).getroot()

    results = []

    # Patient
    results.append(
        compare(
            "patient.given",
            source_root.findtext("./Patient/Given"),
            target_root.findtext(
                ".//cda:recordTarget/"
                "cda:patientRole/"
                "cda:patient/"
                "cda:name/"
                "cda:given",
                namespaces=NS,
            ),
        )
    )

    results.append(
        compare(
            "patient.family",
            source_root.findtext("./Patient/Family"),
            target_root.findtext(
                ".//cda:recordTarget/"
                "cda:patientRole/"
                "cda:patient/"
                "cda:name/"
                "cda:family",
                namespaces=NS,
            ),
        )
    )

    source_birth = source_root.findtext("./Patient/BirthDate")

    target_birth = target_root.find(
        ".//cda:recordTarget/"
        "cda:patientRole/"
        "cda:patient/"
        "cda:birthTime",
        NS,
    )

    results.append(
        compare(
            "patient.birth_date",
            source_birth,
            None if target_birth is None else target_birth.attrib.get("value"),
        )
    )

    source_sex = source_root.find("./Patient/AdministrativeSex")
    target_sex = target_root.find(
        ".//cda:recordTarget/"
        "cda:patientRole/"
        "cda:patient/"
        "cda:administrativeGenderCode",
        NS,
    )

    results.append(
        compare(
            "patient.sex.code",
            None if source_sex is None else source_sex.attrib.get("code"),
            None if target_sex is None else target_sex.attrib.get("code"),
        )
    )

    # Medication
    source_meds = source_root.findall("./Medications/Medication")
    target_meds = target_root.findall(
        ".//cda:substanceAdministration",
        NS,
    )

    results.append(
        compare(
            "medication.count",
            len(source_meds),
            len(target_meds),
        )
    )

    if source_meds and target_meds:
        source_med = source_meds[0]
        target_med = target_meds[0]

        target_route = target_med.find("cda:routeCode", NS)
        target_dose = target_med.find("cda:doseQuantity", NS)
        target_code = target_med.find(
            "cda:consumable/"
            "cda:manufacturedProduct/"
            "cda:manufacturedMaterial/"
            "cda:code",
            NS,
        )

        source_route = source_med.find("Route")
        source_dose = source_med.find("Dose")

        results.append(
            compare(
                "medication.display_name",
                source_med.findtext("DisplayName"),
                None if target_code is None else target_code.attrib.get("displayName"),
            )
        )

        results.append(
            compare(
                "medication.code_system_name",
                source_med.findtext("CodeSystemName"),
                None if target_code is None else target_code.attrib.get("codeSystemName"),
            )
        )

        results.append(
            compare(
                "medication.route.code",
                None if source_route is None else source_route.attrib.get("code"),
                None if target_route is None else target_route.attrib.get("code"),
            )
        )

        results.append(
            compare(
                "medication.route.display",
                None if source_route is None else source_route.text,
                None if target_route is None else target_route.attrib.get("displayName"),
            )
        )

        results.append(
            compare(
                "medication.dose.value",
                None if source_dose is None else source_dose.text,
                None if target_dose is None else target_dose.attrib.get("value"),
            )
        )

        results.append(
            compare(
                "medication.dose.unit",
                None if source_dose is None else source_dose.attrib.get("unit"),
                None if target_dose is None else target_dose.attrib.get("unit"),
            )
        )

    # Encounters
    source_encounters = source_root.findall("./Encounters/Encounter")
    target_encounters = target_root.findall(
        ".//cda:encounter",
        NS,
    )

    results.append(
        compare(
            "encounter.count",
            len(source_encounters),
            len(target_encounters),
        )
    )

    for index, source_encounter in enumerate(source_encounters):
        if index >= len(target_encounters):
            break

        target_encounter = target_encounters[index]

        target_code = target_encounter.find("cda:code", NS)
        target_time = target_encounter.find("cda:effectiveTime", NS)

        results.append(
            compare(
                f"encounter.{index + 1}.description",
                source_encounter.findtext("Description"),
                None if target_code is None else target_code.attrib.get("displayName"),
            )
        )

        results.append(
            compare(
                f"encounter.{index + 1}.effective_time",
                source_encounter.findtext("EffectiveTime"),
                None if target_time is None else target_time.attrib.get("value"),
            )
        )

    failed = [item for item in results if item["status"] == "FAIL"]

    return {
        "status": "PASS" if not failed else "QUARANTINE",
        "checks": results,
    }


if __name__ == "__main__":
    result = reconcile()
    print(json.dumps(result, indent=2))
