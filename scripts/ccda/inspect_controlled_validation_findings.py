from lxml import etree

path = r"examples/ccda/avery-testpatient-complete-demographics.xml"

parser = etree.XMLParser(remove_blank_text=False)
tree = etree.parse(path, parser)

ns = {
    "cda": "urn:hl7-org:v3"
}

targets = {
    "PATIENT ADDRESS":
        "//cda:recordTarget/cda:patientRole/cda:addr",

    "PATIENT TELECOM":
        "//cda:recordTarget/cda:patientRole/cda:telecom",

    "AUTHOR NAME":
        "//cda:author/cda:assignedAuthor/cda:assignedPerson/cda:name",

    "AUTHOR TELECOM":
        "//cda:author/cda:assignedAuthor/cda:telecom",

    "RECIPIENT NAME":
        "//cda:informationRecipient/cda:intendedRecipient/"
        "cda:informationRecipient/cda:name",
}

for label, xpath in targets.items():
    print("=" * 72)
    print(label)
    print("=" * 72)

    nodes = tree.xpath(xpath, namespaces=ns)

    if not nodes:
        print("<NOT PRESENT>")
        print()
        continue

    for node in nodes:
        print(
            etree.tostring(
                node,
                pretty_print=True,
                encoding="unicode",
            )
        )
