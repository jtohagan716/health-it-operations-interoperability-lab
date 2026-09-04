"""Derive the dedicated lab OML channel from the audited ORM channel shell."""

import argparse
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


CHANNEL_ID = "2dbfc428-29fd-4e22-a97c-461588c52a21"

VALIDATOR = r'''/* LAB_OML_O21_IN source validation */
var failures = [];
function safeValue(node) {
    try { return node == null ? "" : String(node.toString()).trim(); }
    catch (e) { return ""; }
}
var messageCode = safeValue(msg['MSH']['MSH.9']['MSH.9.1']);
var triggerEvent = safeValue(msg['MSH']['MSH.9']['MSH.9.2']);
var structure = safeValue(msg['MSH']['MSH.9']['MSH.9.3']);
var receivingApplication = safeValue(msg['MSH']['MSH.5']['MSH.5.1']);
var receivingFacility = safeValue(msg['MSH']['MSH.6']['MSH.6.1']);
var patientId = safeValue(msg['PID']['PID.3']['PID.3.1']);
var patientFamily = safeValue(msg['PID']['PID.5']['PID.5.1']);
var patientGiven = safeValue(msg['PID']['PID.5']['PID.5.2']);
var patientDob = safeValue(msg['PID']['PID.7']['PID.7.1']);
var patientSex = safeValue(msg['PID']['PID.8']['PID.8.1']);
var assigningAuthority = safeValue(msg['PID']['PID.3']['PID.3.4']);
var identifierType = safeValue(msg['PID']['PID.3']['PID.3.5']);
var visitNumber = safeValue(msg['PV1']['PV1.19']['PV1.19.1']);
var orderControl = safeValue(msg['ORC']['ORC.1']['ORC.1.1']);
var orcPlacer = safeValue(msg['ORC']['ORC.2']['ORC.2.1']);
var obrPlacer = safeValue(msg['OBR']['OBR.2']['OBR.2.1']);
var serviceCode = safeValue(msg['OBR']['OBR.4']['OBR.4.1']);
var serviceText = safeValue(msg['OBR']['OBR.4']['OBR.4.2']);
var codingSystem = safeValue(msg['OBR']['OBR.4']['OBR.4.3']);

if (messageCode != 'OML') failures.push('MSH-9.1 must be OML');
if (triggerEvent != 'O21') failures.push('MSH-9.2 must be O21');
if (structure != 'OML_O21') failures.push('MSH-9.3 must be OML_O21');
if (receivingApplication != 'SYNLIS') failures.push('MSH-5 must be SYNLIS');
if (receivingFacility != 'LAB') failures.push('MSH-6 must be LAB');
if (!patientId) failures.push('PID-3 patient identifier is required');
if (!patientFamily) failures.push('PID-5.1 family name is required');
if (!patientGiven) failures.push('PID-5.2 given name is required');
if (!/^\d{8}$/.test(patientDob)) failures.push('PID-7 must be YYYYMMDD');
if (!/^[FMU]$/.test(patientSex)) failures.push('PID-8 must be F, M, or U');
if (assigningAuthority != 'INTEROPLAB') failures.push('PID-3.4 must be INTEROPLAB');
if (identifierType != 'MR') failures.push('PID-3.5 must be MR');
if (!visitNumber) failures.push('PV1-19 visit number is required');
if (orderControl != 'NW') failures.push('ORC-1 must be NW');
if (!orcPlacer) failures.push('ORC-2 placer order number is required');
if (orcPlacer != obrPlacer) failures.push('ORC-2 and OBR-2 must match');
if (!serviceCode) failures.push('OBR-4.1 service code is required');
if (!serviceText) failures.push('OBR-4.2 service text is required');
if (codingSystem != 'LN') failures.push('OBR-4.3 must be LN');

channelMap.put('oml_patient_identifier', patientId);
channelMap.put('oml_patient_family_name', patientFamily);
channelMap.put('oml_patient_given_name', patientGiven);
channelMap.put('oml_patient_date_of_birth', patientDob);
channelMap.put('oml_patient_administrative_sex', patientSex);
channelMap.put('oml_visit_number', visitNumber);
channelMap.put('oml_order_control', orderControl);
channelMap.put('oml_placer_order_number', orcPlacer);
channelMap.put('oml_service_code', serviceCode);
channelMap.put('oml_service_text', serviceText);
channelMap.put('oml_service_coding_system', codingSystem);
channelMap.put('validation_failure_reason', failures.join('; '));
channelMap.put('validation_failure_category', 'INTERFACE_CONTRACT');
channelMap.put('validation_status', failures.length == 0 ? 'PASS' : 'FAIL');
'''

