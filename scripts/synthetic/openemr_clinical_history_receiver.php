<?php

declare(strict_types=1);

/**
 * Guarded OpenEMR receiver for deterministic synthetic clinical history.
 *
 * Supports:
 *   - verify: read-only existence and reconciliation checks
 *   - commit: guarded, idempotent provisioning for exactly one
 *             synthetic patient
 *
 * Synthetic records are identified by stable external_id values.
 * Commit inserts records only when the corresponding synthetic
 * external_id is absent. Existing records are reconciled rather
 * than duplicated.
 */

use OpenEMR\Common\Database\QueryUtils;


/*
 * Bootstrap OpenEMR using the same CLI context established by
 * OpenEMR's bin/console entry point.
 *
 * This receiver runs inside the local synthetic lab container
 * as the OpenEMR web user (apache).
 */
$_GET['site'] = 'default';
$ignoreAuth = true;
$sessionAllowWrite = true;

require_once '/var/www/localhost/htdocs/openemr/interface/globals.php';


const APPROVED_ENVIRONMENT = 'local-lab';
const APPROVED_SOURCE_SYSTEM = 'SYNTHETIC_POPULATION_V1';
const APPROVED_MRN_PREFIX = 'SYNTHMRN';

const APPROVED_ACTIONS = [
    'verify',
    'commit',
];

const APPROVED_ENTITY_TYPES = [
    'medication',
    'allergy',
    'immunization',
];

$encodedPayload = '__PAYLOAD_BASE64__';


function failResponse(string $message): never
{
    echo json_encode(
        [
            'status' => 'FAIL',
            'message' => $message,
        ],
        JSON_PRETTY_PRINT
    );

    exit(1);
}


function validatePayload(array $payload): void
{
    $action = $payload['action'] ?? null;

    if (
        !is_string($action)
        || !in_array(
            $action,
            APPROVED_ACTIONS,
            true
        )
    ) {
        failResponse(
            'Receiver action is not approved.'
        );
    }

    if (
        ($payload['environment'] ?? null)
        !== APPROVED_ENVIRONMENT
    ) {
        failResponse(
            'Payload environment is not approved.'
        );
    }

    if (($payload['synthetic_only'] ?? null) !== true) {
        failResponse(
            'Payload must declare synthetic_only=true.'
        );
    }

    if (
        ($payload['source_system'] ?? null)
        !== APPROVED_SOURCE_SYSTEM
    ) {
        failResponse(
            'Payload source system is not approved.'
        );
    }

    if (
        !isset($payload['records'])
        || !is_array($payload['records'])
        || count($payload['records']) === 0
    ) {
        failResponse(
            'Payload contains no clinical-history records.'
        );
    }

    $mrns = [];

    foreach ($payload['records'] as $record) {
        if (!is_array($record)) {
            failResponse(
                'Clinical-history record must be an object.'
            );
        }

        $entityType = $record['entity_type'] ?? '';

        if (
            !is_string($entityType)
            || !in_array(
                $entityType,
                APPROVED_ENTITY_TYPES,
                true
            )
        ) {
            failResponse(
                'Record has an unsupported entity type.'
            );
        }

        $mrn = $record['mrn'] ?? '';

        if (
            !is_string($mrn)
            || !str_starts_with(
                $mrn,
                APPROVED_MRN_PREFIX
            )
        ) {
            failResponse(
                'Record is outside the synthetic MRN namespace.'
            );
        }

        $mrns[$mrn] = true;

        $logicalKey = $record['logical_key'] ?? '';

        if (
            !is_string($logicalKey)
            || !preg_match(
                '/^SYN(MED|ALG|IMM)[0-9]{8}$/',
                $logicalKey
            )
        ) {
            failResponse(
                'Record has an invalid synthetic logical key.'
            );
        }

        $externalId = $record['external_id'] ?? '';

        if (
            !is_string($externalId)
            || $externalId !== $logicalKey
        ) {
            failResponse(
                'Record external_id must equal logical_key.'
            );
        }

        $expectedPrefix = match ($entityType) {
            'medication' => 'SYNMED',
            'allergy' => 'SYNALG',
            'immunization' => 'SYNIMM',
        };

        if (!str_starts_with(
            $logicalKey,
            $expectedPrefix
        )) {
            failResponse(
                'Logical-key namespace does not match entity type.'
            );
        }

        if (
            ($record['source_system'] ?? null)
            !== APPROVED_SOURCE_SYSTEM
        ) {
            failResponse(
                'Record source system is not approved.'
            );
        }
    }

    /*
     * Commit is intentionally restricted to exactly one patient.
     * This is an independent receiver-side safety boundary.
     */
    if (
        $action === 'commit'
        && count($mrns) !== 1
    ) {
        failResponse(
            'Commit payload must contain exactly one synthetic patient.'
        );
    }
}


