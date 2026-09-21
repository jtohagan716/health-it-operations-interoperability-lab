param(
    [int]$DurationSeconds = 240,
    [int]$IntervalSeconds = 2,
    [string]$OutputDirectory = ".\artifacts\performance"
)

$ErrorActionPreference = "Stop"

$openemr = "health-it-openemr-lab-openemr-1"

New-Item -ItemType Directory -Force $OutputDirectory | Out-Null

$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")

$dataFile = Join-Path $OutputDirectory "openemr-latency-v2-$stamp.log"
$metadataFile = Join-Path $OutputDirectory "openemr-latency-v2-$stamp-metadata.txt"

@"
schema=openemr.latency.capture.v2
started_utc=$([DateTime]::UtcNow.ToString("o"))
duration_seconds=$DurationSeconds
interval_seconds=$IntervalSeconds
openemr_container=$openemr
collector=docker-exec-single-call
"@ | Set-Content $metadataFile

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$sample = 0

while ($stopwatch.Elapsed.TotalSeconds -lt $DurationSeconds) {

    $sampleWatch = [System.Diagnostics.Stopwatch]::StartNew()
    $utc = [DateTime]::UtcNow.ToString("o")

    Add-Content $dataFile ""
    Add-Content $dataFile "===== SAMPLE $sample | UTC $utc ====="

    $snapshot = docker exec $openemr sh -c '
echo "--- CPU_STAT ---"
cat /sys/fs/cgroup/cpu.stat

echo "--- MEMORY_CURRENT ---"
cat /sys/fs/cgroup/memory.current 2>/dev/null || true

echo "--- MEMORY_EVENTS ---"
cat /sys/fs/cgroup/memory.events

echo "--- LOADAVG ---"
cat /proc/loadavg

echo "--- BACKGROUND_PROCESSES ---"
ps -o pid,ppid,user,etime,stat,rss,args |
grep "background:services" |
grep -v grep || true
'

    $snapshot | Add-Content $dataFile

    $sampleWatch.Stop()

    Add-Content `
        $dataFile `
        "collector_sample_elapsed_ms=$($sampleWatch.ElapsedMilliseconds)"

    $sample++

    $remaining =
        ($IntervalSeconds * 1000) -
        [int]$sampleWatch.ElapsedMilliseconds

    if ($remaining -gt 0) {
        Start-Sleep -Milliseconds $remaining
    }
}

$stopwatch.Stop()

Add-Content `
    $metadataFile `
    "finished_utc=$([DateTime]::UtcNow.ToString("o"))"

Add-Content `
    $metadataFile `
    "actual_duration_seconds=$([math]::Round($stopwatch.Elapsed.TotalSeconds, 3))"

Add-Content `
    $metadataFile `
    "samples=$sample"

Write-Host ""
Write-Host "Capture complete."
Write-Host "Metadata : $metadataFile"
Write-Host "Data     : $dataFile"