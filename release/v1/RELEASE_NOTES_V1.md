# DBH Bilingual Subtitle Patcher V1

## What This Release Does

- Builds bilingual subtitles from the user's own local Detroit: Become Human files.
- Merges official English subtitles with official Simplified Chinese subtitles.
- Installs the merged text into the `SCH` / Simplified Chinese language block.
- Creates a timestamped backup before writing `BigFile_PC.idx` and `BigFile_PC.d30`.
- Includes a restore script for the latest or a specific backup.

## Important Notes

- Select `Simplified Chinese` / `SCH` in the game after installing.
- The package does not include official game text or prebuilt game archives.
- The installer requires external helper tools: DBH FileParser and IDX-Detroit.
- Tested locally against archive `1016`, where the verified V1 subtitle resources are stored.

## Verification From Local V1 Test

The verified target line after install:

```text
SCH: Captain Allen? / 艾伦队长？ My name is Connor. / 我是康纳。
```

The Traditional Chinese language block may also contain an English/Traditional Chinese variant if the user installed it separately. V1's recommended route is `SCH`.
