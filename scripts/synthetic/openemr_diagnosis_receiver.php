<?php

declare(strict_types=1);

use OpenEMR\Common\Session\SessionWrapperFactory;
use OpenEMR\Common\Uuid\UuidRegistry;
use OpenEMR\Services\ConditionService;
use OpenEMR\Services\PatientIssuesService;

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

function uuidFromHex(string $hex): string
{
    $hex = strtolower($hex);
    return implode('-', [substr($hex, 0, 8), substr($hex, 8, 4), substr($hex, 12, 4), substr($hex, 16, 4), substr($hex, 20, 12)]);
}

function expectedFor(array $profile, array $patient, array $encounter): array
{
    $template = $profile['cohort_conditions'][$patient['cohort']] ?? null;
    if (!is_array($template)) {
        fail('No condition template for patient cohort', ['cohort' => $patient['cohort']]);
    }
    $encounterDate = new DateTimeImmutable(substr($encounter['date'], 0, 10));
    $problemDate = $encounterDate->modify('-' . (int)$template['onset_days_before'] . ' days');
    return [
        'template' => $template,
        'diagnosis' => 'ICD10:' . $template['code'],
        'encounter_date' => $encounterDate->format('Y-m-d'),
        'problem_date' => $problemDate->format('Y-m-d'),
    ];
}

function conditionByExternalId(string $externalId): ?array
{
    $row = sqlQuery(
        "SELECT id, HEX(uuid) AS uuid_hex, pid, type, title, diagnosis, begdate, enddate, " .
        "activity, outcome, verification, external_id, user, groupname FROM lists " .
        "WHERE type='medical_problem' AND external_id=?",
        [$externalId]
    );
    return empty($row) ? null : $row;
}

function verifyCondition(
    array $condition,
    array $patient,
    array $expected,
    string $externalId,
    bool $encounterDiagnosis,
    array $encounter
): array {
    if ((int)$condition['pid'] !== (int)$patient['pid'] ||
        $condition['type'] !== 'medical_problem' ||
        $condition['title'] !== $expected['template']['title'] ||
        $condition['diagnosis'] !== $expected['diagnosis'] ||
        (int)$condition['activity'] !== 1 ||
        $condition['verification'] !== 'confirmed' ||
        $condition['external_id'] !== $externalId) {
        fail('Condition postcondition mismatch', ['external_id' => $externalId]);
    }
    $expectedDate = $encounterDiagnosis ? $expected['encounter_date'] : $expected['problem_date'];
    if (substr((string)$condition['begdate'], 0, 10) !== $expectedDate) {
        fail('Condition onset-date mismatch', ['external_id' => $externalId]);
    }
    $links = [];
    $statement = sqlStatement(
        'SELECT id, HEX(uuid) AS uuid_hex, pid, list_id, encounter, resolved, created_by, updated_by ' .
        'FROM issue_encounter WHERE pid=? AND list_id=?',
        [$patient['pid'], $condition['id']]
    );
    while ($link = sqlFetchArray($statement)) {
        $links[] = $link;
    }
    if ($encounterDiagnosis) {
        if (count($links) !== 1 ||
            (int)$links[0]['encounter'] !== (int)$encounter['encounter'] ||
            (int)$links[0]['resolved'] !== 0) {
            fail('Encounter diagnosis relationship mismatch', ['external_id' => $externalId]);
        }
    } elseif (!empty($links)) {
        fail('Problem-list condition must not have an encounter link', ['external_id' => $externalId]);
    }
    $result = [
        'condition_id' => (int)$condition['id'],
        'condition_uuid' => uuidFromHex($condition['uuid_hex']),
        'external_id' => $externalId,
        'code' => $expected['template']['code'],
        'category' => $encounterDiagnosis ? 'encounter-diagnosis' : 'problem-list-item',
        'onset_date' => $expectedDate,
    ];
    if ($encounterDiagnosis) {
        $result['link_id'] = (int)$links[0]['id'];
        $result['link_uuid'] = uuidFromHex($links[0]['uuid_hex']);
        $result['encounter_number'] = (int)$links[0]['encounter'];
    }
    return $result;
}

function createCondition(
    ConditionService $service,
    array $profile,
    array $patient,
    array $expected,
    string $externalId,
    string $beginDate,
    string $category
): array {
    $result = $service->insert([
        'puuid' => UuidRegistry::uuidToString($patient['uuid']),
        'title' => $expected['template']['title'],
        'begdate' => $beginDate,
        'diagnosis' => $expected['diagnosis'],
        'external_id' => $externalId,
        'verification' => $profile['verification'],
        'outcome' => 3,
        'user' => $profile['author_username'],
        'groupname' => $profile['provider_group'],
        'comments' => 'Deterministic synthetic ' . $category . ' for interoperability testing',
    ]);
    if (!$result->isValid() || !$result->hasData()) {
        fail('Native condition insertion failed', ['messages' => $result->getMessages()]);
    }
    return $result->getFirstDataResult();
}