function resolvePatient(string $mrn): array
{
    $rows = QueryUtils::fetchRecords(
        '
        SELECT
            pid,
            pubpid,
            HEX(uuid) AS patient_uuid
        FROM patient_data
        WHERE pubpid = ?
        ',
        [$mrn]
    );

    if (count($rows) !== 1) {
        failResponse(
            "Expected exactly one OpenEMR patient for MRN {$mrn}; "
            . 'found '
            . count($rows)
            . '.'
        );
    }

    return $rows[0];
}


function existingRecordCount(
    string $entityType,
    int $pid,
    string $externalId
): int {
    switch ($entityType) {
        case 'medication':
            $sql = '
                SELECT COUNT(*) AS record_count
                FROM prescriptions
                WHERE patient_id = ?
                  AND external_id = ?
            ';
            break;

        case 'allergy':
            $sql = "
                SELECT COUNT(*) AS record_count
                FROM lists
                WHERE pid = ?
                  AND type = 'allergy'
                  AND external_id = ?
            ";
            break;

        case 'immunization':
            $sql = '
                SELECT COUNT(*) AS record_count
                FROM immunizations
                WHERE patient_id = ?
                  AND external_id = ?
            ';
            break;

        default:
            failResponse(
                "Unsupported entity type: {$entityType}"
            );
    }

    $rows = QueryUtils::fetchRecords(
        $sql,
        [
            $pid,
            $externalId,
        ]
    );

    if (count($rows) !== 1) {
        failResponse(
            "Unable to reconcile {$entityType} {$externalId}."
        );
    }

    return (int) $rows[0]['record_count'];
}


function requireString(
    array $record,
    string $field
): string {
    $value = $record[$field] ?? null;

    if (
        !is_string($value)
        || trim($value) === ''
    ) {
        failResponse(
            "Record {$record['logical_key']} "
            . "requires field {$field}."
        );
    }

    return $value;
}


function optionalString(
    array $record,
    string $field
): ?string {
    $value = $record[$field] ?? null;

    if ($value === null || $value === '') {
        return null;
    }

    if (!is_string($value)) {
        failResponse(
            "Record {$record['logical_key']} "
            . "has invalid field {$field}."
        );
    }

    return $value;
}


function insertMedication(
    int $pid,
    array $record
): void {
    $drug = requireString(
        $record,
        'drug'
    );

    $externalId = requireString(
        $record,
        'external_id'
    );

    $startDate = requireString(
        $record,
        'start_date'
    );

    $dosage = optionalString(
        $record,
        'dosage'
    );

    $quantity = optionalString(
        $record,
        'quantity'
    );

    $route = optionalString(
        $record,
        'route'
    );

    $rxnorm = optionalString(
        $record,
        'rxnorm'
    );

    $indication = optionalString(
        $record,
        'indication'
    );

    $diagnosis = optionalString(
        $record,
        'diagnosis'
    );

    QueryUtils::sqlStatementThrowException(
        '
        INSERT INTO prescriptions
        (
            patient_id,
            date_added,
            date_modified,
            start_date,
            drug,
            rxnorm_drugcode,
            dosage,
            quantity,
            route,
            refills,
            active,
            external_id,
            indication,
            diagnosis,
            usage_category,
            usage_category_title,
            request_intent,
            request_intent_title,
            txDate
        )
        VALUES
        (
            ?,
            NOW(),
            NOW(),
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            0,
            1,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )
        ',
        [
            $pid,
            $startDate,
            $drug,
            $rxnorm,
            $dosage,
            $quantity,
            $route,
            $externalId,
            $indication,
            $diagnosis,
            'outpatient',
            'Outpatient',
            'order',
            'Order',
            $startDate,
        ]
    );
}


function insertAllergy(
    int $pid,
    array $record
): void {
    $title = requireString(
        $record,
        'title'
    );

    $externalId = requireString(
        $record,
        'external_id'
    );

    $begdate = requireString(
        $record,
        'begdate'
    );

    $reaction = optionalString(
        $record,
        'reaction'
    ) ?? 'unassigned';

    $verification = optionalString(
        $record,
        'verification'
    ) ?? 'unassigned';

    $severity = optionalString(
        $record,
        'severity'
    );

    QueryUtils::sqlStatementThrowException(
        "
        INSERT INTO lists
        (
            date,
            type,
            subtype,
            title,
            begdate,
            activity,
            pid,
            outcome,
            reinjury_id,
            injury_part,
            injury_type,
            injury_grade,
            reaction,
            verification,
            erx_source,
            erx_uploaded,
            severity_al,
            external_id
        )
        VALUES
        (
            NOW(),
            'allergy',
            '',
            ?,
            ?,
            1,
            ?,
            0,
            0,
            '',
            '',
            '',
            ?,
            ?,
            '0',
            '0',
            ?,
            ?
        )
        ",
        [
            $title,
            $begdate,
            $pid,
            $reaction,
            $verification,
            $severity,
            $externalId,
        ]
    );
}


