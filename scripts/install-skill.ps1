# Installs the building-ai-agents skill for Claude Code and Codex.
# Usage (PowerShell, from the repo root):  powershell -ExecutionPolicy Bypass -File scripts\install-skill.ps1
# Existing copies are moved to ~\.claude\skill-backups (or ~\.codex\skill-backups) first, never deleted;
# backups stay outside the skills folder so they are not loaded as a second copy of the skill.

$ErrorActionPreference = "Stop"
$src = Join-Path $PSScriptRoot "..\skill\building-ai-agents"
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"

$targets = @(
    @{ Name = "Claude Code"; Dir = Join-Path $env:USERPROFILE ".claude\skills"; IncludeEvals = $true },
    @{ Name = "Codex";       Dir = Join-Path $env:USERPROFILE ".codex\skills";  IncludeEvals = $false }
)

foreach ($t in $targets) {
    $dest = Join-Path $t.Dir "building-ai-agents"
    New-Item -ItemType Directory -Force -Path $t.Dir | Out-Null
    if (Test-Path $dest) {
        $backups = Join-Path (Split-Path $t.Dir) "skill-backups"
        New-Item -ItemType Directory -Force -Path $backups | Out-Null
        $backup = Join-Path $backups "building-ai-agents-$stamp"
        Move-Item $dest $backup
        Write-Host "$($t.Name): existing copy moved to $backup"
    }
    Copy-Item $src $dest -Recurse
    if (-not $t.IncludeEvals) {
        $evals = Join-Path $dest "evals"
        if (Test-Path $evals) { Remove-Item $evals -Recurse -Force }
    }
    Write-Host "$($t.Name): installed to $dest"
}

Write-Host ""
Write-Host "Check: python `"$src\scripts\check_freshness.py`" --no-models"