$created = [];
$transactionStarted = false;
try {
    $profile = $payload['profile'];
    $records = $payload['records'];
    if (($profile['synthetic_only'] ?? false) !== true || ($profile['environment'] ?? '') !== 'local-lab') {
        fail('Synthetic local-lab profile is required');
    }
    $admin = exactRow(
        'SELECT id, username FROM users WHERE username=? AND active=1',
        [$profile['author_username']],
        'active execution user'
    );
    $session = SessionWrapperFactory::getInstance()->getActiveSession();
    $session->set('authUserID', (int)$admin['id']);
    $session->set('authUser', $admin['username']);
    $session->set('authProvider', $profile['provider_group']);
    $conditionService = new ConditionService();
    $issuesService = new PatientIssuesService();
    $verifyOnly = (bool)($payload['verify_only'] ?? false);
    $outcomes = [];
    $verification = [];
    if ($commit && !$verifyOnly) {
        sqlBeginTrans();
        $transactionStarted = true;
    }
    foreach ($records as $record) {
        $patient = exactRow(
            "SELECT pid, uuid, pubpid, usertext3 AS cohort FROM patient_data " .
            "WHERE pubpid=? AND usertext1='SYNTHETIC_POPULATION_V1'",
            [$record['mrn']],
            'synthetic patient'
        );
        $encounter = exactRow(
            'SELECT id, uuid, encounter, pid, date, external_id FROM form_encounter ' .
            'WHERE external_id=? AND pid=?',
            [$record['encounter_external_id'], $patient['pid']],
            'synthetic encounter'
        );
        $expected = expectedFor($profile, $patient, $encounter);
        $codeRow = exactRow(
            "SELECT dx_code FROM icd10_dx_order_code WHERE active=1 AND valid_for_coding='1' " .
            "AND REPLACE(formatted_dx_code,'.','')=REPLACE(?,'.','')",
            [$expected['template']['code']],
            'active ICD-10-CM code'
        );
        $createdForPatient = false;
        $patientVerification = [];

        if ($expected['template']['longitudinal_problem']) {
            $problem = conditionByExternalId($record['problem_external_id']);
            if ($problem === null) {
                if ($verifyOnly) {
                    fail('Expected problem-list condition is missing', ['mrn' => $record['mrn']]);
                }
                if (!$commit) {
                    $patientVerification['problem'] = ['status' => 'WOULD_CREATE'];
                } else {
                    $new = createCondition(
                        $conditionService, $profile, $patient, $expected,
                        $record['problem_external_id'], $expected['problem_date'], 'problem-list condition'
                    );
                    $created[] = [
                        'pid' => (int)$patient['pid'],
                        'puuid' => UuidRegistry::uuidToString($patient['uuid']),
                        'condition_id' => (int)$new['id'],
                        'condition_uuid' => $new['uuid'],
                        'external_id' => $record['problem_external_id'],
                        'encounter' => null,
                        'delete_condition' => true,
                    ];
                    $problem = conditionByExternalId($record['problem_external_id']);
                    $createdForPatient = true;
                }
            }
            if ($problem !== null) {
                $patientVerification['problem'] = verifyCondition(
                    $problem, $patient, $expected, $record['problem_external_id'], false, $encounter
                );
            }
        }

        $diagnosis = conditionByExternalId($record['diagnosis_external_id']);
        if ($diagnosis === null) {
            if ($verifyOnly) {
                fail('Expected encounter diagnosis is missing', ['mrn' => $record['mrn']]);
            }
            if (!$commit) {
                $patientVerification['diagnosis'] = ['status' => 'WOULD_CREATE'];
            } else {
                $new = createCondition(
                    $conditionService, $profile, $patient, $expected,
                    $record['diagnosis_external_id'], $expected['encounter_date'], 'encounter diagnosis'
                );
                $created[] = [
                    'pid' => (int)$patient['pid'],
                    'puuid' => UuidRegistry::uuidToString($patient['uuid']),
                    'condition_id' => (int)$new['id'],
                    'condition_uuid' => $new['uuid'],
                    'external_id' => $record['diagnosis_external_id'],
                    'encounter' => (int)$encounter['encounter'],
                    'delete_condition' => true,
                ];
                $issuesService->linkIssueToEncounter(
                    (string)$patient['pid'],
                    (string)$encounter['encounter'],
                    (string)$new['id'],
                    (int)$admin['id']
                );
                $diagnosis = conditionByExternalId($record['diagnosis_external_id']);
                $createdForPatient = true;
            }
        } elseif ($commit && !$verifyOnly) {
            $link = sqlQuery(
                'SELECT id FROM issue_encounter WHERE pid=? AND list_id=? AND encounter=?',
                [$patient['pid'], $diagnosis['id'], $encounter['encounter']]
            );
            if (empty($link)) {
                $issuesService->linkIssueToEncounter(
                    (string)$patient['pid'],
                    (string)$encounter['encounter'],
                    (string)$diagnosis['id'],
                    (int)$admin['id']
                );
                $created[] = [
                    'pid' => (int)$patient['pid'],
                    'puuid' => UuidRegistry::uuidToString($patient['uuid']),
                    'condition_id' => (int)$diagnosis['id'],
                    'condition_uuid' => uuidFromHex($diagnosis['uuid_hex']),
                    'external_id' => $record['diagnosis_external_id'],
                    'encounter' => (int)$encounter['encounter'],
                    'delete_condition' => false,
                ];
                $createdForPatient = true;
            }
        }
        if ($diagnosis !== null) {
            $patientVerification['diagnosis'] = verifyCondition(
                $diagnosis, $patient, $expected, $record['diagnosis_external_id'], true, $encounter
            );
        }

        $outcomes[$record['mrn']] = $commit
            ? ($createdForPatient ? 'CREATED' : 'EXISTING')
            : (count(array_filter(
                $patientVerification,
                fn($item) => ($item['status'] ?? '') === 'WOULD_CREATE'
            )) > 0 ? 'WOULD_CREATE' : 'EXISTING');
        $verification[$record['mrn']] = $patientVerification;
    }
    if ($transactionStarted) {
        sqlCommitTrans();
    }
    if ($verifyOnly) {
        respond([
            'status' => 'VERIFIED',
            'expected_patients' => count($records),
            'resolved_patients' => count($verification),
            'records' => $verification,
        ]);
    }
    respond([
        'status' => 'PASS',
        'mode' => $commit ? 'COMMIT' : 'DRY_RUN',
        'patient_outcomes' => $outcomes,
        'verification' => [
            'status' => $commit ? 'VERIFIED' : 'NOT_WRITTEN',
            'expected_patients' => count($records),
            'resolved_patients' => count(array_filter(
                $verification,
                fn($item) => !in_array(['status' => 'WOULD_CREATE'], $item, true)
            )),
        ],
        'records' => $verification,
    ]);
} catch (Throwable $error) {
    if ($transactionStarted) {
        sqlRollbackTrans();
    }
    $cleanupErrors = [];
    foreach (array_reverse($created) as $item) {
        try {
            $linkRows = sqlStatement(
                'SELECT uuid FROM issue_encounter WHERE pid=? AND list_id=? AND encounter=?',
                [$item['pid'], $item['condition_id'], $item['encounter'] ?? 0]
            );
            while ($link = sqlFetchArray($linkRows)) {
                sqlStatement('DELETE FROM uuid_registry WHERE uuid=?', [$link['uuid']]);
            }
            sqlStatement(
                'DELETE FROM issue_encounter WHERE pid=? AND list_id=? AND encounter=?',
                [$item['pid'], $item['condition_id'], $item['encounter'] ?? 0]
            );
            $condition = conditionByExternalId($item['external_id']);
            if ($condition !== null && $item['delete_condition']) {
                $conditionService->delete($item['puuid'], $item['condition_uuid']);
                sqlStatement('DELETE FROM uuid_registry WHERE uuid=?', [UuidRegistry::uuidToBytes($item['condition_uuid'])]);
            }
            $remaining = (int)(sqlQuery(
                "SELECT (SELECT COUNT(*) FROM lists WHERE id=? AND pid=? AND external_id=?) + " .
                "(SELECT COUNT(*) FROM issue_encounter WHERE pid=? AND list_id=? AND encounter=?) AS count_value",
                [
                    $item['condition_id'],
                    $item['pid'],
                    $item['delete_condition'] ? $item['external_id'] : '__PRESERVE_EXISTING_CONDITION__',
                    $item['pid'],
                    $item['condition_id'],
                    $item['encounter'] ?? 0,
                ]
            )['count_value'] ?? 0);
            if ($remaining !== 0) {
                throw new RuntimeException('Compensating cleanup postcondition failed');
            }
        } catch (Throwable $cleanupError) {
            $cleanupErrors[] = $cleanupError->getMessage();
        }
    }
    respond([
        'status' => 'FAIL',
        'message' => $error->getMessage(),
        'compensating_cleanup' => empty($cleanupErrors) ? 'COMPLETED' : 'FAILED',
        'cleanup_errors' => $cleanupErrors,
    ], 1);
}
