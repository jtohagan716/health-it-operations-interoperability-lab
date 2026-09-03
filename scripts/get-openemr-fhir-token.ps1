param(
    [string]$OpenEmrBaseUrl = "https://localhost:9300",

    [string]$RegistrationPath = (
        Join-Path $HOME ".openemr-fhir-client-registration.json"
    ),

    [string]$OutputTokenPath = (
        Join-Path $env:TEMP "openemr-fhir-token.json"
    )
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $RegistrationPath)) {
    throw "OpenEMR client registration file not found: $RegistrationPath"
}

$reg = Get-Content $RegistrationPath -Raw | ConvertFrom-Json

$redirectUri = $reg.redirect_uris[0]
$scope = $reg.scope

$normalizedBaseUrl = $OpenEmrBaseUrl.TrimEnd("/")

$fhirBase = "$normalizedBaseUrl/apis/default/fhir"
$authorizeEndpoint = "$normalizedBaseUrl/oauth2/default/authorize"
$tokenEndpoint = "$normalizedBaseUrl/oauth2/default/token"

$state = [guid]::NewGuid().ToString("N")

$authUrl = $authorizeEndpoint + "?" +
"response_type=code" +
"&client_id=$([uri]::EscapeDataString($reg.client_id))" +
"&redirect_uri=$([uri]::EscapeDataString($redirectUri))" +
"&scope=$([uri]::EscapeDataString($scope))" +
"&state=$([uri]::EscapeDataString($state))" +
"&aud=$([uri]::EscapeDataString($fhirBase))"

Write-Host ""
Write-Host "OpenEMR FHIR OAuth Authorization"
Write-Host "--------------------------------"
Write-Host "Launching authorization page..."

Start-Process $authUrl

$callbackUrl = Read-Host @"

Authorize the application in OpenEMR.

When the browser reaches the localhost:8765 callback:
  1. Press Ctrl+L
  2. Press Ctrl+C
  3. Return here
  4. Paste the callback URL
  5. Press Enter

Callback URL
"@

Add-Type -AssemblyName System.Web

$callbackUri = [uri]$callbackUrl

if (
    $callbackUri.Scheme -ne "https" -or
    $callbackUri.Host -ne "localhost" -or
    $callbackUri.Port -ne 8765 -or
    $callbackUri.AbsolutePath -ne "/callback"
) {
    throw "Unexpected OAuth callback URI."
}

$query = [System.Web.HttpUtility]::ParseQueryString(
    $callbackUri.Query
)

$code = $query["code"]
$returnedState = $query["state"]

if (-not $code) {
    throw "Authorization response did not contain a code."
}

if ($returnedState -ne $state) {
    throw "OAuth state validation failed."
}

Write-Host ""
Write-Host "Authorization code received."
Write-Host "State validation passed."
Write-Host "Exchanging authorization code immediately..."

$tokenPath = [System.IO.Path]::GetFullPath(
    $OutputTokenPath
)

curl.exe -k -sS -X POST `
    -H "Content-Type: application/x-www-form-urlencoded" `
    --data-urlencode "grant_type=authorization_code" `
    --data-urlencode "client_id=$($reg.client_id)" `
    --data-urlencode "client_secret=$($reg.client_secret)" `
    --data-urlencode "redirect_uri=$redirectUri" `
    --data-urlencode "code=$code" `
    -o "$tokenPath" `
    -w "Token HTTP %{http_code}`n" `
    $tokenEndpoint

$token = Get-Content $tokenPath -Raw | ConvertFrom-Json

if (-not $token.access_token) {
    Write-Host ""
    Write-Host "Token acquisition FAILED."

    if ($token.error) {
        Write-Host "Error: $($token.error)"
    }

    if ($token.message) {
        Write-Host "Message: $($token.message)"
    }

    if ($token.hint) {
        Write-Host "Hint: $($token.hint)"
    }

    exit 1
}

# ---------------------------------------------------------
# TOKEN LIFECYCLE METADATA
# ---------------------------------------------------------

$acquiredAtUtc = [DateTimeOffset]::UtcNow

$expiresInSeconds = [int]$token.expires_in

$expiresAtUtc = $acquiredAtUtc.AddSeconds(
    $expiresInSeconds
)

$token |
Add-Member `
    -NotePropertyName "acquired_at_utc" `
    -NotePropertyValue $acquiredAtUtc.ToString("o") `
    -Force

$token |
Add-Member `
    -NotePropertyName "expires_at_utc" `
    -NotePropertyValue $expiresAtUtc.ToString("o") `
    -Force

$token |
ConvertTo-Json -Depth 10 |
Set-Content `
    -Path $tokenPath `
    -Encoding UTF8


# ---------------------------------------------------------
# SAFE STATUS OUTPUT
# ---------------------------------------------------------

$scopeCount = (
    ($token.scope -split "\s+") |
    Where-Object { $_ }
).Count

Write-Host ""
Write-Host "Token acquisition PASSED."
Write-Host "Token type : $($token.token_type)"
Write-Host "Expires in : $expiresInSeconds seconds"
Write-Host "Scope count: $scopeCount"

Write-Host ""
Write-Host "Token lifecycle"
Write-Host "---------------"
Write-Host "Acquired UTC: $($acquiredAtUtc.ToString('o'))"
Write-Host "Expires UTC : $($expiresAtUtc.ToString('o'))"

Write-Host ""
Write-Host "Token stored temporarily at:"
Write-Host $tokenPath

Write-Host ""
Write-Host "No credential values were displayed."