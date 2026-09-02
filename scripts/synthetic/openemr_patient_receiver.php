<?php

declare(strict_types=1);

use OpenEMR\Services\PatientService;

$ignoreAuth = true;
$_GET['site'] = 'default';
error_reporting(E_ALL & ~E_DEPRECATED);
ini_set('display_errors', '0');

require_once '/var/www/localhost/htdocs/openemr/interface/globals.php';

header('Content-Type: application/json');
$transactionStarted = false;

function failPatientResponse(string $message, array $context = []): never
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

function requirePatientPayload(array $payload): void
{
    $allowedSex = ['Male', 'Female'];
    $allowedRace = ['white', 'black_or_afri_amer', 'Asian', 'amer_ind_or_alaska_native', 'native_hawai_or_pac_island', 'decline_to_specify'];
    $allowedEthnicity = ['not_hisp_or_latin', 'hisp_or_latin', 'decline_to_specify'];
    $allowedLanguage = ['English', 'Spanish', 'french', 'arabic', 'chinese'];
    $allowedMarital = ['single', 'married', 'divorced', 'widowed', 'separated', 'domestic partner'];
    if (($payload['environment'] ?? '') !== 'local-lab') {
        failPatientResponse('Environment must be local-lab.');
    }
    if (($payload['synthetic_only'] ?? false) !== true) {
        failPatientResponse('synthetic_only must be true.');
    }
    if (($payload['source_system'] ?? '') !== 'SYNTHETIC_POPULATION_V1') {
        failPatientResponse('Unexpected source system.');
    }
    if (($payload['assigning_authority'] ?? '') !== 'INTEROPLAB') {
        failPatientResponse('Unexpected assigning authority.');
    }
    if (($payload['identifier_type'] ?? '') !== 'MR') {
        failPatientResponse('Unexpected identifier type.');
    }
    $patientCount = count($payload['patients'] ?? []);
    if ($patientCount !== 1 && $patientCount !== 100) {
        failPatientResponse('Payload must contain exactly one probe patient or 100 full patients.');
    }
    foreach ($payload['patients'] as $patient) {
        if (!preg_match('/^SYNTHMRN\d{6}$/', (string)($patient['patient_id'] ?? ''))) {
            failPatientResponse('Patient outside synthetic identifier namespace.');
        }
        if (!str_ends_with((string)($patient['email'] ?? ''), '@example.invalid')) {
            failPatientResponse('Patient email outside synthetic namespace.');
        }
        if (!preg_match('/^716-555-01\d{2}$/', (string)($patient['phone'] ?? ''))) {
            failPatientResponse('Patient phone outside reserved fictional range.');
        }
        if (!preg_match('/^synprov\d{4}$/', (string)($patient['provider_username'] ?? ''))) {
            failPatientResponse('Provider outside synthetic namespace.');
        }
        if (!in_array($patient['administrative_sex'] ?? '', $allowedSex, true)
            || !in_array($patient['race'] ?? '', $allowedRace, true)
            || !in_array($patient['ethnicity'] ?? '', $allowedEthnicity, true)
            || !in_array($patient['language'] ?? '', $allowedLanguage, true)
            || !in_array($patient['marital_status'] ?? '', $allowedMarital, true)) {
            failPatientResponse('Patient contains an unsupported OpenEMR demographic option.');
        }
        foreach (['ss', 'drivers_license', 'portal_password'] as $forbidden) {
            if (array_key_exists($forbidden, $patient)) {
                failPatientResponse("Forbidden patient identity field: {$forbidden}.");
            }
        }
    }
}

function providerForPatient(array $patient): array
{
    $provider = sqlQuery(
        "SELECT id, username, facility_id, info FROM users WHERE username = ? AND active = 1 LIMIT 1",
        [$patient['provider_username']]
    );
    if (!$provider
        || !str_starts_with((string)($provider['username'] ?? ''), 'synprov')
        || !str_starts_with((string)($provider['info'] ?? ''), 'SYNTHETIC_POPULATION_V1|')) {
        failPatientResponse('Required synthetic provider was not found.', [
            'provider_username' => $patient['provider_username'],
        ]);
    }
    return $provider;
}

function patientRowsByPublicId(string $publicId): array
{
    $statement = sqlStatement(
        'SELECT pid, uuid, pubpid, fname, mname, lname, DOB, sex, street, city, state, postal_code, '
        . 'country_code, phone_home, email, race, ethnicity, language, status, providerID, '
        . 'usertext1, usertext2, usertext3, usertext4 '
        . 'FROM patient_data WHERE pubpid = ?',
        [$publicId]
    );
    $rows = [];
    while ($row = sqlFetchArray($statement)) {
        $rows[] = $row;
    }
    return $rows;
}

function expectedPatientRecord(array $patient, int $providerId): array
{
    return [
        'pubpid' => $patient['patient_id'],
        'fname' => $patient['given_name'],
        'mname' => $patient['middle_name'],
        'lname' => $patient['family_name'],
        'DOB' => $patient['birth_date'],
        'sex' => $patient['administrative_sex'],
        'street' => $patient['street'],
        'city' => $patient['city'],
        'state' => $patient['state'],
        'postal_code' => $patient['postal_code'],
        'country_code' => $patient['country_code'],
        'phone_home' => $patient['phone'],
        'email' => $patient['email'],
        'race' => $patient['race'],
        'ethnicity' => $patient['ethnicity'],
        'language' => $patient['language'],
        'status' => $patient['marital_status'],
        'providerID' => $providerId,
        'usertext1' => 'SYNTHETIC_POPULATION_V1',
        'usertext2' => $patient['logical_key'],
        'usertext3' => implode(',', $patient['cohort_codes']),
        'usertext4' => $patient['golden_patient'] ? 'GOLDEN' : 'VOLUME',
    ];
}

