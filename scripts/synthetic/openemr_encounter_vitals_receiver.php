<?php

declare(strict_types=1);

use OpenEMR\Common\Forms\FormVitals;
use OpenEMR\Common\Session\SessionWrapperFactory;
use OpenEMR\Common\Uuid\UuidRegistry;
use OpenEMR\Services\EncounterService;

$ignoreAuth = true;
$_GET['site'] = 'default';
$_SERVER['HTTP_HOST'] = 'localhost';
error_reporting(E_ALL & ~E_DEPRECATED);
ini_set('display_errors', '0');

require_once '/var/www/localhost/htdocs/openemr/interface/globals.php';
require_once '/var/www/localhost/htdocs/openemr/library/sql.inc.php';

$payload = json_decode(base64_decode('__SYNTHETIC_PAYLOAD_BASE64__'), true, 512, JSON_THROW_ON_ERROR);
$commit = __SYNTHETIC_COMMIT__;

function respond(array $body, int $code = 0): never
{
    echo json_encode($body, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . PHP_EOL;
    exit($code);
}

function fail(string $message, array $context = []): never
{
    throw new RuntimeException($message . (empty($context) ? '' : ': ' . json_encode($context)));
}

function exactRow(string $sql, array $bind, string $label): array
{
    $statement = sqlStatement($sql, $bind);
    $rows = [];
    while ($row = sqlFetchArray($statement)) {
        $rows[] = $row;
    }
    if (count($rows) !== 1) {
        fail("Expected exactly one {$label}", ['count' => count($rows)]);
    }
    return $rows[0];
}

function expectedFor(array $profile, array $record, array $patient): array
{
    $cohort = $patient['cohort'];
    $template = $profile['cohort_defaults'][$cohort] ?? null;
    if (!is_array($template)) {
        fail('No vitals template for patient cohort', ['cohort' => $cohort, 'mrn' => $record['mrn']]);
    }
    $bmi = round(((float)$template['weight'] * 703) / (((float)$template['height']) ** 2), 2);
    return ['cohort' => $cohort, 'template' => $template, 'bmi' => $bmi];
}

function verifyRecord(array $record, array $patient, array $expected, ?array $createdIds = null): array
{
    $encounter = exactRow(
        'SELECT id, encounter, HEX(uuid) AS uuid_hex, pid, provider_id, facility_id, reason, pc_catid, class_code, external_id ' .
        'FROM form_encounter WHERE external_id = ?',
        [$record['encounter_external_id']],
        'encounter'
    );
    if ((int)$encounter['pid'] !== (int)$patient['pid'] ||
        (int)$encounter['provider_id'] !== (int)$patient['provider_id'] ||
        (int)$encounter['facility_id'] !== (int)$patient['facility_id'] ||
        (int)$encounter['pc_catid'] !== 5 || $encounter['class_code'] !== 'AMB' ||
        $encounter['reason'] !== $expected['template']['reason']) {
        fail('Encounter postcondition mismatch', ['external_id' => $record['encounter_external_id']]);
    }
    $encounterForm = exactRow(
        "SELECT id FROM forms WHERE formdir='newpatient' AND form_id=? AND pid=? AND encounter=? AND deleted=0",
        [$encounter['id'], $patient['pid'], $encounter['encounter']],
        'encounter form registration'
    );
    $vitals = exactRow(
        "SELECT v.id, HEX(v.uuid) AS uuid_hex, v.pid, v.bps, v.bpd, v.weight, v.height, v.temperature, " .
        "v.pulse, v.respiration, v.BMI, v.oxygen_saturation, v.note, f.id AS form_registration_id " .
        "FROM forms f JOIN form_vitals v ON v.id=f.form_id " .
        "WHERE f.formdir='vitals' AND f.deleted=0 AND f.pid=? AND f.encounter=? AND v.note=?",
        [$patient['pid'], $encounter['encounter'], 'Deterministic synthetic historical vitals ' . $record['vitals_external_id']],
        'vitals record'
    );
    if ((int)$vitals['pid'] !== (int)$patient['pid']) {
        fail('Vitals patient mismatch', ['external_id' => $record['vitals_external_id']]);
    }
    foreach (['bps','bpd','weight','height','temperature','pulse','respiration','oxygen_saturation'] as $field) {
        if (abs((float)$vitals[$field] - (float)$expected['template'][$field]) > 0.001) {
            fail('Vitals postcondition mismatch', ['field' => $field, 'external_id' => $record['vitals_external_id']]);
        }
    }
    if (abs((float)$vitals['BMI'] - (float)$expected['bmi']) > 0.01) {
        fail('BMI postcondition mismatch', ['external_id' => $record['vitals_external_id']]);
    }
    if ($createdIds !== null &&
        (int)$vitals['id'] !== (int)$createdIds['vitals_id']) {
        fail('Native vitals record ID does not match persisted relationship');
    }
    return [
        'encounter_id' => (int)$encounter['id'],
        'encounter_number' => (int)$encounter['encounter'],
        'encounter_uuid' => strtolower(implode('-', [substr($encounter['uuid_hex'],0,8),substr($encounter['uuid_hex'],8,4),substr($encounter['uuid_hex'],12,4),substr($encounter['uuid_hex'],16,4),substr($encounter['uuid_hex'],20,12)])),
        'encounter_form_id' => (int)$encounterForm['id'],
        'vitals_id' => (int)$vitals['id'],
        'vitals_form_id' => (int)$vitals['form_registration_id'],
        'bmi' => (float)$vitals['BMI'],
    ];
}

$created = [];
$transactionStarted = false;
try {
    $profile = $payload['profile'];
    $records = $payload['records'];
    if (($profile['synthetic_only'] ?? false) !== true || ($profile['environment'] ?? '') !== 'local-lab') {
        fail('Synthetic local-lab profile is required');
    }
    $admin = exactRow("SELECT id, username FROM users WHERE username=? AND active=1", [$profile['encounter']['author_username']], 'active execution user');
    $session = SessionWrapperFactory::getInstance()->getActiveSession();
    $session->set('authUserID', (int)$admin['id']);
    $session->set('authUser', $admin['username']);
    $session->set('authProvider', $profile['encounter']['provider_group']);
    $service = new EncounterService();
    $outcomes = [];
    $verification = [];
    $verifyOnly = (bool)($payload['verify_only'] ?? false);
    if ($commit && !$verifyOnly) {
        sqlBeginTrans();
        $transactionStarted = true;
    }
    foreach ($records as $record) {
        $patient = exactRow(
            "SELECT p.pid, p.uuid, p.pubpid, p.usertext3 AS cohort, p.providerID AS provider_id, " .
            "u.username AS provider_username, u.facility_id, f.name AS facility_name " .
            "FROM patient_data p JOIN users u ON u.id=p.providerID JOIN facility f ON f.id=u.facility_id " .
            "WHERE p.pubpid=? AND p.usertext1='SYNTHETIC_POPULATION_V1'",
            [$record['mrn']],
            'synthetic patient'
        );
        $expected = expectedFor($profile, $record, $patient);
        $existing = sqlQuery('SELECT id FROM form_encounter WHERE external_id = ?', [$record['encounter_external_id']]);
        if (!empty($existing)) {
            $outcomes[$record['mrn']] = 'EXISTING';
            $verification[$record['mrn']] = verifyRecord($record, $patient, $expected);
            continue;
        }
        if ($verifyOnly) {
            fail('Expected encounter is missing', ['mrn' => $record['mrn']]);
        }
        if (!$commit) {
            $outcomes[$record['mrn']] = 'WOULD_CREATE';
            continue;
        }
        $encounterData = [
            'date' => $record['encounter_at'],
            'pc_catid' => (int)$profile['encounter']['category_id'],
            'facility_id' => (int)$patient['facility_id'],
            'facility' => $patient['facility_name'],
            'billing_facility' => (int)$patient['facility_id'],
            'reason' => $expected['template']['reason'],
            'class_code' => $profile['encounter']['class_code'],
            'provider_id' => (int)$patient['provider_id'],
            'external_id' => $record['encounter_external_id'],
            'user' => $profile['encounter']['author_username'],
            'group' => $profile['encounter']['provider_group'],
        ];
        $encounterResult = $service->insertEncounter(UuidRegistry::uuidToString($patient['uuid']), $encounterData);
        if (!$encounterResult->isValid() || !$encounterResult->hasData()) {
            fail('Native encounter insertion failed', ['messages' => $encounterResult->getMessages()]);
        }
        $encounter = $encounterResult->getFirstDataResult();
        $encounterRow = exactRow('SELECT id, encounter FROM form_encounter WHERE external_id=?', [$record['encounter_external_id']], 'new encounter');
        $created[] = [
            'pid' => (int)$patient['pid'],
            'encounter_id' => (int)$encounterRow['id'],
            'encounter_number' => (int)$encounterRow['encounter'],
            'vitals_id' => null,
            'vitals_form_id' => null,
            'native_vitals_form_id' => null,
        ];
        $createdIndex = array_key_last($created);
        $vitalsData = $expected['template'] + [
            'date' => $record['vitals_at'],
            'user' => $profile['encounter']['author_username'],
            'groupname' => $profile['encounter']['provider_group'],
            'activity' => 1,
            'BMI' => $expected['bmi'],
            'temp_method' => $profile['vitals']['temperature_method'],
            'note' => 'Deterministic synthetic historical vitals ' . $record['vitals_external_id'],
        ];
        unset($vitalsData['reason']);
        $basic = $service->validateVital($vitalsData);
        if (!$basic->isValid()) {
            fail('Basic vitals validation failed', ['messages' => $basic->getMessages()]);
        }
        $clinicalForm = new FormVitals();
        $clinicalForm->populate_array($vitalsData);
        $clinical = $clinicalForm->validate();
        if (!empty($clinical['errors'])) {
            fail('Clinical vitals validation failed', $clinical);
        }
        $vitalIds = $service->insertVital((int)$patient['pid'], (int)$encounter['eid'], $vitalsData);
        if (!is_array($vitalIds) || count($vitalIds) !== 2) {
            fail('Native vitals insertion did not return both expected IDs');
        }
        $created[$createdIndex]['vitals_id'] = (int)$vitalIds[0];
        // EncounterService::insertVital() resolves its second return value with
        // `SELECT id FROM forms WHERE form_id = ?`. IDs overlap across OpenEMR
        // form tables, so that value is diagnostic rather than authoritative.
        $created[$createdIndex]['native_vitals_form_id'] = (int)$vitalIds[1];
        $outcomes[$record['mrn']] = 'CREATED';
        $verified = verifyRecord($record, $patient, $expected, $created[$createdIndex]);
        $created[$createdIndex]['vitals_form_id'] = $verified['vitals_form_id'];
        $verified['native_vitals_form_id'] = $created[$createdIndex]['native_vitals_form_id'];
        $verification[$record['mrn']] = $verified;
    }
    if ($transactionStarted) {
        sqlCommitTrans();
    }
    if ($verifyOnly) {
        respond(['status' => 'VERIFIED', 'expected_patients' => count($records), 'resolved_patients' => count($verification), 'records' => $verification]);
    }
    respond(['status' => 'PASS', 'mode' => $commit ? 'COMMIT' : 'DRY_RUN', 'patient_outcomes' => $outcomes, 'verification' => ['status' => $commit ? 'VERIFIED' : 'NOT_WRITTEN', 'expected_patients' => count($records), 'resolved_patients' => count($verification)], 'records' => $verification]);
} catch (Throwable $error) {
    if (!empty($transactionStarted)) {
        sqlRollbackTrans();
    }
    $cleanupErrors = [];
    foreach (array_reverse($created) as $item) {
        try {
            if (!empty($item['vitals_id'])) {
                $calcStatement = sqlStatement('SELECT fvc_uuid FROM form_vitals_calculation_form_vitals WHERE vitals_id=?', [$item['vitals_id']]);
                $calculationUuids = [];
                while ($calc = sqlFetchArray($calcStatement)) {
                    $calculationUuids[] = $calc['fvc_uuid'];
                }
                sqlStatement('DELETE FROM form_vitals_calculation_form_vitals WHERE vitals_id=?', [$item['vitals_id']]);
                foreach ($calculationUuids as $calculationUuid) {
                    $remaining = (int)(sqlQuery('SELECT COUNT(*) AS count_value FROM form_vitals_calculation_form_vitals WHERE fvc_uuid=?', [$calculationUuid])['count_value'] ?? 0);
                    if ($remaining === 0) {
                        sqlStatement('DELETE FROM form_vitals_calculation_components WHERE fvc_uuid=?', [$calculationUuid]);
                        sqlStatement('DELETE FROM form_vitals_calculation WHERE uuid=?', [$calculationUuid]);
                    }
                }
                // Discover the authoritative registration by its complete
                // relationship. Do not rely on insertVital()'s ambiguous second ID.
                sqlStatement(
                    "DELETE FROM forms WHERE formdir='vitals' AND form_id=? AND pid=? AND encounter=?",
                    [$item['vitals_id'], $item['pid'], $item['encounter_number']]
                );
                sqlStatement('DELETE FROM form_vitals WHERE id=? AND pid=?', [$item['vitals_id'], $item['pid']]);
            }
            sqlStatement("DELETE FROM forms WHERE formdir='newpatient' AND form_id=? AND pid=? AND encounter=?", [$item['encounter_id'], $item['pid'], $item['encounter_number']]);
            sqlStatement('DELETE FROM form_encounter WHERE id=? AND pid=? AND encounter=?', [$item['encounter_id'], $item['pid'], $item['encounter_number']]);
            $remainingCore = (int)(sqlQuery(
                'SELECT (SELECT COUNT(*) FROM form_encounter WHERE id=?) + ' .
                '(SELECT COUNT(*) FROM form_vitals WHERE id=?) + ' .
                '(SELECT COUNT(*) FROM forms WHERE pid=? AND encounter=? AND form_id IN (?,?)) AS count_value',
                [$item['encounter_id'], $item['vitals_id'] ?? 0, $item['pid'], $item['encounter_number'], $item['encounter_id'], $item['vitals_id'] ?? 0]
            )['count_value'] ?? 0);
            if ($remainingCore !== 0) {
                throw new RuntimeException('Compensating cleanup postcondition failed');
            }
        } catch (Throwable $cleanupError) {
            $cleanupErrors[] = $cleanupError->getMessage();
        }
    }
    respond(['status' => 'FAIL', 'message' => $error->getMessage(), 'compensating_cleanup' => empty($cleanupErrors) ? 'COMPLETED' : 'FAILED', 'cleanup_errors' => $cleanupErrors], 1);
}
