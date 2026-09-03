param(
    [string]$OpenEmrBaseUrl = "https://localhost:9300",

    [string]$RegistrationPath = (
        Join-Path $HOME ".openemr-fhir-client-registration.json"
    ),

    [string]$RedirectUri = "https://localhost:8765/callback"
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------
# LOCAL LAB TLS HANDLING
# ---------------------------------------------------------
# OpenEMR uses a self-signed certificate in this local lab.
# Do not use this certificate bypass for production systems.

[System.Net.ServicePointManager]::ServerCertificateValidationCallback = {
    $true
}

# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

$normalizedBaseUrl = $OpenEmrBaseUrl.TrimEnd("/")

$registrationEndpoint = (
    "$normalizedBaseUrl/oauth2/default/registration"
)

$scopes = @(
    "openid",
    "fhirUser",
    "online_access",
    "api:fhir",
    "user/Patient.rs",
    "user/Encounter.rs",
    "user/Observation.rs",
    "user/DiagnosticReport.rs",
    "user/Condition.rs",
    "user/MedicationRequest.rs",
    "user/Medication.rs",
    "user/Practitioner.rs",
    "user/Organization.rs"
)

$scope = $scopes -join " "

# ---------------------------------------------------------
# REGISTRATION PAYLOAD
# ---------------------------------------------------------

$registrationObject = @{
    application_type           = "private"
    client_name                = "Healthcare Interoperability Lab FHIR Client"
    redirect_uris              = @(
        $RedirectUri
    )
    token_endpoint_auth_method = "client_secret_post"
    scope                      = $scope
}

$payload = $registrationObject |
ConvertTo-Json -Depth 10

# ---------------------------------------------------------
# STATUS
# ---------------------------------------------------------

Write-Host ""
Write-Host "Registering OpenEMR SMART/FHIR client..."
Write-Host "Requested scope count: $($scopes.Count)"
Write-Host ""

# ---------------------------------------------------------
# DYNAMIC CLIENT REGISTRATION
# ---------------------------------------------------------

$response = Invoke-RestMethod `
    -Uri $registrationEndpoint `
    -Method Post `
    -ContentType "application/json" `
    -Body $payload

# ---------------------------------------------------------
# VALIDATE RESPONSE
# ---------------------------------------------------------

if (-not $response.client_id) {
    throw "OpenEMR registration response did not contain client_id."
}

if (-not $response.client_secret) {
    throw "OpenEMR registration response did not contain client_secret."
}

# ---------------------------------------------------------
# SAVE REGISTRATION OUTSIDE GIT REPOSITORY
# ---------------------------------------------------------

$response |
ConvertTo-Json -Depth 20 |
Set-Content `
    -Path $registrationPath `
    -Encoding UTF8

# ---------------------------------------------------------
# SAFE OUTPUT
# ---------------------------------------------------------

Write-Host "Client registration PASSED."
Write-Host "Client name : $($response.client_name)"
Write-Host "Client ID   : $($response.client_id)"
Write-Host "Saved to    : $registrationPath"

Write-Host ""
Write-Host "Registered scopes"
Write-Host "-----------------"

$response.scope -split "\s+" |
Where-Object { $_ } |
Sort-Object |
ForEach-Object {
    Write-Host $_
}

Write-Host ""
Write-Host "Client secret and registration access token were saved"
Write-Host "to the registration file and were not printed."