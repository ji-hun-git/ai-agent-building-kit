# Installs the building-ai-agents skill for Claude Code and Codex.
# Usage (PowerShell, from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\install-skill.ps1 [-Uninstall]
# Existing copies are moved to ~\.claude\skill-backups (or ~\.codex\skill-backups) first, never deleted;
# backups stay outside the skills folder so they are not loaded as a second copy of the skill.
# Re-running with nothing changed makes no backup; -Uninstall moves the installed copy to the backups.
param([switch]$Uninstall)

$ErrorActionPreference = "Stop"
$src = (Resolve-Path (Join-Path $PSScriptRoot "..\skill\building-ai-agents")).Path
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

$targets = @(
    @{ Name = "Claude Code"; Dir = Join-Path $env:USERPROFILE ".claude\skills"; IncludeEvals = $true },
    @{ Name = "Codex";       Dir = Join-Path $env:USERPROFILE ".codex\skills";  IncludeEvals = $false }
)

function Get-Tree([string]$Root, [bool]$IncludeEvals) {
    # relative path + content hash of every file, so two copies compare by content
    Get-ChildItem -Path $Root -Recurse -File | Where-Object {
        $rel = $_.FullName.Substring($Root.Length).TrimStart('\', '/')
        -not ($rel -match '(^|[\\/])__pycache__([\\/]|$)') -and ($IncludeEvals -or -not ($rel -match '^evals([\\/]|$)'))
    } | ForEach-Object {
        "{0} {1}" -f $_.FullName.Substring($Root.Length).TrimStart('\', '/'), (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    } | Sort-Object
}

function Move-ToBackup([hashtable]$t, [string]$dest) {
    $backups = Join-Path (Split-Path $t.Dir) "skill-backups"
    New-Item -ItemType Directory -Force -Path $backups | Out-Null
    $backup = Join-Path $backups "building-ai-agents-$stamp"
    Move-Item $dest $backup
    Write-Host "$($t.Name): existing copy moved to $backup"
}

foreach ($t in $targets) {
    $dest = Join-Path $t.Dir "building-ai-agents"
    if ($Uninstall) {
        if (Test-Path $dest) { Move-ToBackup $t $dest; Write-Host "$($t.Name): uninstalled" }
        else { Write-Host "$($t.Name): not installed" }
        continue
    }
    New-Item -ItemType Directory -Force -Path $t.Dir | Out-Null
    if (Test-Path $dest) {
        $same = $null -eq (Compare-Object @(Get-Tree $src $t.IncludeEvals) @(Get-Tree $dest $t.IncludeEvals))
        if ($same) { Write-Host "$($t.Name): up to date at $dest"; continue }
        Move-ToBackup $t $dest
    }
    Copy-Item $src $dest -Recurse
    if (-not $t.IncludeEvals) {
        $evals = Join-Path $dest "evals"
        if (Test-Path $evals) { Remove-Item $evals -Recurse -Force }
    }
    Write-Host "$($t.Name): installed to $dest"
}

if (-not $Uninstall) {
    Write-Host ""
    Write-Host "Check: python `"$src\scripts\check_freshness.py`" --no-models"
}
