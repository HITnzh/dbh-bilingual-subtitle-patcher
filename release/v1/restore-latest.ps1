#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameDir,

    [string]$BackupId = "latest",

    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Resolve-ToolRoot {
    $scriptDir = Split-Path -Parent $PSCommandPath
    $candidates = @(
        $scriptDir,
        (Split-Path -Parent $scriptDir),
        (Split-Path -Parent (Split-Path -Parent $scriptDir))
    )
    foreach ($candidate in $candidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            $src = Join-Path $candidate "src\dbh_bisub"
            $project = Join-Path $candidate "pyproject.toml"
            if ((Test-Path -LiteralPath $src) -and (Test-Path -LiteralPath $project)) {
                return (Resolve-Path -LiteralPath $candidate).Path
            }
        }
    }
    throw "Cannot find dbh_bisub source directory. Run this script from the V1 release package."
}

function Resolve-RequiredDirectory {
    param([string]$PathValue, [string]$Label)
    $item = Get-Item -LiteralPath $PathValue -ErrorAction Stop
    if (-not $item.PSIsContainer) {
        throw "$Label is not a directory: $PathValue"
    }
    return $item.FullName
}

$toolRoot = Resolve-ToolRoot
$gameRoot = Resolve-RequiredDirectory -PathValue $GameDir -Label "GameDir"

$running = Get-Process | Where-Object {
    $_.ProcessName -like "*Detroit*" -or $_.ProcessName -like "*DetroitBecomeHuman*"
}
if ($running) {
    $names = ($running | ForEach-Object { "$($_.ProcessName)($($_.Id))" }) -join ", "
    throw "Close Detroit: Become Human before restoring. Running processes: $names"
}

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $toolRoot "src"
    & $Python -m dbh_bisub restore --game-dir $gameRoot --backup-id $BackupId --json
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Restore failed with exit code $exitCode."
    }

    $idxBackup = Join-Path $gameRoot "BigFile_PC.idx_bk"
    if (Test-Path -LiteralPath $idxBackup) {
        Remove-Item -LiteralPath $idxBackup -Force
    }

    Write-Host "Restore complete. Backup id: $BackupId"
}
finally {
    $env:PYTHONPATH = $oldPythonPath
}
