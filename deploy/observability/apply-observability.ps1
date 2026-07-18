param(
    [string]$ProjectId = "project-5d300c02-d165-4037-b6f"
)

$ErrorActionPreference = "Stop"
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$token = gcloud auth print-access-token
$headers = @{ Authorization = "Bearer $token" }

function Invoke-GcpJson {
    param([string]$Uri, [string]$Method, [string]$Body)
    try {
        return Invoke-RestMethod -Uri $Uri -Headers $headers -Method $Method -ContentType "application/json" -Body $Body
    }
    catch {
        $details = $_.ErrorDetails.Message
        if (-not $details -and $_.Exception.Response) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $details = $reader.ReadToEnd()
        }
        throw "GCP API request failed: $Method $Uri`n$details"
    }
}

$metrics = Get-Content (Join-Path $scriptDirectory "log-metrics.json") -Raw | ConvertFrom-Json
foreach ($metric in $metrics) {
    $uri = "https://logging.googleapis.com/v2/projects/$ProjectId/metrics/$($metric.name)"
    $body = $metric | ConvertTo-Json -Depth 20 -Compress
    Invoke-GcpJson -Uri $uri -Method Put -Body $body | Out-Null
    Write-Output "Applied log metric: $($metric.name)"
}

$monitoringBase = "https://monitoring.googleapis.com/v3/projects/$ProjectId"
$channels = (Invoke-RestMethod -Uri "$monitoringBase/notificationChannels" -Headers $headers).notificationChannels
$channel = $channels | Where-Object { $_.displayName -eq "Athena operations email" } | Select-Object -First 1
if (-not $channel) {
    throw "Notification channel 'Athena operations email' was not found."
}

$existingPolicies = (Invoke-RestMethod -Uri "$monitoringBase/alertPolicies" -Headers $headers).alertPolicies
$policies = Get-Content (Join-Path $scriptDirectory "alert-policies.json") -Raw | ConvertFrom-Json
foreach ($policy in $policies) {
    $policy | Add-Member -NotePropertyName notificationChannels -NotePropertyValue @($channel.name) -Force
    $existing = $existingPolicies | Where-Object { $_.displayName -eq $policy.displayName } | Select-Object -First 1
    if ($existing) {
        $policy | Add-Member -NotePropertyName name -NotePropertyValue $existing.name -Force
        $uri = "https://monitoring.googleapis.com/v3/$($existing.name)?updateMask=displayName,documentation,conditions,combiner,enabled,notificationChannels,alertStrategy"
        $method = "Patch"
    } else {
        $uri = "$monitoringBase/alertPolicies"
        $method = "Post"
    }
    $body = $policy | ConvertTo-Json -Depth 20 -Compress
    Invoke-GcpJson -Uri $uri -Method $method -Body $body | Out-Null
    Write-Output "Applied alert policy: $($policy.displayName)"
}

$dashboardFile = Join-Path $scriptDirectory "deep-observability-dashboard.json"
$dashboardId = gcloud monitoring dashboards list --project=$ProjectId --filter="displayName='Athena Agent and Product Observability'" --format="value(name.basename())" --limit=1
if ($dashboardId) {
    gcloud monitoring dashboards update $dashboardId --project=$ProjectId --config-from-file=$dashboardFile --quiet | Out-Null
}
else {
    gcloud monitoring dashboards create --project=$ProjectId --config-from-file=$dashboardFile --quiet | Out-Null
}
Write-Output "Applied dashboard: Athena Agent and Product Observability"
