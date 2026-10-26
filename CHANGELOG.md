# Changelog

## Unreleased — 2026-10-26

### Motivation

- Real TR2013 updates exposed two different causes behind apparent unknown modifications: unbound translation memory
  and an older installed package that differed from the revised package. Make those states actionable without
  bypassing original-source, build or recovery-integrity checks.
- Shared Setup/in-game strings made circumflex substitution unsuitable for one rendering context or the other.
  Add actual Unicode glyphs so the same correct Hungarian text can be used in both contexts and in subtitles.
- Resource progress appeared frozen at completion while archive planning, copying or verification continued.
  Surface these phases and diagnostic identities so long operations and genuine validation failures can be distinguished.
- Rise was blocked by missing text writers, and null/filled counts hid repeated-layer gaps and wrong-language imports.
  Enable safe writes, fill exact matches, and track language/content validation separately from field population.
- Trial/full-game source and timing differences required explicit reconciliation rather than blind translation reuse.
  Preserve target-build identities and confirm that restoration leaves the package installable again.

### Added

- A setup-style graphical client with Steam discovery, manual folder selection, translation checks, installation,
  restoration, interrupted-transaction recovery, and English/Hungarian interface messages.
- Separate installation choices for multiple copies of the same game, with status and recovery checks tied to
  the selected folder and its file hashes.
- Bigfile v2 support for Underworld and Guardian of Light, including independent patch indexes, physical archive
  layers, and Guardian of Light DLC resources.
- TIGER v3 reading, writing, and restoration for Tomb Raider (2013), plus TIGER v4 text and embedded-font writing
  for the verified Temple of Osiris build.
- Rise locals/3 and SCH/3 writers, plus selected TIGER v5/keyed-text writing and journaled restoration for Shadow
  and Shadow Trial. Verified text-resource paths do not establish arbitrary binary-resource writing support.
- Additional locals, CINE, and SCH handlers, including 64-bit locals pointers and preserved resource identities
  across physical archive layers.
- Translation schema support for embedded fonts and explicit archive-layer selection, with separate original
  font recovery assets.
- Hungarian packages and provenance for Underworld, Tomb Raider (2013), Guardian of Light, and Temple of Osiris.
- Supported Anniversary Demo Steam build `251873`, with its dedicated profile, verified filename list, complete
  Hungarian interface/subtitles and replacement font. User-verified Setup remains UTF-8; Direct3D and already-running
  error dialogs deliberately retain original English ASCII after a CP1250 experiment broke Setup decoding.
- Maintained font supplements for Tomb Raider (2013), Guardian of Light, and Temple of Osiris. The TR2013 and Osiris
  supplements add real Unicode `ŐőŰű` glyphs; TR2013 no longer substitutes circumflexes in interface text or subtitles.
- Translation-memory import and binding tools, verified filename lists, and a Windows GUI launcher.
- A helper script for archiving staged project files.

### Changed

- GUI and CLI recovery data now defaults to `transactions/<game-id>/<timestamp>/` beside the program. Source runs
  use the project root; bundled applications use the executable directory. The CLI override remains available.
- The GUI also discovers recovery journals in the previous project and user-data locations without moving them.
- The Windows source launcher enables debug logging and game-local recovery, with progress and validation details
  in the GUI log. Build tooling can produce the executable separately from the optional installer.
- Standardized content category names as Interface / Felhasználói felület and Subtitles / Feliratok without changing
  translation schema keys or game text.
- Completed Shadow Trial's 77-record source/timing reconciliation and verified the updated selected-text package
  through GUI-backend installation, byte-exact restoration and renewed translation availability on a copy.
- Expanded the partial Rise draft: 19,623 exact-match interface fields, 73 remaining interface translations and
  239 subtitle records from the opening ice-climb scene. Existing French text remains unchanged; subtitle work continues.
- Updated Anniversary, Legend, and Legend Demo translation data, provenance, and user-reported verification status.
- Extended development support to Python 3.14 alongside Python 3.13.
- Expanded translation documentation, contributor credits, binary-safety guidance, and per-game status cards with
  archive/text variants, filename coverage, proofreading, fonts, remaining work, and verification limits.

### Fixed

- Prevented the graphical installation list from discarding additional copies of the same game.
- Preserved case-sensitive POSIX installation identities while retaining Windows/WSL path matching and
  case-insensitive Windows network paths.
- Corrected font placement and archive-stream metadata for embedded font supplements, with recovery of original
  bytes and archive sizes.
- Preserved per-entry substitution exceptions, translation comments, control tokens, and legacy menu import behavior.
- Validated known build IDs on the already-installed GUI path, not only before installation planning.
- Kept verified restoration available after a translation package changes, without weakening source or backup checks.
  Restoration uses journal-owned runtime settings and follows applicable earlier targeted-patch journals.
- Preserved resource-layer identities, control placeholders, timing prefixes and unrelated language slots in the new
  Rise text writers and targeted subtitle batches.

### Validation and scope

- Added regression coverage for archive variants, layered and embedded fonts, text formats, portable recovery paths,
  translation memory, GUI workflows, and independent installation/restoration of identical game copies.
- The complete development scope, including the completed Anniversary Demo project, passed 450 tests with
  19 optional integration tests deselected.
  Ruff lint, formatting, mypy and Markdown checks passed. Maintained-package regression tests guard source identities,
  translation coverage, current package hashes and font metadata.
- Game-specific installation, restoration, and user-reported appearance checks remain documented in the individual
  package provenance files. Complete text extraction or installation does not imply complete linguistic review.
- Rise remains a partial translation draft: filled subtitle fields include unchanged English and French imports.
  Binary readback, copy restoration and observed game appearance are separate results, not linguistic sign-off.
