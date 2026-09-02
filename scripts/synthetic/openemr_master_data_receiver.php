<?php

declare(strict_types=1);

use OpenEMR\Common\Uuid\UuidRegistry;
use OpenEMR\Services\FacilityService;

$ignoreAuth = true;
$_GET['site'] = 'default';

error_reporting(E_ALL & ~E_DEPRECATED);
ini_set('display_errors', '0');

require_once '/var/www/localhost/htdocs/openemr/interface/globals.php';

header('Content-Type: application/json');

$transactionStarted = false;

function failResponse(string $message, array $context = []): never
{
    global $transactionStarted;
    if ($transactionStarted) {
        try {
            sqlStatement('ROLLBACK');
        } catch (Throwable $ignored) {
        }
        $transactionStarted = false;
    }
    echo json_encode(array_merge([
        'status' => 'FAIL',
        'message' => $message,
    ], $context), JSON_PRETTY_PRINT) . PHP_EOL;
    exit(1);
}

function requireSyntheticPayload(array $payload): void
{
    if (($payload['environment'] ?? '') !== 'local-lab') {
        failResponse('Environment must be local-lab.');
    }
    if (($payload['synthetic_only'] ?? false) !== true) {
        failResponse('synthetic_only must be true.');
    }
    if (($payload['source_system'] ?? '') !== 'SYNTHETIC_POPULATION_V1') {
        failResponse('Unexpected source system.');
    }
    foreach (($payload['facilities'] ?? []) as $facility) {
        if (!str_starts_with((string)($facility['facility_code'] ?? ''), 'SYNFAC')) {
            failResponse('Facility outside synthetic namespace.');
        }
        if (isset($facility['facility_npi'])) {
            failResponse('Synthetic facility must not declare an NPI.');
        }
    }
    foreach (($payload['providers'] ?? []) as $provider) {
        if (!str_starts_with((string)($provider['provider_id'] ?? ''), 'SYNPROV')) {
            failResponse('Provider outside synthetic namespace.');
        }
        if (!str_starts_with((string)($provider['username'] ?? ''), 'synprov')) {
            failResponse('Provider username outside synthetic namespace.');
        }
        if (!str_ends_with((string)($provider['email'] ?? ''), '@example.invalid')) {
            failResponse('Provider email outside synthetic namespace.');
        }
        if (isset($provider['npi'])) {
            failResponse('Synthetic provider must not declare an NPI.');
        }
        if (!preg_match('/^[A-Z0-9]{10}$/', (string)($provider['taxonomy'] ?? ''))) {
            failResponse('Provider taxonomy must be a 10-character NUCC code.');
        }
    }
}

function facilityByCode(string $code): ?array
{
    $row = sqlQuery(
        'SELECT id, uuid, name, facility_code, email, street, city, state, postal_code '
        . 'FROM facility WHERE facility_code = ? LIMIT 1',
        [$code]
    );
    return $row ?: null;
}

function providerByUsername(string $username): ?array
{
    $row = sqlQuery(
        'SELECT id, uuid, username, fname, lname, email, specialty, taxonomy, facility, facility_id, active, authorized, npi, info '
        . 'FROM users WHERE username = ? LIMIT 1',
        [$username]
    );
    return $row ?: null;
}

function assertSameFields(array $expected, array $actual, array $fields, string $kind): void
{
    $mismatches = [];
    foreach ($fields as $field) {
        if ((string)($expected[$field] ?? '') !== (string)($actual[$field] ?? '')) {
            $mismatches[$field] = [
                'expected' => $expected[$field] ?? null,
                'actual' => $actual[$field] ?? null,
            ];
        }
    }
    if ($mismatches) {
        failResponse("Existing {$kind} conflicts with deterministic fixture.", [
            'mismatches' => $mismatches,
        ]);
    }
}

function ensureFacility(array $facility): array
{
    $existing = facilityByCode($facility['facility_code']);
    if ($existing) {
        assertSameFields(
            $facility,
            $existing,
            ['name', 'facility_code', 'email', 'street', 'city', 'state', 'postal_code'],
            'facility'
        );
        return ['outcome' => 'EXISTING', 'id' => (int)$existing['id']];
    }

    $facilityService = new FacilityService();
    $validation = $facilityService->validate($facility);
    if (!$validation->isValid()) {
        failResponse('Facility validation failed.', [
            'facility_code' => $facility['facility_code'],
            'errors' => $validation->getMessages(),
        ]);
    }

    $facility['uuid'] = (new UuidRegistry(['table_name' => 'facility']))->createUuid();
    $facility['organization_type'] = 'prov';
    $id = $facilityService->insertFacility($facility);
    if (!$id) {
        failResponse('Facility insert failed.', ['facility_code' => $facility['facility_code']]);
    }
    return ['outcome' => 'CREATED', 'id' => (int)$id];
}

