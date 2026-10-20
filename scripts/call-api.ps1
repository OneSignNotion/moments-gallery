# 绕过系统代理调用 moments 后端 API
# 用法: .\call-api.ps1 -Path "/api/archive/import" -BodyFile "data\payload.json"

param(
  [Parameter(Mandatory=$true)][string]$Path,
  [string]$BodyFile = "",
  [string]$Body = ""
)

$env:NO_PROXY = "*"
Remove-Item Env:http_proxy, Env:https_proxy, Env:HTTP_PROXY, Env:HTTPS_PROXY -ErrorAction SilentlyContinue

$api = $env:MOMENTS_API
if (-not $api) {
  $local = Join-Path $PSScriptRoot "sync.local.cmd"
  if (Test-Path $local) {
    foreach ($line in Get-Content $local) {
      if ($line -match 'set MOMENTS_API=(.+)') { $api = $Matches[1].Trim() }
      if ($line -match 'set MOMENTS_TOKEN=(.+)') { $token = $Matches[1].Trim() }
    }
  }
}
if (-not $api) { $api = "https://moments-backend.ityourknow.workers.dev" }

if (-not $token) {
  $tf = Join-Path $PSScriptRoot "token.txt"
  if (Test-Path $tf) { $token = (Get-Content $tf -Raw).Trim() }
}
if (-not $token) { throw "No token found. Set MOMENTS_TOKEN or create token.txt" }

if ($BodyFile -and (Test-Path $BodyFile)) {
  $Body = Get-Content $BodyFile -Raw
}
if (-not $Body) { $Body = "{}" }

try {
  $r = Invoke-RestMethod -Uri "$api$Path" -Method POST `
        -Body $Body -ContentType "application/json" `
        -Headers @{ "X-API-TOKEN" = $token } -TimeoutSec 120
  $r | ConvertTo-Json -Depth 6 -Compress
} catch {
  Write-Error "API call failed: $($_.Exception.Message)"
  exit 1
}