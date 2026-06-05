#Requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GameDir,

    [Parameter(Mandatory = $true)]
    [string]$FileParser,

    [Parameter(Mandatory = $true)]
    [string]$IdxDetroit,

    [string]$Python = "python",

    [string]$WorkDir,

    [switch]$Force
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

function Resolve-RequiredFile {
    param([string]$PathValue, [string]$Label)
    $item = Get-Item -LiteralPath $PathValue -ErrorAction Stop
    if ($item.PSIsContainer) {
        throw "$Label is not a file: $PathValue"
    }
    return $item.FullName
}

function Invoke-DbhBisub {
    param(
        [string]$Step,
        [string[]]$Arguments,
        [string]$LogPath
    )
    Write-Host "==> $Step"
    $logDir = Split-Path -Parent $LogPath
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
    & $Python -m dbh_bisub @Arguments > $LogPath 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "$Step failed with exit code $exitCode. See log: $LogPath"
    }
}

function Assert-DetroitIsClosed {
    $running = Get-Process | Where-Object {
        $_.ProcessName -like "*Detroit*" -or $_.ProcessName -like "*DetroitBecomeHuman*"
    }
    if ($running) {
        $names = ($running | ForEach-Object { "$($_.ProcessName)($($_.Id))" }) -join ", "
        throw "Close Detroit: Become Human before installing. Running processes: $names"
    }
}

$toolRoot = Resolve-ToolRoot
$gameRoot = Resolve-RequiredDirectory -PathValue $GameDir -Label "GameDir"
$fileParserPath = Resolve-RequiredFile -PathValue $FileParser -Label "FileParser"
$idxDetroitPath = Resolve-RequiredFile -PathValue $IdxDetroit -Label "IdxDetroit"

if (-not (Test-Path -LiteralPath (Join-Path $gameRoot "BigFile_PC.idx"))) {
    throw "BigFile_PC.idx was not found in GameDir: $gameRoot"
}

Assert-DetroitIsClosed

if ([string]::IsNullOrWhiteSpace($WorkDir)) {
    $stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $base = if ([string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) { $PWD.Path } else { $env:LOCALAPPDATA }
    $WorkDir = Join-Path $base "DBHBilingualSubtitlePatcher\v1-sch-$stamp"
}

$workRoot = [System.IO.Path]::GetFullPath($WorkDir)
if ((Test-Path -LiteralPath $workRoot) -and -not $Force) {
    $hasFiles = Get-ChildItem -LiteralPath $workRoot -Force -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hasFiles) {
        throw "WorkDir is not empty: $workRoot. Use a fresh directory or pass -Force."
    }
}

$reports = Join-Path $workRoot "reports"
$fileparserOutput = Join-Path $workRoot "fileparser-output"
$catalogDir = Join-Path $workRoot "catalog-src"
$patchWork = Join-Path $workRoot "patch"
$manifests = Join-Path $workRoot "manifests"
$catalog = Join-Path $catalogDir "bilingual-sch.json"
$beforeHash = Join-Path $manifests "before-install-no-d30.hashes.json"
$afterHash = Join-Path $manifests "after-install-with-d30.hashes.json"

New-Item -ItemType Directory -Path $reports, $catalogDir, $manifests -Force | Out-Null

$oldPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $toolRoot "src"

    & $Python -c "import sys; assert sys.version_info >= (3, 10); import dbh_bisub" > (Join-Path $reports "python-check.log") 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Python 3.10+ with dbh_bisub import failed. See: $(Join-Path $reports 'python-check.log')"
    }

    Invoke-DbhBisub "Extract local game language JSON with FileParser" @(
        "extract",
        "--game-dir", $gameRoot,
        "--output-dir", $fileparserOutput,
        "--file-parser", $fileParserPath,
        "--force",
        "--json"
    ) (Join-Path $reports "01-fileparser-extract.json")

    $english = Join-Path $fileparserOutput "eng.json"
    $simplified = Join-Path $fileparserOutput "sch.json"
    if (-not (Test-Path -LiteralPath $english)) { throw "FileParser did not create eng.json: $english" }
    if (-not (Test-Path -LiteralPath $simplified)) { throw "FileParser did not create sch.json: $simplified" }

    Invoke-DbhBisub "Merge English and Simplified Chinese subtitles" @(
        "merge",
        "--english", $english,
        "--chinese", $simplified,
        "--output", $catalog,
        "--report", (Join-Path $reports "02-merge-sch-report.json"),
        "--json"
    ) (Join-Path $reports "02-merge-sch.json")

    Invoke-DbhBisub "Snapshot game hashes before install" @(
        "hashes", "snapshot",
        "--game-dir", $gameRoot,
        "--output", $beforeHash,
        "--version-id", "v1-before-install-no-d30",
        "--json"
    ) (Join-Path $reports "03-before-hash.json")

    Invoke-DbhBisub "Prepare patch work directory" @(
        "prepare",
        "--game-dir", $gameRoot,
        "--catalog", $catalog,
        "--work-dir", $patchWork,
        "--idx-detroit", $idxDetroitPath,
        "--force",
        "--json"
    ) (Join-Path $reports "04-prepare.json")

    Invoke-DbhBisub "Extract IDX archive 1016" @(
        "patch-extract",
        "--game-dir", $gameRoot,
        "--work-dir", $patchWork,
        "--idx-detroit", $idxDetroitPath,
        "--archive-id", "1016",
        "--object-count", "0",
        "--execute",
        "--force",
        "--result", (Join-Path $patchWork "reports\patch-extract-result.json"),
        "--json"
    ) (Join-Path $reports "05-patch-extract.json")

    Invoke-DbhBisub "Stage Simplified Chinese DAT language patch" @(
        "patch-stage",
        "--game-dir", $gameRoot,
        "--work-dir", $patchWork,
        "--idx-dat-language", "SCH",
        "--idx-detroit", $idxDetroitPath,
        "--require-repack-plan",
        "--result", (Join-Path $patchWork "reports\patch-stage-result.json"),
        "--json"
    ) (Join-Path $reports "06-patch-stage.json")

    Invoke-DbhBisub "Materialize staged patch into extracted tree" @(
        "patch-materialize",
        "--work-dir", $patchWork,
        "--result", (Join-Path $patchWork "reports\patch-materialize-result.json"),
        "--json"
    ) (Join-Path $reports "07-patch-materialize.json")

    Invoke-DbhBisub "Install V1 patch with backup-protected repack" @(
        "patch-repack",
        "--game-dir", $gameRoot,
        "--work-dir", $patchWork,
        "--hash-manifest", $beforeHash,
        "--idx-detroit", $idxDetroitPath,
        "--execute",
        "--result", (Join-Path $patchWork "reports\patch-repack-result.json"),
        "--json"
    ) (Join-Path $reports "08-patch-repack.json")

    $idxBackup = Join-Path $gameRoot "BigFile_PC.idx_bk"
    if (Test-Path -LiteralPath $idxBackup) {
        Remove-Item -LiteralPath $idxBackup -Force
    }

    Invoke-DbhBisub "Snapshot game hashes after install" @(
        "hashes", "snapshot",
        "--game-dir", $gameRoot,
        "--output", $afterHash,
        "--version-id", "v1-after-install-sch",
        "--include-patch-archive",
        "--json"
    ) (Join-Path $reports "09-after-hash.json")

    Write-Host ""
    Write-Host "V1 install complete."
    Write-Host "Game subtitle language to select: Simplified Chinese / SCH."
    Write-Host "Work directory: $workRoot"
    Write-Host "Reports: $reports"
    Write-Host "Restore latest backup with: .\restore-latest.ps1 -GameDir `"$gameRoot`""
}
finally {
    $env:PYTHONPATH = $oldPythonPath
}
