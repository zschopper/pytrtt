# Translating a Game into Your Language

This guide explains how to contribute a language for a game and build listed in the [README support
table](../README.md#current-support). PyTRTT currently runs from Python source; a standalone Windows release
is not available yet.

## 1. Check the game and build

Use the exact game and build listed as supported. A translation for a different build must be extracted and
verified separately because game updates can change strings and identifiers. If the game or build is not
listed, open an issue before starting; new support may need archive-format research and developer work.

You need Python 3.13 or 3.14 and access to a clean copy of the supported game. Do not use your only installation as a
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

The content categories are **Interface** (Hungarian: **Felhasználói felület**) and **Subtitles**
(Hungarian: **Feliratok**). Interface covers menus, settings, HUD, prompts, and other UI text; subtitles cover
both cinematic and in-game dialogue captions. For compatibility, their JSON keys remain `menu` and `subtitles`;
do not rename these keys or related runtime identifiers.

Translation completeness means more than a non-null field. An imported value can still be unchanged English or text
from another language slot. Preserve intentional foreign-language dialogue, but do not assume every non-English
import is an intentional exception or a valid translation into the target language.

The Rise audit found repeated physical layers with missing translations and a mixture of English, French and
Hungarian subtitle imports. Exact resource/record/source matches can safely identify reusable candidates across
layers; source-only matching can conflate different contexts. Review source differences rather than replacing
controls or platform names with those from another build. The current draft and its remaining gaps are described
in the [Rise status](../README.md#rise-of-the-tomb-raider).

Likewise, a full game's subtitle timings are not automatically valid for a Trial. Preserve the target build's own
markers and leave unmarked text unmarked unless a specific exception is approved. Keep source records and timing
metadata unchanged while translating the text; binary readback does not establish synchronization with the audio.

Edit the `translation` values while preserving the source text, resource hashes and paths, entry IDs,
placeholders, control codes, and meaningful line breaks. Keep the file in UTF-8 and write normal Unicode
characters for your language. The optional `comment` field is an array of strings, with each translator or
reviewer note in its own element. Keep existing notes in order and append revision tags with their reasons
as new elements. These notes are not shown in the game.

Use `[revision: ID]` for a proposed correction and change it to `[revised: ID]` once the reviewer accepts
that wording. Keep the ID, previous text, and reason unchanged. A revised tag records text review;
it does not mean the wording has been checked in the game. Use `[rejected: ID]` for wording the reviewer
declined in favor of an accepted alternative, and `[superseded: ID]` when a previously accepted version
is replaced by a newer accepted version. Only proposals awaiting a decision remain `revision` notes.
Preserve each note's ID, previous text, and reason as review history.

```json
"comment": [
  "Check this label's width in the menu.",
  "[revision: R001] Previous: Start. Reason: clarified the action."
]
```

Use `[]` for an empty comment array, or omit the field when there are no notes. Legacy string comments
remain readable and are split at newline characters when loaded; serialization always writes arrays.

Entries normally use the document's `metadata.source_language`. If an individual source string is in another
language, set that entry's `source_language` property to its language code (for example, `"ru"`). This
per-entry override requires translation document schema version 3.

Schema version 4 can also retain the exact `archive_locale` on a resource when one hash occurs in
several archive locales. `archive_family` distinguishes physical layers with the same hash and locale,
such as a base interface resource and a partial patch interface resource. Preserve both values along with the
extracted entry IDs.
The optional runtime archive setting `include_overridden` exposes these layers for explicit addressing;
the default archive view still resolves the highest-priority resource.

For Bigfile v2, `runtime.archive.index_files` can map a declared family alias to an independently indexed
file. Guardian of Light uses `{"patch0": "patch.000", "patch1": "patch.001"}` because these files have
separate indexes, rather than forming a multipart family. Unmapped families retain the usual `.000`, `.001`
part naming. Keep the declared `families` order and aliases unchanged when editing an extracted document.
Exact duplicate index rows sharing the same data are preserved and updated together; conflicting duplicates
are rejected.

Read-only TIGER v4 profiles also use `index_files`, with aliases mapped to complete `.000.tiger` filenames,
including names with update/language components. The Temple of Osiris profile selects the base, English,
update and English-update indexes explicitly. Its archive handler supports extraction only; writing and
restoration are not implemented. The exported `en.json` is an English source template with unset translation fields.

Historical imports marked `"entry_identity": "source_text"` are translation memories. Their IDs are
memory-local ordinals; `legacy_tuid` and `legacy_context` preserve TMX provenance and do not locate game
records. These documents cannot be compiled into installation packages directly. A maintainer must first
extract the exact build and bind the memory to those records, for example:

```bash
bash scripts/dev.sh run --locked python scripts/bind_translation_memory.py \
  --memory translations/tomb-raider/hu.json \
  --extracted work/runs/example/extracted.json \
  --output work/runs/example/bound.json
```

The paths above are illustrative. Binding matches source language and source text, normalizes CRLF/LF,
and rejects conflicting translations. It keeps repeated game occurrences and their actual record IDs.
Missing matches still require review; binding does not prove archive writing or in-game compatibility.

Binding also preserves the memory's font declarations and copies their verified replacement assets beside
the output JSON. Existing assets with different contents are rejected. Keep the JSON and its `assets/`
directory together when moving a translation package.

Schema version 5 supports fonts embedded in DRM v22 collections in TIGER v3 archives. Each font declares
the collection's `resource_hash` and `resource_path`, an `embedded_type`, `embedded_id`, `archive_locale`,
replacement file, and SHA-256 digests of the original and replacement decoded resource bodies.
Optional font-specific `character_substitutions` are applied at installation time; conflicting runtime
substitutions are rejected. The planner updates all discovered physical references, allocates fresh
virtual ranges, writes the `NEXT` chain, and preserves original font bodies in the recovery journal.
This currently supports reference-free resource bodies and uncompressed indexed collections; unsupported
layouts fail without writes. Prepared font assets belong in the translation package, not in game archives.

Schema version 5 also allows an optional `archive_family` on a font asset. For a whole-resource font, this selects
one physical archive layer when the same resource hash occurs in the base game and patches. Each layer keeps
its own source digest and recovery asset. Extraction also saves each layer's original font under a distinct
recovery filename.

For an embedded font, `archive_family` selects the DRM collection layer used to identify and verify the source
body. Other collection layers referencing that same physical body are updated together, while distinct bodies
in other layers remain unchanged. Planning and installed-state checks use the same selector. Without it,
different source bodies for the same embedded identity remain an error; no layer is chosen implicitly.

Schema version 6 supports the document-level `credits` object. Each lowercase role maps to an ordered,
non-empty list of unique contributor names.

Schema version 7 supports 64-bit resource hashes and an optional per-entry `key` for keyed locals tables.
Preserve keyed record IDs and keys together. The TIGER v5 handler can append replacements for selected,
uncompressed keyed-locals resources and update their indexes through the common transaction journal. This does not
claim support for compressed resources, other embedded formats, or uninspected builds.

A missing `translation` value leaves the original game text in place and is reported as incomplete. An
explicit empty string (`"translation": ""`) writes one space, which can intentionally hide a string. Do not
leave a value empty by accident.

Do not copy another language's font asset, character substitutions, or subtitle-slot settings without checking
that they are suitable for your language and tested game build. Ask a maintainer if your language needs
additional glyphs or font work. The files under `restore-data/` are local recovery data, not translation
assets; do not submit them or any game archives.

## 4. Review and test

When replacing an installed translation with a revised package in the GUI, restore the previous installation first.
If an intact recovery journal matches the current game files, the GUI offers **Verified restoration available**
even when the selected package no longer matches the installed text. Installation remains disabled until restoration
and a fresh check. Restoration uses the journal's saved runtime configuration and follows applicable earlier patch
journals; missing, corrupt, foreign, or externally modified recovery states are not offered as safe restoration.
Legacy journals without saved runtime configuration still require the compatible translation document.

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

Launch the test copy and check the interface, subtitles, accents, placeholders, and line wrapping. Then restore it
using the same transaction directory:

```bat
py -3.13 -m pytrtt ^
  --restore ^
  --game-dir "C:\Games\Tomb Raider Anniversary test copy" ^
  --transaction-dir work\transactions\tra\es-test
```

Without `--transaction-dir`, new recovery data is written beside the program in
`transactions/<game-id>/<timestamp>/`; source runs use the project root. The GUI uses the same default and also
recognizes journals in its previous recovery locations. Multiple game copies are checked separately by folder;
a journal belonging to one copy cannot restore a different folder, even when their game files are identical.

Keep the transaction data until restoration succeeds. Include the game/build, language code, translator
credit, remaining review items, and test results in your pull request. Add or update the translation
provenance file alongside the JSON, following the existing language packages. Submit the translation JSON and
any required, verified translation assets only; never submit game files, local configuration, or transaction
backups.

The Windows Command Prompt examples follow the current CLI arguments but have not yet been tested on a native
Windows system.