PERSISTENCE = r'''/* Persist accepted OML into synthetic LIS-owned state. */
var dbConn = null;
try {
    if (String(channelMap.get('validation_status')) != 'PASS') return;
    var outcome = String(channelMap.get('audit_attempt_outcome'));
    if (outcome == 'CONFLICTING_REUSE') return;
    if (outcome != 'FIRST_DELIVERY' && outcome != 'EXACT_REPLAY') {
        throw new Error('Unexpected OML transaction classification: ' + outcome);
    }
    var dbUrl = java.lang.System.getenv('INTEROP_DB_URL');
    var dbUser = java.lang.System.getenv('INTEROP_DB_USER');
    var dbPassword = java.lang.System.getenv('INTEROP_DB_PASSWORD');
    if (dbUrl == null || dbUser == null || dbPassword == null) {
        throw new Error('Required INTEROP_DB_* configuration is missing.');
    }
    dbConn = DatabaseConnectionFactory.createDatabaseConnection(
        'org.postgresql.Driver', dbUrl, dbUser, dbPassword
    );
    var sql =
        'SELECT lis_order_id, filler_order_number, created ' +
        'FROM lis.accept_order(CAST(? AS BIGINT), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)';
    var p = new java.util.ArrayList();
    p.add(String(channelMap.get('audit_logical_transaction_id')));
    p.add(channelMap.get('audit_message_control_id'));
    p.add(channelMap.get('oml_patient_identifier'));
    p.add(channelMap.get('oml_patient_family_name'));
    p.add(channelMap.get('oml_patient_given_name'));
    p.add(channelMap.get('oml_patient_date_of_birth'));
    p.add(channelMap.get('oml_patient_administrative_sex'));
    p.add(channelMap.get('oml_visit_number'));
    p.add(channelMap.get('oml_placer_order_number'));
    p.add(channelMap.get('oml_service_code'));
    p.add(channelMap.get('oml_service_text'));
    p.add(channelMap.get('oml_service_coding_system'));
    p.add(channelMap.get('oml_order_control'));
    p.add(String(connectorMessage.getRawData()));
    var result = dbConn.executeCachedQuery(sql, p);
    if (!result.next()) throw new Error('lis.accept_order returned no row.');
    channelMap.put('lis_order_id', result.getString('lis_order_id'));
    channelMap.put('lis_filler_order_number', result.getString('filler_order_number'));
    channelMap.put('lis_order_created', result.getString('created'));
} finally {
    if (dbConn != null) dbConn.close();
}
'''


def local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def child(element: ET.Element, name: str):
    return next((item for item in element if local_name(item) == name), None)


def build(source: Path, destination: Path) -> None:
    tree = ET.parse(source)
    root = tree.getroot()
    direct_id = child(root, "id")
    direct_name = child(root, "name")
    if direct_id is None or direct_name is None:
        raise ValueError("Input does not look like a Mirth channel export.")
    direct_id.text = CHANNEL_ID
    direct_name.text = "LAB_OML_O21_IN"

    for element in root.iter():
        if local_name(element) == "port" and element.text == "6663":
            element.text = "6664"
        if local_name(element) == "script" and element.text:
            if "ORM_O01_IN interface contract validation" in element.text:
                element.text = VALIDATOR
        if local_name(element) == "connector":
            name = child(element, "name")
            if name is not None and name.text == "Persist ORM Order":
                name.text = "Persist Synthetic LIS Order"
                query = next(
                    (node for node in element.iter() if local_name(node) == "query"),
                    None,
                )
                if query is None:
                    raise ValueError("ORM persistence connector has no query.")
                query.text = PERSISTENCE

    rendered = ET.tostring(root, encoding="unicode")
    rendered = rendered.replace("ORM_O01_IN", "LAB_OML_O21_IN")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + rendered,
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.output)


if __name__ == "__main__":
    main()

