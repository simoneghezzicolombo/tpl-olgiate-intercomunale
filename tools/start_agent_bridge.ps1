param(
    [string]$Workspace = (Get-Location).Path,
    [int]$PollSeconds = 45,
    [string]$Model = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=== TPL Agent Bridge ==="
Write-Host "Workspace: $Workspace"
Write-Host "Issue: simoneghezzicolombo/tpl-olgiate-intercomunale#1"
Write-Host "Poll: ${PollSeconds}s"

$localAgy = Join-Path $env:LOCALAPPDATA "agy\bin"
if (Test-Path (Join-Path $localAgy "agy.exe")) {
    $env:PATH = "$localAgy;$env:PATH"
}

if (-not (Get-Command agy -ErrorAction SilentlyContinue)) {
    Write-Host "Antigravity CLI (agy) non trovato." -ForegroundColor Yellow
    Write-Host "Installazione ufficiale Windows:"
    Write-Host '  irm https://antigravity.google/cli/install.ps1 | iex'
    exit 1
}

Write-Host "agy trovato: $((Get-Command agy).Source)" -ForegroundColor Green
Write-Host ""
Write-Host "Il bridge NON usa --dangerously-skip-permissions."
Write-Host "Concorrenza protetta da lockfile locale (.agent_bridge.lock)." -ForegroundColor Cyan
Write-Host ""

$Bridge = Join-Path $Workspace "tools\agent_bridge.py"
if (-not (Test-Path $Bridge)) {
    throw "Bridge non trovato: $Bridge"
}

$argsList = @($Bridge, "--workspace", $Workspace, "--poll-seconds", "$PollSeconds")
if ($Model -ne "") {
    $argsList += @("--model", $Model)
}

python @argsList