function insertImmunization(
    int $pid,
    array $record
): void {
    $externalId = requireString(
        $record,
        'external_id'
    );

    $administeredDate = requireString(
        $record,
        'administered_date'
    );

    $cvx = requireString(
        $record,
        'cvx'
    );

    QueryUtils::sqlStatementThrowException(
        '
        INSERT INTO immunizations
        (
            patient_id,
            administered_date,
            cvx_code,
            note,
            create_date,
            update_date,
            external_id,
            completion_status,
            information_source
        )
        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            NOW(),
            NOW(),
            ?,
            ?,
            ?
        )
        ',
        [
            $pid,
            $administeredDate,
            $cvx,
            'Deterministic synthetic clinical-history record.',
            $externalId,
            'completed',
            'historical',
        ]
    );
}


function insertRecord(
    string $entityType,
    int $pid,
    array $record
): void {
    switch ($entityType) {
        case 'medication':
            insertMedication(
                $pid,
                $record
            );
            return;

        case 'allergy':
            insertAllergy(
                $pid,
                $record
            );
            return;

        case 'immunization':
            insertImmunization(
                $pid,
                $record
            );
            return;

        default:
            failResponse(
                "Unsupported entity type: {$entityType}"
            );
    }
}


function verifyRecords(array $records): array
{
    $results = [];

    foreach ($records as $record) {
        $patient = resolvePatient(
            $record['mrn']
        );

        $existingCount = existingRecordCount(
            $record['entity_type'],
            (int) $patient['pid'],
            $record['external_id']
        );

        $results[] = [
            'entity_type' => $record['entity_type'],
            'logical_key' => $record['logical_key'],
            'mrn' => $record['mrn'],
            'pid' => (int) $patient['pid'],
            'existing_count' => $existingCount,
        ];
    }

    return $results;
}


function commitRecords(array $records): array
{
    $results = [];

    foreach ($records as $record) {
        $patient = resolvePatient(
            $record['mrn']
        );

        $pid = (int) $patient['pid'];
        $entityType = $record['entity_type'];
        $externalId = $record['external_id'];

        $beforeCount = existingRecordCount(
            $entityType,
            $pid,
            $externalId
        );

        if ($beforeCount > 1) {
            failResponse(
                "Duplicate synthetic record already exists: "
                . "{$externalId}; count={$beforeCount}."
            );
        }

        $operation = 'reconciled';

        if ($beforeCount === 0) {
            insertRecord(
                $entityType,
                $pid,
                $record
            );

            $operation = 'inserted';
        }

        $afterCount = existingRecordCount(
            $entityType,
            $pid,
            $externalId
        );

        if ($afterCount !== 1) {
            failResponse(
                "Post-write reconciliation failed for "
                . "{$externalId}; expected 1, found "
                . "{$afterCount}."
            );
        }

        $results[] = [
            'entity_type' => $entityType,
            'logical_key' => $record['logical_key'],
            'mrn' => $record['mrn'],
            'pid' => $pid,
            'before_count' => $beforeCount,
            'after_count' => $afterCount,
            'operation' => $operation,
        ];
    }

    return $results;
}


$decoded = base64_decode(
    $encodedPayload,
    true
);

if ($decoded === false) {
    failResponse(
        'Payload is not valid base64.'
    );
}

$payload = json_decode(
    $decoded,
    true
);

if (!is_array($payload)) {
    failResponse(
        'Payload is not valid JSON.'
    );
}

validatePayload(
    $payload
);

$action = $payload['action'];

try {
    if ($action === 'verify') {
        $verifiedRecords = verifyRecords(
            $payload['records']
        );

        echo json_encode(
            [
                'status' => 'VERIFIED',
                'action' => 'verify',
                'record_count' => count(
                    $verifiedRecords
                ),
                'records' => $verifiedRecords,
            ],
            JSON_PRETTY_PRINT
        );

        exit(0);
    }

    $committedRecords = commitRecords(
        $payload['records']
    );

    $inserted = count(
        array_filter(
            $committedRecords,
            static fn(array $record): bool =>
                $record['operation'] === 'inserted'
        )
    );

    $reconciled = count(
        array_filter(
            $committedRecords,
            static fn(array $record): bool =>
                $record['operation'] === 'reconciled'
        )
    );

    echo json_encode(
        [
            'status' => 'COMMITTED',
            'action' => 'commit',
            'record_count' => count(
                $committedRecords
            ),
            'inserted' => $inserted,
            'reconciled' => $reconciled,
            'records' => $committedRecords,
        ],
        JSON_PRETTY_PRINT
    );

    exit(0);
} catch (Throwable $exception) {
    failResponse(
        'OpenEMR clinical-history operation failed: '
        . $exception->getMessage()
    );
}