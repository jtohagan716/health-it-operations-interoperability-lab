<?php

declare(strict_types=1);

use OpenEMR\Common\Session\SessionWrapperFactory;
use OpenEMR\Common\Uuid\UuidRegistry;

$ignoreAuth = true;
$_GET['site'] = 'default';
$_SERVER['HTTP_HOST'] = 'localhost';
error_reporting(E_ALL & ~E_DEPRECATED);
ini_set('display_errors', '0');

require_once '/var/www/localhost/htdocs/openemr/interface/globals.php';
require_once '/var/www/localhost/htdocs/openemr/library/sql.inc.php';
require_once '/var/www/localhost/htdocs/openemr/library/forms.inc.php';
require_once '/var/www/localhost/htdocs/openemr/interface/forms/procedure_order/procedure_order_save_functions.php';

$payload = json_decode(
    base64_decode('__SYNTHETIC_PAYLOAD_BASE64__'),
    true,
    512,
    JSON_THROW_ON_ERROR
);
$commit = __SYNTHETIC_COMMIT__;

function respond(array $body, int $code = 0): never
{
    echo json_encode(
        $body,
        JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES
    ) . PHP_EOL;
    exit($code);
}

function fail(string $message, array $context = []): never
{
    throw new RuntimeException(
        $message . (
            empty($context)
                ? ''
                : ': ' . json_encode($context)
        )
    );
}

function allRows(string $sql, array $bind = []): array
{
    $statement = sqlStatement($sql, $bind);
    $rows = [];
    while ($row = sqlFetchArray($statement)) {
        $rows[] = $row;
    }
    return $rows;
}

function exactRow(string $sql, array $bind, string $label): array
{
    $rows = allRows($sql, $bind);
    if (count($rows) !== 1) {
        fail("Expected exactly one {$label}", ['count' => count($rows)]);
    }
    return $rows[0];
}

function uuidFromHex(string $hex): string
{
    $hex = strtolower($hex);
    return implode('-', [
        substr($hex, 0, 8),
        substr($hex, 8, 4),
        substr($hex, 12, 4),
        substr($hex, 16, 4),
        substr($hex, 20, 12),
    ]);
}

function findLaboratory(array $config): ?array
{
    $rows = allRows(
        'SELECT ppid, HEX(uuid) AS uuid_hex, name, npi, send_app_id, ' .
        'send_fac_id, recv_app_id, recv_fac_id, DorP, direction, protocol, ' .
        'remote_host, active, type, notes FROM procedure_providers WHERE name=?',
        [$config['name']]
    );
    if (count($rows) > 1) {
        fail('Synthetic laboratory name is not unique');
    }
    return $rows[0] ?? null;
}

function verifyLaboratory(array $row, array $config): array
{
    $expected = [
        'name' => $config['name'],
        'send_app_id' => $config['send_app_id'],
        'send_fac_id' => $config['send_fac_id'],
        'recv_app_id' => $config['recv_app_id'],
        'recv_fac_id' => $config['recv_fac_id'],
        'DorP' => $config['environment_mode'],
        'direction' => $config['direction'],
        'protocol' => $config['protocol'],
        'type' => $config['type'],
    ];
    foreach ($expected as $field => $value) {
        if ((string)$row[$field] !== (string)$value) {
            fail('Synthetic laboratory configuration mismatch', [
                'field' => $field,
                'expected' => $value,
                'actual' => $row[$field],
            ]);
        }
    }
    if ((int)$row['active'] !== 1 || (string)$row['npi'] !== '') {
        fail('Synthetic laboratory safety attributes mismatch');
    }
    if (empty($row['uuid_hex'])) {
        fail('Synthetic laboratory UUID is missing');
    }
    return [
        'ppid' => (int)$row['ppid'],
        'uuid' => uuidFromHex($row['uuid_hex']),
        'name' => $row['name'],
        'receiving_application' => $row['recv_app_id'],
        'receiving_facility' => $row['recv_fac_id'],
    ];
}

