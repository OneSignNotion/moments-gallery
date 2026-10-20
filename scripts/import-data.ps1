# 导入媒体到 git 仓库（图片走 LFS，元数据写 D1）
#
# 用法:
#   powershell -File import-data.ps1 -Author 4KAestheticHQ -Limit 10
#   powershell -File import-data.ps1 -Author 4KAestheticHQ -AllDates
#
# 流程: 复制文件到 frontend/public/media -> git commit/push
#       -> Cloudflare Pages 自动构建部署
#       -> 写 D1 元数据

param(
  [string]$Author = "4KAestheticHQ",
  [int]$Limit = 0,
  [switch]$AllDates,
  [string]$Date = "",
  [switch]$SkipPush
)

$ErrorActionPreference = "Stop"
$env:NO_PROXY = "*"
Remove-Item Env:http_proxy, Env:https_proxy, Env:HTTP_PROXY, Env:HTTPS_PROXY -ErrorAction SilentlyContinue

$root = Split-Path $PSScriptRoot -Parent
$mediaRoot = Join-Path $root "frontend\public\media"
$srcRoot = "D:\Devops\TwitterPhoto\$Author"
$api = "https://moments-backend.ityourknow.workers.dev"
$token = (Get-Content (Join-Path $root "data\token.txt") -Raw).Trim()

if (-not (Test-Path $srcRoot)) { throw "Source not found: $srcRoot" }

$mediaExts = @(".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".m4v", ".webm")

$dateDirs = Get-ChildItem $srcRoot -Directory | Sort-Object Name -Descending
if ($Date) { $dateDirs = $dateDirs | Where-Object { $_.Name -eq $Date } }
elseif (-not $AllDates) { $dateDirs = $dateDirs | Select-Object -First 1 }

$copied = 0
$totalTweets = 0
$totalImported = 0
$totalSkipped = 0

foreach ($dd in $dateDirs) {
  $date = $dd.Name
  Write-Host "`n=== $date ==="

  $tweetDirs = @(Get-ChildItem $dd.FullName -Directory -ErrorAction SilentlyContinue)
  $loose = @(Get-ChildItem $dd.FullName -File -ErrorAction SilentlyContinue |
             Where-Object { $mediaExts -contains $_.Extension.ToLower() })

  $payloadTweets = @()

  if ($tweetDirs.Count -gt 0) {
    foreach ($td in $tweetDirs) {
      $files = @(Get-ChildItem $td.FullName -File | Where-Object { $mediaExts -contains $_.Extension.ToLower() })
      if ($files.Count -eq 0) { continue }

      $keys = @()
      foreach ($f in $files) {
        $rel = "$Author/$date/$($td.Name)/$($f.Name)"
        $dest = Join-Path $mediaRoot $rel
        if (-not (Test-Path $dest)) {
          New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
          Copy-Item $f.FullName $dest
          $copied++
        }
        $keys += "/media/$rel"
      }
      if ($keys.Count -gt 0) {
        $payloadTweets += @{
          tweetId   = $td.Name
          createdAt = "${date}T12:00:00.000Z"
          content   = ""
          imgs      = $keys
          tags      = @($Author)
        }
      }
    }
  } elseif ($loose.Count -gt 0) {
    $keys = @()
    foreach ($f in $loose) {
      $rel = "$Author/$date/$($f.Name)"
      $dest = Join-Path $mediaRoot $rel
      if (-not (Test-Path $dest)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
        Copy-Item $f.FullName $dest
        $copied++
      }
      $keys += "/media/$rel"
    }
    if ($keys.Count -gt 0) {
      $payloadTweets += @{
        tweetId   = "$date-0"
        createdAt = "${date}T12:00:00.000Z"
        content   = ""
        imgs      = $keys
        tags      = @($Author)
      }
    }
  }

  if ($payloadTweets.Count -eq 0) { Write-Host "  no media"; continue }

  if ($Limit -gt 0 -and ($totalTweets + $payloadTweets.Count) -gt $Limit) {
    $payloadTweets = $payloadTweets[0..($Limit - $totalTweets - 1)]
  }
  $totalTweets += $payloadTweets.Count

  $body = @{ author = $Author; date = $date; tweets = $payloadTweets } | ConvertTo-Json -Depth 6
  try {
    $r = Invoke-RestMethod -Uri "$api/api/archive/import" -Method POST -Body $body `
          -ContentType "application/json" -Headers @{ "X-API-TOKEN" = $token } -TimeoutSec 120
    Write-Host "  D1: +$($r.data.imported), skip $($r.data.skipped)"
    $totalImported += $r.data.imported
    $totalSkipped += $r.data.skipped
  } catch {
    Write-Host "  [x] D1 write failed: $($_.Exception.Message)"
  }
}

Write-Host "`n================================"
Write-Host "Files copied: $copied"
Write-Host "Tweets:       $totalTweets"
Write-Host "D1 new:       $totalImported  (skipped $totalSkipped)"

if (-not $SkipPush) {
  Write-Host "`n--- commit to git ---"
  Push-Location $root
  try {
    git add "frontend/public/media" 2>&1 | Out-Null
    $staged = @(git diff --cached --name-only)
    if ($staged.Count -gt 0) {
      git commit -m "sync: $Author archive $totalTweets tweets ($copied new files)" 2>&1 | Select-Object -First 2
      git push origin main 2>&1 | Select-Object -Last 3
      Write-Host "Pushed. Cloudflare Pages will auto-deploy in a few minutes."
    } else {
      Write-Host "No media changes, skip commit."
    }
  } catch {
    Write-Host "[x] git failed: $($_.Exception.Message)"
  } finally {
    Pop-Location
  }
}