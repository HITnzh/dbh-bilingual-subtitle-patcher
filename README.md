# DBH Bilingual Subtitle Patcher

`dbh-bilingual-subtitle-patcher` is a local patcher concept for building in-game bilingual subtitles for the Steam PC version of *Detroit: Become Human*.

The intended release model is conservative: the tool reads the player's own installed game files, extracts the official English and Chinese text locally, merges dialogue subtitles into `English line + newline + Simplified Chinese line`, and writes patched files on that player's machine. It should not ship official game text or prebuilt game archives.

## Current Status

This repository is at the project skeleton stage.

Implemented:

- `verify`: inspect a DBH game directory and report required files.
- `patch --dry-run`: produce a local patch plan without writing game files.
- `backup`: create a manifest-backed backup of files the patcher may modify.
- `restore`: restore files from backups created by this tool.
- `hashes`: create and compare local game file hash manifests.
- Core merge helpers for bilingual subtitle text.
- `tools`: inspect external DBH helper tools and print example extractor/packer commands.
- `idx`: run audited IDX-Detroit extract/repack plans.
- `discover`: find English and Chinese JSON catalogs in FileParser output.
- `merge`: merge local English and Chinese JSON text catalogs into bilingual JSON.
- `lint`: inspect merged catalogs for subtitle overflow and control-token risks.

Not implemented yet:

- DBH extractor/packer integration.
- Real patch application to `BigFile_PC.idx` / `BigFile_PC.d30`.
- Steam version hash allowlist.
- GUI.

## CLI

Run from the repository root during development:

```powershell
$env:PYTHONPATH = "src"
python -m dbh_bisub verify --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human"
python -m dbh_bisub hashes snapshot --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" --output ".\data\steam-local.hashes.json" --version-id "steam-local"
python -m dbh_bisub verify --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" --hash-manifest ".\data\steam-local.hashes.json"
python -m dbh_bisub patch --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" --dry-run
python -m dbh_bisub backup --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" --dry-run
python -m dbh_bisub backup --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human"
python -m dbh_bisub restore --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human"
python -m dbh_bisub tools --examples --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human"
python -m dbh_bisub idx extract --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" --idx-detroit "C:\Tools\IDX_Detroit.exe" --dry-run
python -m dbh_bisub extract --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" --output-dir ".\work\fileparser-output" --dry-run
python -m dbh_bisub discover --output-dir ".\work\fileparser-output"
python -m dbh_bisub merge --english ".\work\english.json" --chinese ".\work\chinese.json" --output ".\work\bilingual.json" --report ".\work\merge-report.json" --terms ".\data\terminology.csv"
python -m dbh_bisub lint --catalog ".\work\bilingual.json" --report ".\work\lint-report.json"
```

JSON output is available for automation:

```powershell
python -m dbh_bisub verify --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" --json
```

## External Tools

The patcher keeps DBH archive tooling behind an adapter layer. The first supported tool targets are:

- [`dbh-file-parser`](https://github.com/detroitbecometext/dbh-file-parser), for extracting DBH translation data from local game files.
- [`IDX-Detroit`](https://github.com/systemsiteseason/IDX-Detroit), for extracting and repacking `BigFile_PC.idx` archive data.

Check whether tools are discoverable on `PATH`:

```powershell
$env:PYTHONPATH = "src"
python -m dbh_bisub tools
```

Or point to local executable paths explicitly:

```powershell
python -m dbh_bisub tools `
  --file-parser "C:\Tools\FileParser.exe" `
  --idx-detroit "C:\Tools\IDX_Detroit.exe" `
  --examples `
  --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human"
```

After running FileParser, inspect the output directory:

```powershell
python -m dbh_bisub extract `
  --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" `
  --output-dir ".\work\fileparser-output" `
  --file-parser "C:\Tools\FileParser.exe" `
  --dry-run

python -m dbh_bisub extract `
  --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" `
  --output-dir ".\work\fileparser-output" `
  --file-parser "C:\Tools\FileParser.exe"

python -m dbh_bisub discover --output-dir ".\work\fileparser-output"
```

The command scans JSON files recursively, loads any catalog-like files it can parse, and recommends English/Chinese merge inputs when their filenames or paths are recognizable.

IDX-Detroit commands are also exposed with dry-run support:

```powershell
python -m dbh_bisub idx extract `
  --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" `
  --idx-detroit "C:\Tools\IDX_Detroit.exe" `
  --archive-id 1 `
  --object-count 0 `
  --dry-run

python -m dbh_bisub idx repack `
  --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" `
  --idx-detroit "C:\Tools\IDX_Detroit.exe" `
  --file-size-table ".\work\BigFile_PC.FileSizeTable" `
  --dry-run
```

## Text Catalogs

`merge` accepts a few simple JSON shapes so early experiments are not tied to one extractor format.

Mapping shape:

```json
{
  "subtitle_key_1": "Hello",
  "subtitle_key_2": "Stay where you are."
}
```

Entry list shape:

```json
{
  "entries": [
    { "key": "subtitle_key_1", "text": "Hello" },
    { "key": "subtitle_key_2", "text": "Stay where you are.", "speaker": "Connor" }
  ]
}
```

The output is normalized to:

```json
{
  "entries": [
    { "key": "subtitle_key_1", "text": "Hello\n你好" }
  ]
}
```

Quality checks can be tuned for experiments:

```powershell
python -m dbh_bisub lint `
  --catalog ".\work\bilingual.json" `
  --max-lines 2 `
  --max-line-chars 84 `
  --max-total-chars 160
```

The lint report flags empty text, too many visual lines, overlong lines, overlong entries, and control-token differences between bilingual lines.

Optional terminology CSV is applied to Chinese text before merging:

```csv
source,target,note
康纳,康納,character name
耶利哥,杰里科,location
```

Supported column aliases:

- Source: `source`, `from`, `traditional`, `original`
- Target: `target`, `to`, `simplified`, `replacement`
- Note: `note`, `notes`, `comment`

## Development

```powershell
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

Recommended Git flow:

```powershell
git switch -c feature/project-skeleton
git add .
git commit -m "Add project skeleton"
git switch main
git merge feature/project-skeleton
```

## Safety Rules

- Never distribute official game text or generated game archives.
- Always create a timestamped backup before writing any game file.
- Use `backup --dry-run` before creating backups in a real install directory.
- Record and verify game file hashes before applying any patch.
- Keep `patch --dry-run` useful enough to inspect every planned write before applying.

## Hash Manifests

Create a local manifest from a known-clean Steam install:

```powershell
python -m dbh_bisub hashes snapshot `
  --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" `
  --output ".\data\steam-local.hashes.json" `
  --version-id "steam-local"
```

Check a game directory against that manifest:

```powershell
python -m dbh_bisub hashes check `
  --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" `
  --manifest ".\data\steam-local.hashes.json"
```

`BigFile_PC.d30` is excluded by default because this project treats it as the patch archive slot. Pass `--include-patch-archive` only when you intentionally want to record or compare it.