function findOrderable(int $labId, array $config): ?array
{
    $rows = allRows(
        'SELECT procedure_type_id, parent, name, lab_id, procedure_code, ' .
        'procedure_type, specimen, description, standard_code, units, `range`, ' .
        'activity FROM procedure_type WHERE lab_id=? AND procedure_code=? ' .
        "AND procedure_type='ord'",
        [$labId, $config['procedure_code']]
    );
    if (count($rows) > 1) {
        fail('Synthetic laboratory orderable is not unique');
    }
    return $rows[0] ?? null;
}

function verifyOrderable(array $row, int $labId, array $config): array
{
    $expected = [
        'parent' => 0,
        'name' => $config['name'],
        'lab_id' => $labId,
        'procedure_code' => $config['procedure_code'],
        'procedure_type' => $config['procedure_type'],
        'standard_code' => $config['standard_code'],
        'specimen' => $config['specimen'],
        'units' => $config['units'],
        'range' => $config['range'],
        'activity' => 1,
    ];
    foreach ($expected as $field => $value) {
        if ((string)$row[$field] !== (string)$value) {
            fail('Synthetic orderable configuration mismatch', [
                'field' => $field,
                'expected' => $value,
                'actual' => $row[$field],
            ]);
        }
    }
    return [
        'procedure_type_id' => (int)$row['procedure_type_id'],
        'procedure_code' => $row['procedure_code'],
        'name' => $row['name'],
        'standard_code' => $row['standard_code'],
        'units' => $row['units'],
        'range' => $row['range'],
    ];
}

function resolveDiagnosis(array $patient, array $encounter, array $config): string
{
    $row = sqlQuery(
        "SELECT l.diagnosis FROM lists l JOIN issue_encounter ie " .
        "ON ie.list_id=l.id AND ie.pid=l.pid WHERE l.pid=? " .
        "AND l.type='medical_problem' AND l.activity=1 AND ie.encounter=? " .
        'ORDER BY l.id LIMIT 1',
        [$patient['pid'], $encounter['encounter']]
    );
    $diagnosis = trim((string)($row['diagnosis'] ?? ''));
    if ($diagnosis === '') {
        fail('Synthetic encounter diagnosis is required for laboratory order', [
            'mrn' => $patient['pubpid'],
            'encounter_external_id' => $encounter['external_id'],
        ]);
    }
    if (!str_starts_with($diagnosis, $config['diagnosis_prefix'])) {
        fail('Laboratory order diagnosis is not an ICD-10 value', [
            'diagnosis' => $diagnosis,
        ]);
    }
    return $diagnosis;
}

function findOrder(string $externalId): ?array
{
    $rows = allRows(
        'SELECT procedure_order_id, HEX(uuid) AS uuid_hex, external_id, ' .
        'patient_id, encounter_id, provider_id, lab_id, date_ordered, ' .
        'order_priority, order_status, activity, procedure_order_type, ' .
        'order_intent, order_diagnosis FROM procedure_order WHERE external_id=?',
        [$externalId]
    );
    if (count($rows) > 1) {
        fail('Laboratory order external identifier is not unique', [
            'external_id' => $externalId,
        ]);
    }
    return $rows[0] ?? null;
}

