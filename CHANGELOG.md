# Changelog

## Unreleased — 2026-10-19

### Added

- A setup-style graphical client with Steam discovery, manual folder selection, translation checks, installation,
  restoration, interrupted-transaction recovery, and English/Hungarian interface messages.
- Separate installation choices for multiple copies of the same game, with status and recovery checks tied to
  the selected folder and its file hashes.
- Bigfile v2 support for Underworld and Guardian of Light, including independent patch indexes, physical archive
  layers, and Guardian of Light DLC resources.
- TIGER v3 reading, writing, and restoration for Tomb Raider (2013), plus TIGER v4 text and embedded-font writing
  for the verified Temple of Osiris build.
- Read-only Rise extraction support and standalone TIGER v5/keyed-text readers for Shadow and Shadow Trial.
  These readers do not establish general writing support for those games.
- Additional locals, CINE, and SCH handlers, including 64-bit locals pointers and preserved resource identities
  across physical archive layers.
- Translation schema support for embedded fonts and explicit archive-layer selection, with separate original
  font recovery assets.
- Hungarian packages and provenance for Underworld, Tomb Raider (2013), Guardian of Light, and Temple of Osiris.
- Maintained font supplements for Tomb Raider (2013), Guardian of Light, and Temple of Osiris. The Osiris supplement
  adds real Unicode `ŐőŰű` glyphs without character substitution.
- Translation-memory import and binding tools, verified filename lists, and a Windows GUI launcher.
- A helper script for archiving staged project files.

### Changed

- GUI and CLI recovery data now defaults to `transactions/<game-id>/<timestamp>/` beside the program. Source runs
  use the project root; bundled applications use the executable directory. The CLI override remains available.
- The GUI also discovers recovery journals in the previous project and user-data locations without moving them.
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

### Validation and scope

- Added regression coverage for archive variants, layered and embedded fonts, text formats, portable recovery paths,
  translation memory, GUI workflows, and independent installation/restoration of identical game copies.
- The latest development test run passed 306 tests; 18 optional integration tests were deselected.
- Game-specific installation, restoration, and user-reported appearance checks remain documented in the individual
  package provenance files. Complete text extraction or installation does not imply complete linguistic review.
- Rise, Shadow, and Shadow Trial translation directories are excluded from this staged change. Their supporting
  development code, tests, profiles, and filename data are included where present.
