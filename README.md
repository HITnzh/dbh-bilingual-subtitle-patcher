# DBH Bilingual Subtitle Patcher

`dbh-bilingual-subtitle-patcher` is a local patcher concept for building in-game bilingual subtitles for the Steam PC version of *Detroit: Become Human*.

The intended release model is conservative: the tool reads the player's own installed game files, extracts the official English and Chinese text locally, merges dialogue subtitles into `English line + newline + Simplified Chinese line`, and writes patched files on that player's machine. It should not ship official game text or prebuilt game archives.

## Current Status

This repository is at the project skeleton stage.

Implemented:

- `verify`: inspect a DBH game directory and report required files.
- `patch --dry-run`: produce a local patch plan without writing game files.
- `restore`: restore files from backups created by this tool.
- Core merge helpers for bilingual subtitle text.
- `tools`: inspect external DBH helper tools and print example extractor/packer commands.
- `merge`: merge local English and Chinese JSON text catalogs into bilingual JSON.

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
python -m dbh_bisub patch --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human" --dry-run
python -m dbh_bisub restore --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human"
python -m dbh_bisub tools --examples --game-dir "D:\SteamLibrary\steamapps\common\Detroit Become Human"
python -m dbh_bisub merge --english ".\work\english.json" --chinese ".\work\chinese.json" --output ".\work\bilingual.json" --report ".\work\merge-report.json" --terms ".\data\terminology.csv"
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
- Refuse unknown game file versions by default once version hashes are implemented.
- Keep `patch --dry-run` useful enough to inspect every planned write before applying.
