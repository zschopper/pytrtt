# Translating a Game into Your Language

This guide explains how to contribute a language for a game and build listed in the [README support
table](../README.md#current-support). PyTRTT currently runs from Python source; a standalone Windows release
is not available yet.

## 1. Check the game and build

Use the exact game and build listed as supported. A translation for a different build must be extracted and
verified separately because game updates can change strings and identifiers. If the game or build is not
listed, open an issue before starting; new support may need archive-format research and developer work.

You need Python 3.13 and access to a clean copy of the supported game. Do not use your only installation as a
test copy.

## 2. Extract a translation template

From the repository root, run `scripts/extract_strings.py` with the game's developer profile and a new output
directory. For the supported Tomb Raider: Anniversary Steam build, run this in Windows Command Prompt:

```bat
py -3.13 scripts\extract_strings.py ^
  --profile profiles\tomb-raider-anniversary.json ^
  --game-dir "C:\SteamLibrary\steamapps\common\Tomb Raider Anniversary" ^
  --output-dir work\runs\tra\842717\es-template ^
  --source-language en ^
  --target-language es ^
  --build-id 842717
```

Replace `es` with your language code. Use a fresh output directory outside the game folder; the extractor
refuses to overwrite files. It creates a JSON file containing the source strings and technical settings, plus
an extraction report and any required local font/recovery files. Copy the generated JSON into
`translations/<game-id>/<language-code>.json`, for example `translations/tomb-raider-anniversary/es.json`.

For another supported game, use its profile, exact build ID, installation path, and a matching output
directory. Do not edit the profile or runtime settings unless you are working with a maintainer.

## 3. Translate the JSON

Edit the `translation` values while preserving the source text, resource hashes and paths, entry IDs,
placeholders, control codes, and meaningful line breaks. Keep the file in UTF-8 and write normal Unicode
characters for your language. Optional `comment` values are for translator or reviewer notes; they are not
shown in the game.

A missing `translation` value leaves the original game text in place and is reported as incomplete. An
explicit empty string (`"translation": ""`) writes one space, which can intentionally hide a string. Do not
leave a value empty by accident.

Do not copy another language's font asset, character substitutions, or subtitle-slot settings without checking
that they are suitable for your language and tested game build. Ask a maintainer if your language needs
additional glyphs or font work. The files under `restore-data/` are local recovery data, not translation
assets; do not submit them or any game archives.

## 4. Review and test

First run the default dry run against a separate game copy. It does not write to the game:

```bat
py -3.13 -m pytrtt ^
  --translation-file translations\tomb-raider-anniversary\es.json ^
  --game-dir "C:\Games\Tomb Raider Anniversary test copy" ^
  --build-id 842717 ^
  --ui-language en
```

Resolve missing or invalid records before installation. For a round-trip test, apply the translation to that
test copy with a new transaction directory:

```bat
py -3.13 -m pytrtt ^
  --translation-file translations\tomb-raider-anniversary\es.json ^
  --game-dir "C:\Games\Tomb Raider Anniversary test copy" ^
  --build-id 842717 ^
  --apply ^
  --transaction-dir work\transactions\tra\es-test
```

Launch the test copy and check menus, subtitles, accents, placeholders, and line wrapping. Then restore it
using the same transaction directory:

```bat
py -3.13 -m pytrtt ^
  --restore ^
  --game-dir "C:\Games\Tomb Raider Anniversary test copy" ^
  --transaction-dir work\transactions\tra\es-test
```

Keep the transaction data until restoration succeeds. Include the game/build, language code, translator
credit, remaining review items, and test results in your pull request. Add or update the translation
provenance file alongside the JSON, following the existing language packages. Submit the translation JSON and
any required, verified translation assets only; never submit game files, local configuration, or transaction
backups.

The Windows Command Prompt examples follow the current CLI arguments but have not yet been tested on a native
Windows system.
