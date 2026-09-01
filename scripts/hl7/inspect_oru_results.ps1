param(
    [ValidateSet(
        "Details",
        "Summary",
        "Both"
    )]
    [string]$View = "Both",

    [ValidateRange(1, 500)]
    [int]$Limit = 25,

    [ValidateRange(0, 10080)]
    [int]$RecentMinutes = 0,

    [string]$MessageControlId = "",

    [string]$Container = (
        "health-it-mirth-lab-interop-db-1"
    ),

    [string]$DatabaseUser = "interop_app",

    [string]$Database = "interop"
)

$ErrorActionPreference = "Stop"


function ConvertTo-SqlLiteral {
    param(
        [Parameter(Mandatory)]
        [string]$Value
    )

    return "'" + $Value.Replace("'", "''") + "'"
}


function Get-WhereClause {
    $conditions = @()

    if ($MessageControlId) {
        $conditions += (
            "m.message_control_id = " +
            (ConvertTo-SqlLiteral `
                -Value $MessageControlId)
        )
    }

    if ($RecentMinutes -gt 0) {
        $conditions += (
            "m.received_at >= " +
            "CURRENT_TIMESTAMP - " +
            "INTERVAL '$RecentMinutes minutes'"
        )
    }

    if ($conditions.Count -eq 0) {
        return ""
    }

    return (
        "WHERE " +
        ($conditions -join " AND ")
    )
}


function Invoke-InteropQuery {
    param(
        [Parameter(Mandatory)]
        [string]$Query
    )

    & docker exec `
        $Container `
        psql `
        -U $DatabaseUser `
        -d $Database `
        -P "pager=off" `
        -P "border=2" `
        -P "null=<NULL>" `
        -c $Query

    if ($LASTEXITCODE -ne 0) {
        throw (
            "ORU database inspection failed with " +
            "exit code $LASTEXITCODE."
        )
    }
}


$whereClause = Get-WhereClause


if ($View -in @("Details", "Both")) {
    $detailQuery = @"
SELECT
    to_char(
        m.received_at,
        'YYYY-MM-DD HH24:MI:SS'
    ) AS received,
    m.message_control_id AS msh_10,
    m.patient_identifier AS patient,
    m.placer_order_number AS placer_order,
    m.filler_order_number AS filler_order,
    m.service_code AS service,
    o.observation_code AS observation,
    o.observation_value AS value,
    o.units,
    o.reference_range AS reference,
    o.abnormal_flag AS flag,
    o.result_status,
    m.processing_status
FROM audit.oru_messages m
LEFT JOIN audit.oru_observations o
    ON o.oru_message_id = m.oru_message_id
$whereClause
ORDER BY m.received_at DESC
LIMIT $Limit;
"@

    Write-Host ""
    Write-Host "ORU RESULT DETAILS"
    Write-Host "------------------"

    Invoke-InteropQuery -Query $detailQuery
}


if ($View -in @("Summary", "Both")) {
    $summaryQuery = @"
SELECT
    o.result_status,
    o.abnormal_flag,
    COUNT(*) AS persisted_observations,
    COUNT(
        DISTINCT m.message_control_id
    ) AS distinct_transactions,
    MIN(
        CASE
            WHEN o.observation_value ~
                '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$'
            THEN o.observation_value::numeric
        END
    ) AS minimum_numeric_value,
    MAX(
        CASE
            WHEN o.observation_value ~
                '^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)$'
            THEN o.observation_value::numeric
        END
    ) AS maximum_numeric_value
FROM audit.oru_messages m
JOIN audit.oru_observations o
    ON o.oru_message_id = m.oru_message_id
$whereClause
GROUP BY
    o.result_status,
    o.abnormal_flag
ORDER BY
    o.result_status,
    o.abnormal_flag;
"@

    Write-Host ""
    Write-Host "ORU RESULT SUMMARY"
    Write-Host "------------------"

    Invoke-InteropQuery -Query $summaryQuery
}