function ensureProvider(array $provider, array $facilityIds, array $facilityNames): array
{
    $existing = providerByUsername($provider['username']);
    $facilityId = $facilityIds[$provider['facility_code']] ?? null;
    if (!$facilityId) {
        failResponse('Provider references an unresolved facility.', [
            'provider_id' => $provider['provider_id'],
        ]);
    }
    $facilityName = $facilityNames[$provider['facility_code']] ?? null;
    if (!$facilityName) {
        failResponse('Provider references an unresolved facility name.', [
            'provider_id' => $provider['provider_id'],
        ]);
    }

    $expected = [
        'username' => $provider['username'],
        'fname' => $provider['given_name'],
        'lname' => $provider['family_name'],
        'email' => $provider['email'],
        'specialty' => $provider['specialty'],
        'taxonomy' => $provider['taxonomy'],
        'facility' => $facilityName,
        'facility_id' => $facilityId,
        'active' => $provider['active'] ? 1 : 0,
        'authorized' => $provider['authorized'] ? 1 : 0,
        'npi' => '',
    ];

    if ($existing) {
        assertSameFields(
            $expected,
            $existing,
            ['username', 'fname', 'lname', 'email', 'specialty', 'facility', 'facility_id', 'active', 'authorized', 'npi'],
            'provider'
        );
        $id = (int)$existing['id'];
        if ((string)$existing['taxonomy'] !== (string)$expected['taxonomy']) {
            $isSynthetic = str_starts_with(
                (string)($existing['info'] ?? ''),
                'SYNTHETIC_POPULATION_V1|' . $provider['provider_id'] . '|'
            );
            if (!$isSynthetic || (string)$existing['taxonomy'] !== '207Q00000X') {
                failResponse('Existing provider taxonomy cannot be safely normalized.', [
                    'provider_id' => $provider['provider_id'],
                    'expected_taxonomy' => $expected['taxonomy'],
                    'actual_taxonomy' => $existing['taxonomy'],
                ]);
            }
            sqlStatement(
                "UPDATE users SET taxonomy = ? WHERE id = ? AND username = ? AND taxonomy = '207Q00000X'",
                [$expected['taxonomy'], $id, $expected['username']]
            );
            $updated = providerByUsername($expected['username']);
            assertSameFields($expected, $updated ?: [], ['taxonomy'], 'provider taxonomy');
            $outcome = 'UPDATED';
        } else {
            $outcome = 'EXISTING';
        }
    } else {
        $uuid = UuidRegistry::getRegistryForTable('users')->createUuid();
        $id = sqlInsert(
            'INSERT INTO users '
            . '(uuid, username, authorized, fname, lname, facility, facility_id, active, specialty, taxonomy, email, phonew1, info, npi) '
            . 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            [
                $uuid,
                $expected['username'],
                $expected['authorized'],
                $expected['fname'],
                $expected['lname'],
                $facilityName,
                $facilityId,
                $expected['active'],
                $expected['specialty'],
                $expected['taxonomy'],
                $expected['email'],
                $provider['phone'],
                'SYNTHETIC_POPULATION_V1|' . $provider['provider_id'] . '|' . $provider['department_code'],
                '',
            ]
        );
        if (!$id) {
            failResponse('Provider insert failed.', ['provider_id' => $provider['provider_id']]);
        }
        $outcome = 'CREATED';
    }

    $link = sqlQuery(
        "SELECT table_id FROM users_facility WHERE tablename = 'users' AND table_id = ? AND facility_id = ? LIMIT 1",
        [$id, $facilityId]
    );
    if (!$link) {
        sqlInsert(
            "INSERT INTO users_facility (tablename, table_id, facility_id, warehouse_id) VALUES ('users', ?, ?, '')",
            [$id, $facilityId]
        );
    }

    return ['outcome' => $outcome, 'id' => (int)$id];
}