function assertPatientFields(array $expected, array $actual, string $publicId): void
{
    $mismatches = [];
    foreach ($expected as $field => $value) {
        if ((string)$value !== (string)($actual[$field] ?? '')) {
            $mismatches[$field] = [
                'expected' => $value,
                'actual' => $actual[$field] ?? null,
            ];
        }
    }
    if ($mismatches) {
        failPatientResponse('Existing patient conflicts with deterministic fixture.', [
            'patient_id' => $publicId,
            'mismatches' => $mismatches,
        ]);
    }
}

function ensurePatient(array $patient, PatientService $patientService): array
{
    $provider = providerForPatient($patient);
    $expected = expectedPatientRecord($patient, (int)$provider['id']);
    $rows = patientRowsByPublicId($patient['patient_id']);
    if (count($rows) > 1) {
        failPatientResponse('Duplicate public patient identifier detected.', [
            'patient_id' => $patient['patient_id'],
            'count' => count($rows),
        ]);
    }
    if (count($rows) === 1) {
        assertPatientFields($expected, $rows[0], $patient['patient_id']);
        return [
            'outcome' => 'EXISTING',
            'pid' => (int)$rows[0]['pid'],
        ];
    }

    $result = $patientService->insert($expected);
    if (!$result->isValid() || empty($result->getData())) {
        $context = [];
        if (method_exists($result, 'getValidationMessages')) {
            $context['validation_messages'] = $result->getValidationMessages();
        }
        if (method_exists($result, 'getInternalErrors')) {
            $context['internal_errors'] = $result->getInternalErrors();
        }
        failPatientResponse('OpenEMR PatientService insert failed.', array_merge([
            'patient_id' => $patient['patient_id'],
        ], $context));
    }
    $created = $result->getData()[0];
    $rows = patientRowsByPublicId($patient['patient_id']);
    if (count($rows) !== 1) {
        failPatientResponse('Patient post-insert lookup did not resolve exactly one row.', [
            'patient_id' => $patient['patient_id'],
        ]);
    }
    assertPatientFields($expected, $rows[0], $patient['patient_id']);
    return [
        'outcome' => 'CREATED',
        'pid' => (int)$rows[0]['pid'],
        'uuid' => $created['uuid'] ?? null,
    ];
}

function verifyPatients(array $payload): array
{
    $missing = [];
    $verified = 0;
    $pids = [];
    foreach ($payload['patients'] as $patient) {
        $provider = providerForPatient($patient);
        $expected = expectedPatientRecord($patient, (int)$provider['id']);
        $rows = patientRowsByPublicId($patient['patient_id']);
        if (count($rows) === 0) {
            $missing[] = $patient['patient_id'];
            continue;
        }
        if (count($rows) > 1) {
            failPatientResponse('Duplicate public patient identifier detected during verification.', [
                'patient_id' => $patient['patient_id'],
                'count' => count($rows),
            ]);
        }
        assertPatientFields($expected, $rows[0], $patient['patient_id']);
        $pids[] = (int)$rows[0]['pid'];
        $verified++;
    }
    return [
        'status' => empty($missing) && count(array_unique($pids)) === count($pids) ? 'VERIFIED' : 'FAIL',
        'expected_patients' => count($payload['patients']),
        'resolved_patients' => $verified,
        'unique_internal_pids' => count(array_unique($pids)),
        'missing_patients' => $missing,
    ];
}

try {
    $encoded = '__SYNTH_PATIENT_PAYLOAD_BASE64__';
    $decoded = base64_decode($encoded, true);
    if ($decoded === false) {
        failPatientResponse('Embedded payload is not valid base64.');
    }
    $payload = json_decode($decoded, true, 512, JSON_THROW_ON_ERROR);
    requirePatientPayload($payload);

    if (($payload['action'] ?? '') === 'verify') {
        echo json_encode(verifyPatients($payload), JSON_PRETTY_PRINT) . PHP_EOL;
        exit(0);
    }
    if (($payload['action'] ?? '') !== 'commit') {
        failPatientResponse('Unsupported action.');
    }

    sqlStatement('START TRANSACTION');
    $transactionStarted = true;
    $service = new PatientService();
    $outcomes = [];
    foreach ($payload['patients'] as $patient) {
        $result = ensurePatient($patient, $service);
        $outcomes[$patient['patient_id']] = $result['outcome'];
    }
    $verification = verifyPatients($payload);
    if ($verification['status'] !== 'VERIFIED') {
        failPatientResponse('Patient postcondition verification failed.', $verification);
    }
    sqlStatement('COMMIT');
    $transactionStarted = false;

    echo json_encode([
        'status' => 'PASS',
        'mode' => !empty($payload['probe']) ? 'PROBE' : 'FULL',
        'patient_outcomes' => $outcomes,
        'verification' => $verification,
    ], JSON_PRETTY_PRINT) . PHP_EOL;
} catch (Throwable $error) {
    failPatientResponse('Unhandled patient receiver error.', [
        'error_type' => get_class($error),
        'error' => $error->getMessage(),
    ]);
}