function verifyOrder(
    array $profile,
    array $record,
    array $patient,
    array $encounter,
    array $laboratory,
    array $orderable,
    string $diagnosis,
    ?int $createdOrderId = null
): array {
    $order = findOrder($record['order_external_id']);
    if ($order === null) {
        fail('Expected laboratory order is missing', [
            'external_id' => $record['order_external_id'],
        ]);
    }
    $expected = [
        'external_id' => $record['order_external_id'],
        'patient_id' => (int)$patient['pid'],
        'encounter_id' => (int)$encounter['encounter'],
        'provider_id' => (int)$patient['provider_id'],
        'lab_id' => (int)$laboratory['ppid'],
        'date_ordered' => $encounter['date'],
        'order_priority' => $profile['order_priority'],
        'order_status' => $profile['order_status'],
        'activity' => 1,
        'procedure_order_type' => $profile['procedure_order_type'],
        'order_intent' => $profile['order_intent'],
        'order_diagnosis' => $diagnosis,
    ];
    foreach ($expected as $field => $value) {
        if ((string)$order[$field] !== (string)$value) {
            fail('Laboratory order postcondition mismatch', [
                'external_id' => $record['order_external_id'],
                'field' => $field,
                'expected' => $value,
                'actual' => $order[$field],
            ]);
        }
    }
    if ($createdOrderId !== null && (int)$order['procedure_order_id'] !== $createdOrderId) {
        fail('Created laboratory order ID does not match persisted record');
    }
    if (empty($order['uuid_hex'])) {
        fail('Laboratory order UUID is missing');
    }

    $line = exactRow(
        'SELECT procedure_order_id, procedure_order_seq, procedure_code, ' .
        'procedure_name, diagnoses, procedure_type, transport FROM ' .
        'procedure_order_code WHERE procedure_order_id=?',
        [$order['procedure_order_id']],
        'laboratory ordered-test line'
    );
    if (
        (int)$line['procedure_order_seq'] !== 1 ||
        $line['procedure_code'] !== $orderable['procedure_code'] ||
        $line['procedure_name'] !== $orderable['name'] ||
        $line['diagnoses'] !== $diagnosis ||
        $line['procedure_type'] !== $profile['procedure_order_type'] ||
        $line['transport'] !== $profile['orderable']['transport']
    ) {
        fail('Laboratory ordered-test postcondition mismatch', [
            'external_id' => $record['order_external_id'],
        ]);
    }

    $form = exactRow(
        "SELECT id, form_name, form_id, pid, encounter, deleted, formdir " .
        "FROM forms WHERE formdir='procedure_order' AND form_id=? " .
        'AND pid=? AND encounter=? AND deleted=0',
        [
            $order['procedure_order_id'],
            $patient['pid'],
            $encounter['encounter'],
        ],
        'laboratory order form registration'
    );

    return [
        'mrn' => $patient['pubpid'],
        'cohort' => $patient['cohort'],
        'order_external_id' => $order['external_id'],
        'order_id' => (int)$order['procedure_order_id'],
        'order_uuid' => uuidFromHex($order['uuid_hex']),
        'encounter_external_id' => $encounter['external_id'],
        'encounter_number' => (int)$encounter['encounter'],
        'form_registration_id' => (int)$form['id'],
        'lab_id' => (int)$order['lab_id'],
        'placer_order_number' => $order['external_id'],
        'test_code' => $line['procedure_code'],
        'test_name' => $line['procedure_name'],
        'diagnosis' => $line['diagnoses'],
        'ordered_at' => $order['date_ordered'],
    ];
}

$created = [];
$transactionStarted = false;