function verifyPayload(array $payload): array
{
    $facilityIds = [];
    $facilityNames = array_column($payload['facilities'], 'name', 'facility_code');
    $facilityMissing = [];
    $providerMissing = [];
    $providerLinkMissing = [];

    foreach ($payload['facilities'] as $facility) {
        $row = facilityByCode($facility['facility_code']);
        if (!$row) {
            $facilityMissing[] = $facility['facility_code'];
            continue;
        }
        assertSameFields(
            $facility,
            $row,
            ['name', 'facility_code', 'email', 'street', 'city', 'state', 'postal_code'],
            'facility'
        );
        $facilityIds[$facility['facility_code']] = (int)$row['id'];
    }

    foreach ($payload['providers'] as $provider) {
        $row = providerByUsername($provider['username']);
        if (!$row) {
            $providerMissing[] = $provider['provider_id'];
            continue;
        }
        $facilityId = $facilityIds[$provider['facility_code']] ?? 0;
        assertSameFields(
            [
                'username' => $provider['username'],
                'fname' => $provider['given_name'],
                'lname' => $provider['family_name'],
                'email' => $provider['email'],
                'specialty' => $provider['specialty'],
                'taxonomy' => $provider['taxonomy'],
                'facility' => $facilityNames[$provider['facility_code']] ?? '',
                'facility_id' => $facilityId,
                'active' => $provider['active'] ? 1 : 0,
                'authorized' => $provider['authorized'] ? 1 : 0,
                'npi' => '',
            ],
            $row,
            ['username', 'fname', 'lname', 'email', 'specialty', 'taxonomy', 'facility', 'facility_id', 'active', 'authorized', 'npi'],
            'provider'
        );
        $link = sqlQuery(
            "SELECT table_id FROM users_facility WHERE tablename = 'users' AND table_id = ? AND facility_id = ? LIMIT 1",
            [(int)$row['id'], $facilityId]
        );
        if (!$link) {
            $providerLinkMissing[] = $provider['provider_id'];
        }
    }

    return [
        'status' => (!$facilityMissing && !$providerMissing && !$providerLinkMissing) ? 'VERIFIED' : 'FAIL',
        'expected_facilities' => count($payload['facilities']),
        'resolved_facilities' => count($facilityIds),
        'expected_providers' => count($payload['providers']),
        'resolved_providers' => count($payload['providers']) - count($providerMissing),
        'facility_missing' => $facilityMissing,
        'provider_missing' => $providerMissing,
        'provider_link_missing' => $providerLinkMissing,
    ];
}

try {
    $encoded = getenv('SYNTH_MASTER_DATA_B64');
    if (!$encoded) {
        failResponse('SYNTH_MASTER_DATA_B64 is required.');
    }
    $decoded = base64_decode($encoded, true);
    $payload = json_decode((string)$decoded, true, 512, JSON_THROW_ON_ERROR);
    requireSyntheticPayload($payload);

    if (($payload['action'] ?? '') === 'verify') {
        echo json_encode(verifyPayload($payload), JSON_PRETTY_PRINT) . PHP_EOL;
        exit(0);
    }
    if (($payload['action'] ?? '') !== 'commit') {
        failResponse('Unsupported action.');
    }

    sqlStatement('START TRANSACTION');
    $transactionStarted = true;
    $facilityIds = [];
    $facilityNames = [];
    $facilityOutcomes = [];
    foreach ($payload['facilities'] as $facility) {
        $result = ensureFacility($facility);
        $facilityIds[$facility['facility_code']] = $result['id'];
        $facilityNames[$facility['facility_code']] = $facility['name'];
        $facilityOutcomes[$facility['facility_code']] = $result['outcome'];
    }

    $providerOutcomes = [];
    foreach ($payload['providers'] as $provider) {
        $result = ensureProvider($provider, $facilityIds, $facilityNames);
        $providerOutcomes[$provider['provider_id']] = $result['outcome'];
    }
    $verification = verifyPayload($payload);
    if ($verification['status'] !== 'VERIFIED') {
        failResponse('Postcondition verification failed.', $verification);
    }
    sqlStatement('COMMIT');
    $transactionStarted = false;

    echo json_encode([
        'status' => 'PASS',
        'mode' => !empty($payload['probe']) ? 'PROBE' : 'FULL',
        'facility_outcomes' => $facilityOutcomes,
        'provider_outcomes' => $providerOutcomes,
        'verification' => $verification,
    ], JSON_PRETTY_PRINT) . PHP_EOL;
} catch (Throwable $error) {
    failResponse('Unhandled master-data receiver error.', [
        'error_type' => get_class($error),
        'error' => $error->getMessage(),
    ]);
}
