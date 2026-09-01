<?php

declare(strict_types=1);

/*
 * Local OpenEMR ORU ingestion harness.
 *
 * This file is rendered and streamed to the OpenEMR container by
 * openemr_oru_ingest.py. It deliberately calls only the module's local
 * parser. It never calls ConnectorApi::sendAck() or another DORN API.
 */

$ignoreAuth = true;
$_GET['site'] = 'default';

error_reporting(E_ALL & ~E_DEPRECATED);
ini_set('display_errors', '0');

require_once '/var/www/localhost/htdocs/openemr/interface/globals.php';

$module = '/var/www/localhost/htdocs/openemr/interface/modules/' .
    'custom_modules/oe-module-dorn';
require_once $module . '/src/ReceiveHl7Results.php';

$orderId = __OPENEMR_ORDER_ID__;
$patientId = __OPENEMR_PATIENT_ID__;
$encounterId = __OPENEMR_ENCOUNTER_ID__;
$labId = __OPENEMR_LAB_ID__;
$commit = __OPENEMR_COMMIT__;
$allowExistingResults = __OPENEMR_ALLOW_EXISTING__;
$procedureCode = base64_decode('__OPENEMR_PROCEDURE_CODE_BASE64__');
$fillerId = base64_decode('__OPENEMR_FILLER_ID_BASE64__');
$hl7 = base64_decode('__OPENEMR_HL7_BASE64__');

function respond(array $payload, int $exitCode = 0): never
{
    echo json_encode(
        $payload,
        JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES
    ) . PHP_EOL;
    exit($exitCode);
}

function countReports(int $orderId): int
{
    $row = sqlQuery(
        'SELECT COUNT(*) AS count_value FROM procedure_report ' .
        'WHERE procedure_order_id = ?',
        [$orderId]
    );
    return (int)($row['count_value'] ?? 0);
}

function countResults(int $orderId): int
{
    $row = sqlQuery(
        'SELECT COUNT(*) AS count_value ' .
        'FROM procedure_result AS result ' .
        'INNER JOIN procedure_report AS report ON ' .
        'report.procedure_report_id = result.procedure_report_id ' .
        'WHERE report.procedure_order_id = ?',
        [$orderId]
    );
    return (int)($row['count_value'] ?? 0);
}

if ($hl7 === false || !str_starts_with($hl7, 'MSH')) {
    respond([
        'status' => 'PRECONDITION_FAILED',
        'message' => 'Decoded payload is not an HL7 message.',
    ], 2);
}

$order = sqlQuery(
    'SELECT procedure_order_id, patient_id, encounter_id, lab_id, ' .
    'control_id, order_status, date_transmitted ' .
    'FROM procedure_order WHERE procedure_order_id = ?',
    [$orderId]
);

if (empty($order)) {
    respond([
        'status' => 'PRECONDITION_FAILED',
        'message' => "OpenEMR order $orderId was not found.",
    ], 2);
}

$expected = [
    'patient_id' => $patientId,
    'encounter_id' => $encounterId,
    'lab_id' => $labId,
];

foreach ($expected as $field => $expectedValue) {
    if ((int)$order[$field] !== $expectedValue) {
        respond([
            'status' => 'PRECONDITION_FAILED',
            'message' => "$field did not match Order ID $orderId.",
            'expected' => $expectedValue,
            'observed' => (int)$order[$field],
        ], 2);
    }
}

$orderCode = sqlQuery(
    'SELECT procedure_order_seq, procedure_code, procedure_name ' .
    'FROM procedure_order_code WHERE procedure_order_id = ? ' .
    'AND procedure_code = ? ORDER BY procedure_order_seq LIMIT 1',
    [$orderId, $procedureCode]
);

if (empty($orderCode)) {
    respond([
        'status' => 'PRECONDITION_FAILED',
        'message' => "Procedure $procedureCode is not present on Order ID $orderId.",
    ], 2);
}

$beforeReports = countReports($orderId);
$beforeResults = countResults($orderId);
$beforeControlId = (string)($order['control_id'] ?? '');