try {
    $profile = $payload['profile'];
    $records = $payload['records'];
    $verifyOnly = (bool)($payload['verify_only'] ?? false);

    if (
        ($profile['synthetic_only'] ?? false) !== true ||
        ($profile['environment'] ?? '') !== 'local-lab'
    ) {
        fail('Synthetic local-lab profile is required');
    }
    if (($profile['laboratory']['recv_app_id'] ?? '') !== 'SYNLIS') {
        fail('Vendor-neutral synthetic LIS configuration is required');
    }

    $expectedPatients = (int)($payload['expected_patients'] ?? 0);
    $expectedRequisitions = (int)($payload['expected_requisitions'] ?? 0);
    $expectedOrderLines = (int)($payload['expected_order_lines'] ?? 0);
    $keys = array_column($records, 'order_external_id');
    $actualPatients = count(array_unique(array_column($records, 'mrn')));

    if (
        count($records) !== $expectedRequisitions ||
        count(array_unique($keys)) !== $expectedRequisitions ||
        $expectedOrderLines !== $expectedRequisitions
    ) {
        fail('Laboratory payload cardinality mismatch');
    }
    if ($actualPatients !== $expectedPatients) {
        fail('Laboratory payload patient count mismatch');
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

    if ($commit && !$verifyOnly) {
        sqlBeginTrans();
        $transactionStarted = true;
    }

    $configurationOutcomes = [];
    $laboratoryRow = findLaboratory($profile['laboratory']);
    if ($laboratoryRow === null) {
        if ($verifyOnly) {
            fail('Expected synthetic laboratory configuration is missing');
        }
        if (!$commit) {
            $configurationOutcomes['laboratory'] = 'WOULD_CREATE';
        } else {
            $labId = sqlInsert(
                'INSERT INTO procedure_providers SET name=?, npi=?, ' .
                'send_app_id=?, send_fac_id=?, recv_app_id=?, recv_fac_id=?, ' .
                'DorP=?, direction=?, protocol=?, remote_host=?, login=?, ' .
                'password=?, orders_path=?, results_path=?, notes=?, active=1, type=?',
                [
                    $profile['laboratory']['name'],
                    '',
                    $profile['laboratory']['send_app_id'],
                    $profile['laboratory']['send_fac_id'],
                    $profile['laboratory']['recv_app_id'],
                    $profile['laboratory']['recv_fac_id'],
                    $profile['laboratory']['environment_mode'],
                    $profile['laboratory']['direction'],
                    $profile['laboratory']['protocol'],
                    '', '', '', '', '',
                    $profile['laboratory']['notes'],
                    $profile['laboratory']['type'],
                ]
            );
            UuidRegistry::createMissingUuidsForTables(['procedure_providers']);
            $created[] = ['type' => 'laboratory', 'id' => (int)$labId];
            $laboratoryRow = findLaboratory($profile['laboratory']);
            $configurationOutcomes['laboratory'] = 'CREATED';
        }
    } else {
        $configurationOutcomes['laboratory'] = 'EXISTING';
    }

    $laboratory = null;
    $orderable = null;
    if ($laboratoryRow !== null) {
        $laboratory = verifyLaboratory(
            $laboratoryRow,
            $profile['laboratory']
        );
        $orderableRow = findOrderable(
            $laboratory['ppid'],
            $profile['orderable']
        );
        if ($orderableRow === null) {
            if ($verifyOnly) {
                fail('Expected synthetic glucose orderable is missing');
            }
            if (!$commit) {
                $configurationOutcomes['orderable'] = 'WOULD_CREATE';
            } else {
                $procedureTypeId = sqlInsert(
                    'INSERT INTO procedure_type SET parent=0, name=?, lab_id=?, ' .
                    'procedure_code=?, procedure_type=?, specimen=?, description=?, ' .
                    'standard_code=?, units=?, `range`=?, activity=1, seq=1, notes=?',
                    [
                        $profile['orderable']['name'],
                        $laboratory['ppid'],
                        $profile['orderable']['procedure_code'],
                        $profile['orderable']['procedure_type'],
                        $profile['orderable']['specimen'],
                        'Synthetic glucose orderable for interoperability testing',
                        $profile['orderable']['standard_code'],
                        $profile['orderable']['units'],
                        $profile['orderable']['range'],
                        'Local synthetic terminology configuration',
                    ]
                );
                $created[] = [
                    'type' => 'orderable',
                    'id' => (int)$procedureTypeId,
                    'lab_id' => (int)$laboratory['ppid'],
                ];
                $orderableRow = findOrderable(
                    $laboratory['ppid'],
                    $profile['orderable']
                );
                $configurationOutcomes['orderable'] = 'CREATED';
            }
        } else {
            $configurationOutcomes['orderable'] = 'EXISTING';
        }
        if ($orderableRow !== null) {
            $orderable = verifyOrderable(
                $orderableRow,
                $laboratory['ppid'],
                $profile['orderable']
            );
        }
    } else {
        $configurationOutcomes['orderable'] = 'WOULD_CREATE';
    }

    $outcomes = [];
    $verification = [];

    foreach ($records as $record) {
        $patient = exactRow(
            "SELECT p.pid, p.pubpid, p.usertext3 AS cohort, " .
            "p.providerID AS provider_id FROM patient_data p WHERE " .
            "p.pubpid=? AND p.usertext1='SYNTHETIC_POPULATION_V1'",
            [$record['mrn']],
            'synthetic patient'
        );
        if ((int)$patient['provider_id'] <= 0) {
            fail('Synthetic patient has no assigned ordering provider', [
                'mrn' => $record['mrn'],
            ]);
        }
        $encounter = exactRow(
            'SELECT id, encounter, pid, date, external_id FROM form_encounter ' .
            'WHERE external_id=? AND pid=?',
            [$record['encounter_external_id'], $patient['pid']],
            'synthetic encounter'
        );
        $diagnosis = resolveDiagnosis(
            $patient,
            $encounter,
            $profile['orderable']
        );
        $existing = findOrder($record['order_external_id']);

        if ($existing !== null) {
            if ($laboratory === null || $orderable === null) {
                fail('Existing order cannot be verified without configuration');
            }
            $outcomes[$record['order_external_id']] = 'EXISTING';
            $verification[$record['order_external_id']] = verifyOrder(
                $profile,
                $record,
                $patient,
                $encounter,
                $laboratory,
                $orderable,
                $diagnosis
            );
            continue;
        }
        if ($verifyOnly) {
            fail('Expected laboratory order is missing', [
                'external_id' => $record['order_external_id'],
            ]);
        }
        if (!$commit) {
            $outcomes[$record['order_external_id']] = 'WOULD_CREATE';
            continue;
        }
        if ($laboratory === null || $orderable === null) {
            fail('Laboratory configuration was not resolved before commit');
        }

        $orderId = sqlInsert(
            'INSERT INTO procedure_order SET provider_id=?, patient_id=?, ' .
            'encounter_id=?, date_ordered=?, order_priority=?, order_status=?, ' .
            'activity=1, control_id=?, lab_id=?, external_id=?, history_order=?, ' .
            'order_diagnosis=?, procedure_order_type=?, order_intent=?',
            [
                $patient['provider_id'],
                $patient['pid'],
                $encounter['encounter'],
                $encounter['date'],
                $profile['order_priority'],
                $profile['order_status'],
                '',
                $laboratory['ppid'],
                $record['order_external_id'],
                '0',
                $diagnosis,
                $profile['procedure_order_type'],
                $profile['order_intent'],
            ]
        );
        UuidRegistry::createMissingUuidsForTables(['procedure_order']);
        $created[] = [
            'type' => 'order',
            'id' => (int)$orderId,
            'pid' => (int)$patient['pid'],
            'encounter' => (int)$encounter['encounter'],
        ];

        $title = $profile['laboratory']['name'] . '-laboratory_test-' .
            $orderId . '-' . substr($encounter['date'], 0, 10);
        addForm(
            (int)$encounter['encounter'],
            $title,
            (int)$orderId,
            'procedure_order',
            (int)$patient['pid'],
            1
        );

        insertProcedureOrderCode(
            (int)$orderId,
            1,
            [
                'diagnoses' => $diagnosis,
                'procedure_order_title' => $profile['orderable']['name'],
                'transport' => $profile['orderable']['transport'],
                'procedure_type' => $profile['procedure_order_type'],
                'reason_code' => '',
                'reason_description' => null,
                'reason_date_low' => null,
                'reason_date_high' => null,
                'reason_status' => null,
            ],
            $orderable['procedure_type_id']
        );

        $outcomes[$record['order_external_id']] = 'CREATED';
        $verification[$record['order_external_id']] = verifyOrder(
            $profile,
            $record,
            $patient,
            $encounter,
            $laboratory,
            $orderable,
            $diagnosis,
            (int)$orderId
        );
    }

    if ($transactionStarted) {
        sqlCommitTrans();
        $transactionStarted = false;
    }

    if ($verifyOnly) {
        respond([
            'status' => 'VERIFIED',
            'expected_patients' => $expectedPatients,
            'expected_requisitions' => $expectedRequisitions,
            'expected_order_lines' => $expectedOrderLines,
            'resolved_requisitions' => count($verification),
            'laboratory' => $laboratory,
            'orderable' => $orderable,
            'records' => $verification,
        ]);
    }

    respond([
        'status' => 'PASS',
        'mode' => $commit ? 'COMMIT' : 'DRY_RUN',
        'configuration_outcomes' => $configurationOutcomes,
        'record_outcomes' => $outcomes,
        'verification' => [
            'status' => $commit ? 'VERIFIED' : 'NOT_WRITTEN',
            'expected_patients' => $expectedPatients,
            'expected_requisitions' => $expectedRequisitions,
            'expected_order_lines' => $expectedOrderLines,
            'resolved_requisitions' => count($verification),
        ],
        'laboratory' => $laboratory,
        'orderable' => $orderable,
        'records' => $verification,
    ]);
} catch (Throwable $error) {
    if ($transactionStarted) {
        sqlRollbackTrans();
        $transactionStarted = false;
    }

    $cleanupErrors = [];
    foreach (array_reverse($created) as $item) {
        try {
            if ($item['type'] === 'order') {
                $uuid = sqlQuery(
                    'SELECT uuid FROM procedure_order WHERE procedure_order_id=?',
                    [$item['id']]
                );
                sqlStatement(
                    'DELETE FROM procedure_specimen WHERE procedure_order_id=?',
                    [$item['id']]
                );
                sqlStatement(
                    'DELETE FROM procedure_order_code WHERE procedure_order_id=?',
                    [$item['id']]
                );
                sqlStatement(
                    "DELETE FROM forms WHERE formdir='procedure_order' " .
                    'AND form_id=? AND pid=? AND encounter=?',
                    [$item['id'], $item['pid'], $item['encounter']]
                );
                sqlStatement(
                    'DELETE FROM procedure_order WHERE procedure_order_id=? ' .
                    'AND patient_id=? AND encounter_id=?',
                    [$item['id'], $item['pid'], $item['encounter']]
                );
                if (!empty($uuid['uuid'])) {
                    sqlStatement(
                        'DELETE FROM uuid_registry WHERE uuid=?',
                        [$uuid['uuid']]
                    );
                }
            } elseif ($item['type'] === 'orderable') {
                $used = (int)(sqlQuery(
                    'SELECT COUNT(*) AS count_value FROM procedure_order ' .
                    'WHERE lab_id=?',
                    [$item['lab_id']]
                )['count_value'] ?? 0);
                if ($used === 0) {
                    sqlStatement(
                        'DELETE FROM procedure_type WHERE procedure_type_id=?',
                        [$item['id']]
                    );
                }
            } elseif ($item['type'] === 'laboratory') {
                $row = sqlQuery(
                    'SELECT uuid FROM procedure_providers WHERE ppid=?',
                    [$item['id']]
                );
                $used = (int)(sqlQuery(
                    'SELECT COUNT(*) AS count_value FROM procedure_order ' .
                    'WHERE lab_id=?',
                    [$item['id']]
                )['count_value'] ?? 0);
                if ($used === 0) {
                    sqlStatement(
                        'DELETE FROM procedure_type WHERE lab_id=?',
                        [$item['id']]
                    );
                    sqlStatement(
                        'DELETE FROM procedure_providers WHERE ppid=?',
                        [$item['id']]
                    );
                    if (!empty($row['uuid'])) {
                        sqlStatement(
                            'DELETE FROM uuid_registry WHERE uuid=?',
                            [$row['uuid']]
                        );
                    }
                }
            }
        } catch (Throwable $cleanupError) {
            $cleanupErrors[] = $cleanupError->getMessage();
        }
    }

    respond([
        'status' => 'FAIL',
        'message' => $error->getMessage(),
        'compensating_cleanup' => (
            empty($cleanupErrors) ? 'COMPLETED' : 'FAILED'
        ),
        'cleanup_errors' => $cleanupErrors,
    ], 1);
}