if ($commit && $beforeReports > 0 && !$allowExistingResults) {
    $status = $beforeControlId === $fillerId
        ? 'REPLAY_BLOCKED'
        : 'EXISTING_RESULTS_BLOCKED';
    respond([
        'status' => $status,
        'message' => 'Order already has persisted results. ' .
            'Use an explicit lifecycle/update workflow instead of replaying.',
        'report_count' => $beforeReports,
        'result_count' => $beforeResults,
        'control_id' => $beforeControlId,
    ], 3);
}

$matchRequirements = [];
$GLOBALS['lab_npi'] = 'DORN';

$receiver = new \OpenEMR\Modules\Dorn\ReceiveHl7Results();
$method = new ReflectionMethod($receiver, 'receiveHl7Results');

$arguments = [
    &$hl7,
    &$matchRequirements,
    $labId,
    'B',
    !$commit,
    $patientId,
];

$parserResult = $method->invokeArgs($receiver, $arguments);

if (!empty($parserResult['mssgs']) ||
    !empty($parserResult['fatal']) ||
    !empty($parserResult['needmatch'])) {
    respond([
        'status' => 'PARSER_REJECTED',
        'parser' => $parserResult,
        'match_requirements' => $matchRequirements,
    ], 4);
}

$afterOrder = sqlQuery(
    'SELECT control_id, order_status, date_transmitted ' .
    'FROM procedure_order WHERE procedure_order_id = ?',
    [$orderId]
);
$afterReports = countReports($orderId);
$afterResults = countResults($orderId);
$afterControlId = (string)($afterOrder['control_id'] ?? '');

if (!$commit) {
    if ($beforeReports !== $afterReports ||
        $beforeResults !== $afterResults ||
        $beforeControlId !== $afterControlId) {
        respond([
            'status' => 'DRY_RUN_MUTATED_STATE',
            'before' => [
                'reports' => $beforeReports,
                'results' => $beforeResults,
                'control_id' => $beforeControlId,
            ],
            'after' => [
                'reports' => $afterReports,
                'results' => $afterResults,
                'control_id' => $afterControlId,
            ],
        ], 5);
    }

    respond([
        'status' => 'DRY_RUN_PASSED',
        'order_id' => $orderId,
        'procedure_code' => $procedureCode,
        'report_count' => $afterReports,
        'result_count' => $afterResults,
        'control_id' => $afterControlId,
        'parser' => $parserResult,
    ]);
}

if ($afterReports !== $beforeReports + 1 ||
    $afterResults < $beforeResults + 1) {
    respond([
        'status' => 'COMMIT_POSTCONDITION_FAILED',
        'before' => [
            'reports' => $beforeReports,
            'results' => $beforeResults,
        ],
        'after' => [
            'reports' => $afterReports,
            'results' => $afterResults,
        ],
    ], 6);
}

if ($beforeReports === 0 && $afterControlId !== $fillerId) {
    respond([
        'status' => 'COMMIT_POSTCONDITION_FAILED',
        'message' => 'The committed filler ID was not stored as control_id.',
        'expected' => $fillerId,
        'observed' => $afterControlId,
    ], 6);
}

$persisted = sqlQuery(
    'SELECT report.procedure_report_id, report.report_status, ' .
    'report.review_status, result.procedure_result_id, ' .
    'result.result_code, result.result_text, result.result, ' .
    'result.units, result.range, result.abnormal, ' .
    'result.result_status ' .
    'FROM procedure_report AS report ' .
    'INNER JOIN procedure_result AS result ON ' .
    'result.procedure_report_id = report.procedure_report_id ' .
    'WHERE report.procedure_order_id = ? ' .
    'ORDER BY report.procedure_report_id DESC, ' .
    'result.procedure_result_id DESC LIMIT 1',
    [$orderId]
);

respond([
    'status' => 'COMMIT_PASSED',
    'order_id' => $orderId,
    'control_id' => $afterControlId,
    'order_status' => $afterOrder['order_status'],
    'date_transmitted' => $afterOrder['date_transmitted'],
    'report_count' => $afterReports,
    'result_count' => $afterResults,
    'persisted' => $persisted,
    'parser' => $parserResult,
]);

