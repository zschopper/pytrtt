# PyTRTT - Tomb Raider Translation Toolkit

*Forged in Python, Built for Adventure.*

PyTRTT extracts, installs and restores Tomb Raider translations. It is the Python successor to the
C# TRTR2 project, with shared archive and resource handlers selected by format and version.

Translations are editable UTF-8 JSON files, grouped by resource, with source text, translation and
translator comments. Game profiles supply technical settings during development; compiled language
files carry the configuration needed to apply the translation.

## Game status and remaining work

The following covers the games currently in scope. Translation status refers to Hungarian on PC; Steam build
numbers identify the versions investigated. An unknown build means no target build is established here. Supported
status applies only to the listed game/build. Experimental installations and imported text drafts still have the
outstanding checks described below; owning a game or having reference files does not establish support.

Status snapshot: **2026-10-26**. The game sections below are ordered by release date.

**Current local Steam state:** the Anniversary Demo uses the Hungarian UTF-8 package with English error dialogs;
the other games remain in their previously recorded states. Hungarian JSON files, font assets and recovery backups
are preserved. The results below describe translation capabilities and completed tests.

| Game | Steam build | Project status | Verified result | Current Steam state |
| --- | --- | --- | --- | --- |
| Tomb Raider: Legend Demo | `251815` | 🟢 Supported | Proofread HU; game/setup verified | English |
| Tomb Raider: Legend | `251820` | 🟢 Supported | Complete, proofread HU; game verified | English |
| Tomb Raider: Anniversary | `842717` | 🟢 Supported | Proofread HU; install, restore and game verified | English |
| Tomb Raider: Anniversary Demo | `251873` | 🟢 Supported | HU UI; English error dialogs verified | Hungarian |
| Tomb Raider: Underworld Demo | Unknown | 🔴 Not started | Index inventory only | English |
| Tomb Raider: Underworld | `251883` | 🟡 Experimental | Selected HU verified; font port pending | English |
| Lara Croft and the Guardian of Light | `11395` | 🟡 Experimental | HU base/DLC verified; font check pending | English |
| Tomb Raider (2013) | `9573671` | 🟡 Experimental | Selected HU text and repaired font observed in game | English |
| Lara Croft and the Temple of Osiris | `477027` | 🟡 Complete draft | 3,082 HU texts; accents game-verified | English |
| Rise of the Tomb Raider | `9575745` | 🟡 Partial draft | Interface filled; subtitles incomplete | English |
| Shadow of the Tomb Raider Trial | `3668420` | 🟡 Game-tested draft | 38,055 HU texts; game-verified | English |
| Shadow of the Tomb Raider | `11668867` | 🟡 Import draft | 38,234 HU texts; review/game test pending | English |

Recent verified results: Temple of Osiris was installed with all 3,082 exported texts translated and real Unicode
`ŐőŰű` font glyphs; the user confirmed the corrected accents in the game and setup dialog. Shadow Trial was installed
with all 38,055 populated text records translated and a successful user-reported game test. Both translations still
need linguistic review; these results apply to the inspected builds and content described below.

Status markers: 🟢 complete; 🟡 in progress or partially complete; 🔴 not started.
Markers apply to the individual aspect and its stated scope; completion of one aspect does not imply full game support.

Version numbers below identify PyTRTT handlers unless an on-disk version is explicitly named. Bigfile v1/v2 are
handler variants of an indexed layout, not native version fields. R/W means reading, writing and restoration are
implemented for the verified variant; it does not mean gameplay is verified.

Filename coverage counts unique indexed resource-name hashes, combining locales and repeated archive layers. Only
names whose computed hash matches the index count as resolved; hash-only paths do not count. Above 99% each game
shows the exact missing-name count instead of a rounded percentage. The denominator is the inspected archive set,
not every edition or platform: selected families for supported projects, all top-level index archives for Rise and
Shadow. These filename measurements were collected on 2026-10-16 and have not been rerun for this status update.
Rise's English export targets Steam build `9575745`; Underworld Demo was compared with the full game's name list
and has no dedicated translation profile. The
[measurement evidence](docs/game-status-evidence.json) records every selected index, name-list hash and denominator.
Filename coverage is independent of text extraction coverage. Shadow's keyed locals table uses text handler version
4; its language ID and translation JSON schema are separate version numbers.

Translation content categories are **Interface** (Hungarian: **Felhasználói felület**) and **Subtitles**
(Hungarian: **Feliratok**). Interface includes menus, settings, HUD, and prompts; subtitles include cinematic and
in-game dialogue captions. Existing JSON keys `menu` and `subtitles` remain unchanged for compatibility.

“Complete” extraction refers to the selected build's identified interface/subtitle resource types and archive layers. It
does not establish arbitrary embedded-text or unexamined DLC coverage. Human authorship, machine pretranslation,
structural QA, linguistic proofreading and gameplay checks are separate results. “Needs review” means the current
assembled package has no documented complete linguistic sign-off.

Legacy human authors and editors are recorded in [translation credits](TRANSLATION_CREDITS.md). The supplied
Guardian of Light package does not identify its contributors or production method; its new additions were produced
by this AI assistant. AI-authored additions are not counted as human translation because they were entered manually
or passed structural QA. The same distinction applies to Underworld's gap fills and the Temple of Osiris draft.
Historical releases and official reference text are not evidence that every current import or new addition was
proofread. Tomb Raider (2013)'s 48 unmatched records comprise 32 nonempty interface texts, one nonempty subtitle and 15
empty source records; the outstanding text includes privacy notices, terms of service and Epic/Steam multiplayer
messages.

Binary localization covers fonts, glyph maps and other language-dependent non-text assets. A “not assessed” entry
means necessity is unknown, not that replacement is unnecessary. Shared
[translation guidelines](ai-guidance/translation/guidelines.md),
[terminology rules](ai-guidance/translation/terminology.md) and
[QA rules](ai-guidance/translation/quality-assurance.md) apply to every game. The
[game-specific guidance](docs/GAME_TRANSLATION_GUIDE.md) records the translation workflow differences and known
technical or contextual caveats for each title; it does not replace the executable technical profiles.

Temple of Osiris terminology is recorded in its
[translation provenance](translations/lara-croft-and-the-temple-of-osiris/provenance.json). Other binary assets,
such as localized interface textures, have no established complete localization inventory. The font results below
do not imply that all non-text assets have been checked.

### Tomb Raider: Legend Demo

Steam build: `251815`. **Status:** 🟢 Supported; game appearance user-verified.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟢 Bigfile/1, R/W |
| Text formats | 🟢 locals/1; CINE/1 |
| Resolved filenames | 🟢 0 missing |
| Text extraction | 🟢 Complete interface/subtitles |
| Translation / origin | 🟢 Human translation; legacy release |
| Proofreading | 🟢 Original translation manually proofread; user-confirmed |
| Binary format / need | 🟢 RAW/1 font; required |
| Binary localization | 🟢 Replacement ready; setup accents user-verified |
| Game-specific guidance | 🟢 [Legend Demo guidance](docs/GAME_TRANSLATION_GUIDE.md#tomb-raider-legend-demo) |

The [Hungarian package](translations/tomb-raider-legend-demo/hu.json) covers interface text, subtitles and font replacement.
The user confirmed the corrected setup accents with Hungarian selected as the Windows language for non-Unicode
programs.

The user confirmed on 2026-10-19 that the Hungarian version works correctly and that the original translation
was manually proofread. This confirmation applies to the Hungarian package.

**Remaining:** preserve that setup behavior in regression checks and validate future Windows distribution
builds.

### Tomb Raider: Legend

Steam build: `251820`. **Status:** 🟢 Supported; game appearance user-verified.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟢 Bigfile/1, R/W |
| Text formats | 🟢 locals/1; CINE/1 |
| Resolved filenames | 🟢 0 missing |
| Text extraction | 🟢 Complete interface/subtitles |
| Translation / origin | 🟢 Human translation; legacy release and user completions |
| Proofreading | 🟢 Original translation manually proofread; user-confirmed |
| Binary format / need | 🟢 RAW/1 font; required |
| Binary localization | 🟢 Replacement ready in supported package |
| Game-specific guidance | 🟢 [Legend guidance](docs/GAME_TRANSLATION_GUIDE.md#tomb-raider-legend) |

The [Hungarian package](translations/tomb-raider-legend/hu.json) covers interface text, subtitles and a replacement
font for the supported build.

The user confirmed on 2026-10-19 that the Hungarian version works correctly and that the original translation
was manually proofread. This confirmation applies to the Hungarian package.

**Remaining:** maintain build-specific regression checks and validate future packaging changes.
There is no open translation implementation task for this build.

### Tomb Raider: Anniversary

Steam build: `842717`. **Status:** 🟢 Supported; Hungarian installation user-verified; Steam now English.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟢 Bigfile/1, R/W |
| Text formats | 🟢 locals/1; CINE/1 |
| Resolved filenames | 🟢 0 missing |
| Text extraction | 🟢 Complete interface/subtitles |
| Translation / origin | 🟢 Human translation; legacy/public reference |
| Proofreading | 🟢 Original translation manually proofread; user-confirmed |
| Binary format / need | 🟢 RAW/1 font; required |
| Binary localization | 🟢 Replacement verified; Steam original restored |
| Game-specific guidance | 🟢 [Anniversary guidance](docs/GAME_TRANSLATION_GUIDE.md#tomb-raider-anniversary) |

The [Hungarian package](translations/tomb-raider-anniversary/hu.json) covers interface text, subtitles and font replacement.
Full copy installation/restoration and a native Windows transaction smoke test passed; the installed Hungarian
package was user-verified before restoration to English.

The user confirmed on 2026-10-19 that the Hungarian version works correctly and that the original translation
was manually proofread. This confirmation applies to the Hungarian package.

**Remaining:** validate release packaging. The separate
[Brazilian Portuguese draft](translations/tomb-raider-anniversary/pt-BR.json) still needs language review and
in-game testing.

### Tomb Raider: Anniversary Demo

Steam build: `251873`. **Status:** 🟢 Supported; installation/restoration and setup error dialogs verified.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟢 Bigfile/1, R/W |
| Text formats | 🟢 locals/1; CINE/1 |
| Resolved filenames | 🟢 0 missing for translated resources |
| Text extraction | 🟢 Complete interface/subtitles |
| Translation / origin | 🟢 Human translation; Anniversary legacy release |
| Proofreading | 🟢 Inherited from the manually proofread Anniversary translation |
| Binary format / need | 🟢 RAW/1 font; required |
| Binary localization | 🟢 Game/font and English ASCII error dialogs user-verified |
| Game-specific guidance | 🟢 [Anniversary Demo guidance](docs/GAME_TRANSLATION_GUIDE.md#tomb-raider-anniversary-demo) |

The [Hungarian package](translations/tomb-raider-anniversary-demo/hu.json) covers 1001 interface records,
73 subtitle records in 62 resources, and the replacement font. The historical `trad.v1.0` filelist was verified
against this build; the maintained full Anniversary translation supplies the matching Hungarian text.
The user verified accented Hungarian characters in the game and ordinary setup screens on 2026-10-22, then found
UTF-8 mojibake in a Direct3D error dialog. A CP1250 experiment made the setup reject its labels as invalid UTF-8 and
was removed completely. The normal setup remains Hungarian UTF-8; its 18 legacy system/error-dialog strings retain
their original English ASCII text. The user verified both the Direct3D initialization error and the already-running
process error without encoding corruption on 2026-10-26.

**Remaining:** validate the packaged Windows release.

### Tomb Raider: Underworld Demo

Steam build: not established. **Status:** 🔴 Not started.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟡 Bigfile index read; variant unverified |
| Text formats | 🔴 Not investigated |
| Resolved filenames | 🟡 1.50% |
| Text extraction | 🔴 Not extracted |
| Translation / origin | 🔴 Untranslated |
| Proofreading | 🔴 Not started |
| Binary format / need | 🔴 Not investigated |
| Binary localization | 🔴 Need unknown; no localized assets prepared |
| Game-specific guidance | 🟢 [Underworld Demo guidance](docs/GAME_TRANSLATION_GUIDE.md#tomb-raider-underworld-demo) |

no dedicated profile, extraction or translation package exists.

**Remaining:** establish the target build, inspect
its archives and text variants, export the text, prepare the translation, then verify installation, restoration and
in-game appearance separately from the full game.

### Tomb Raider: Underworld

Steam build: `251883`. **Status:** 🟡 Experimental; Steam restored to English.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟢 Bigfile/2, R/W |
| Text formats | 🟢 locals/1; CINE/3; SCH/2 |
| Resolved filenames | 🟢 0 missing |
| Text extraction | 🟢 Complete selected interface/subtitles |
| Translation / origin | 🟡 Official HU reference plus AI gap fills |
| Proofreading | 🟡 Needs review of additions |
| Binary format / need | 🟢 DRM v19 / PCD9 font; required |
| Binary localization | 🟡 Identified; Steam port pending |
| Game-specific guidance | 🟢 [Underworld guidance](docs/GAME_TRANSLATION_GUIDE.md#tomb-raider-underworld) |

The [Hungarian package](translations/tomb-raider-underworld/hu.json) uses the official Hungarian edition as its
reference. All 2,895 interface records and 863 subtitle records were read back after Steam installation; installation and
repeated restoration were verified on a copy. The user reported boxes instead of Hungarian double-acute letters. The
installed font matches the original Steam font: its 205-entry character table lacks all four `ŐőŰű` glyphs. The
official Hungarian font has 501 entries and includes them; its character table and larger glyph atlas differ from
Steam's.

**Remaining:** implement and verify compatible replacement of both font resources, then test interface text,
subtitles and accents. No font replacement has been applied. See the
[provenance](translations/tomb-raider-underworld/provenance.json).

### Lara Croft and the Guardian of Light

Steam build: `11395`. **Status:** 🟡 Experimental; Steam restored to English.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟢 Bigfile/2, R/W |
| Text formats | 🟢 locals/1; CINE/3; SCH/2 |
| Resolved filenames | 🟡 84.54% |
| Text extraction | 🟢 Complete selected base/DLC text |
| Translation / origin | 🟡 Legacy + AI additions |
| Proofreading | 🟡 Needs review; interface approved |
| Binary format / need | 🟢 DRM v19 / PCD9 DXT5 Latin font; required |
| Binary localization | 🟡 Double-acute font verified by readback; original restored; game check pending |
| Game-specific guidance | 🟢 [Guardian guide](docs/GAME_TRANSLATION_GUIDE.md#lara-croft-and-the-guardian-of-light) |

The [Hungarian package](translations/lara-croft-and-the-guardian-of-light/hu.json) covers 8,214 interface records across
eight physical layers and 283 subtitle records, including the five installed DLC packs. It imports the historical
Hungarian translation and adds 115 previously unmatched unique strings. Full copy installation/readback and repeated
byte-exact restoration passed; Steam installation/readback also passed. The package retains the historical `ő/ű/Ő/Ű
→ ô/û/Ô/Û` runtime fallback; editable text keeps correct Unicode. The user confirmed the interface translation before
the font update. On 2026-10-18 a font supplement was installed: those four fallback slots now contain Hungarian
double-acute glyph images, preserving the native outlines and metrics. Only the patch font atlas changed; text
resources remained byte-identical. Copy installation and repeated byte-exact restoration, plus Steam font readback,
passed; in-game appearance of this new font still needs a Windows check.

**Remaining:** verify the new double-acute glyphs in interface text and subtitles, DLC-specific text and line wrapping.
See the
[provenance](translations/lara-croft-and-the-guardian-of-light/provenance.json).

### Tomb Raider (2013)

Steam build: `9573671`. **Status:** 🟡 Experimental; font appearance verified.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟢 TIGER/3, R/W |
| Text formats | 🟢 locals/2; CINE/2; SCH/1 |
| Resolved filenames | 🟡 2 missing |
| Text extraction | 🟢 Complete selected text |
| Translation / origin | 🟡 Human legacy + 33 build-specific AI additions; 19,888 bound records |
| Proofreading | 🟡 New batch appearance reviewed in game; linguistic sign-off pending |
| Binary format / need | 🟢 DRM v22 / GFX fonts; required |
| Binary localization | 🟢 Packaged and observed glyphs verified; Steam original restored |
| Game-specific guidance | 🟢 [Tomb Raider (2013) guidance](docs/GAME_TRANSLATION_GUIDE.md#tomb-raider-2013) |

The [build-specific Hungarian package](translations/tomb-raider/steam-9573671-hu.json) contains 19,888 bound records,
including 33 additions for this build; 15 empty source records remain untranslated. Its font supplement and archive
changes passed copy-based installation and restoration checks. The user reviewed the new translated batch in game on
2026-10-22 and reported that it looked good. This confirms the reviewed text's appearance, not a complete linguistic
proofread or every screen and line-wrapping case.

The maintained fonts now include actual Unicode `ŐőŰű` glyphs, and both Hungarian documents disable all former
double-acute-to-circumflex substitutions for interface text and subtitles. The user confirmed correct accents after
installation on 2026-10-26, then successful GUI restoration and renewed translation availability. This confirms the
observed screens, not every font consumer or subtitle scene.

**Remaining:** complete linguistic proofreading and broaden screen/line-wrapping coverage.
The 15 empty unmatched source records are tracked separately from
untranslated text. See the
[provenance and verification limits](translations/tomb-raider/provenance.json).

### Lara Croft and the Temple of Osiris

Steam build: `477027`. **Status:** 🟡 Hungarian text and accents verified; Steam now English.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟡 TIGER/4; append-only writing and repeated restoration verified on a copy |
| Text formats | 🟢 locals/2; CINE/2; SCH/2 |
| Resolved filenames | 🟡 69.87% |
| Text extraction | 🟢 Complete selected text |
| Translation / origin | 🟡 AI draft + reused HU; 3,082/3,082 filled |
| Proofreading | 🟡 Needs proofreading |
| Binary format / need | 🟢 DRM v22 / GFx DefineFont3; Unicode glyph supplement required |
| Binary localization | 🟢 Unicode `ŐőŰű` font and accents user-verified; Steam original restored |
| Game-specific guidance | 🟢 [Osiris guide](docs/GAME_TRANSLATION_GUIDE.md#lara-croft-and-the-temple-of-osiris) |

The [English source export](translations/lara-croft-and-the-temple-of-osiris/en.json) contains 1,744 interface records
and 1,338 subtitles from the selected base and update archives. The
[first Hungarian draft](translations/lara-croft-and-the-temple-of-osiris/hu.json) covers all 3,082 records, using
the existing Hungarian translations as references. Source identities, placeholders, markup and line breaks pass QA.
On 2026-10-18 the full draft passed copy installation, readback of all 3,082 records and two byte-exact restorations.
The writer preserves original archive data and appends translated resources, updating their index entries.
The draft was installed in the Steam English slot, with all 3,082 records verified by readback.
Setup strings are annotated in the JSON;
some labels may also be used by in-game menus. EXE template
reconstruction verified 61 filename candidates, resolving eight unknown names; nine names also match the Guardian of
Light list. A reference-path typo correction resolved one more name. A new 37-file ASCII/UTF-16 scan found no direct
index matches; 1,150 original names remain unresolved.

The user confirmed the translation appears in game. Screenshots first showed missing `ő/Ő`; a fallback-slot repair
then worked in game but displayed circumflexes in the Windows setup dialog. The final supplement instead adds real
Unicode `ŐőŰű` glyphs to five Arial/DIN fonts in the two embedded universal GFx resources. No character substitution
is used. Copy installation and two byte-exact restorations passed.
Both installed Steam font assets matched their packaged hashes,
all 3,082 text records remained unchanged, and readback retains the real Unicode characters. In-game and setup
accents after this final update were verified by the user on 2026-10-18.
An English Square Enix Membership notice still appears in the menu. It was not found in the exported text,
executable strings, or flat resources. The executable contains the `https://notification.os.eidos.com/game/`
endpoint, so we treat the notice as server-delivered rather than part of the local translation package. The current
endpoint response and its direct link to this exact notice have not been verified.

**Remaining:** proofread the installed draft and broaden gameplay and line-wrapping checks. See the
[extraction and filename provenance](translations/lara-croft-and-the-temple-of-osiris/provenance.json). This result
does not establish support for Rise's related archive version.

### Rise of the Tomb Raider

Steam build: `9575745`. **Status:** 🟡 Partial Hungarian draft; interface filled, subtitle import repair in progress.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟡 TIGER v4, `pcx64-w`; earlier partial-package copy install/restore passed; 13 indexes |
| Text formats | 🟢 locals/3: 64-bit unkeyed UTF-8 pointers; CINE/2; SCH/3: optional Version 1 header |
| Resolved filenames | 🟡 85.24%; 6,187 names missing; explicit hash labels do not count as resolved names |
| Text extraction | 🟡 27,113 interface + 28,845 subtitle records; named + detected SCH; other content unclassified |
| Translation / origin | 🟡 Legacy import + AI additions; 27,111 interface fields filled; subtitle draft incomplete |
| Proofreading | 🟡 Incomplete; audited French imports cleared, remaining subtitle imports need review |
| Binary format / need | 🔴 Font localization need not investigated |
| Binary localization | 🔴 No maintained localized assets; appearance and font needs still require verification |
| Game-specific guidance | 🟢 [Rise guidance](docs/GAME_TRANSLATION_GUIDE.md#rise-of-the-tomb-raider) |

[Translation JSON](translations/rise-of-the-tomb-raider/hu.json),
[English source snapshot](translations/rise-of-the-tomb-raider/en.json),
[profile](profiles/rise-of-the-tomb-raider.json),
[provenance](translations/rise-of-the-tomb-raider/provenance.json).
The export includes installed Endurance, Baba Yaga, Cold Darkness and Blood Ties resources.
An additional 1,879 subtitle records in 1,657 physical resources use `unresolved-hash:XXXXXXXX` identity labels;
their real filenames remain unknown. The default profile filelist contains verified names only; provenance
records the supplemental identity-map export and merge. There were 0 skipped resources.
Physical patch layers retain separate identities, so the record count includes repeated source text.
Unknown binary content prevents a claim of complete game text coverage.

All nonblank interface fields are filled; two blank source fields remain null. Exact resource/record/source matches
supplied 19,623 repeated-layer fields, followed by 73 translated fields. All 27,113 interface records passed binary
readback. The first opening ice-climb scene adds 79 distinct Hungarian translations across 239 subtitle records;
seven further scenes and the expedition movie add 155 distinct translations across another 470 records.
Their 217 and 349 affected CINE/SCH resources passed readback with timing, speaker markers and other languages preserved.
The scene batches preserved existing translations. A subsequent cleanup cleared 730 exact, audited French-slot
imports from the Hungarian draft to null; French text is not a translation donor. The French language slot may
host Hungarian output, but its original content is not evidence of Hungarian translation.
There are now 8,618 filled subtitle fields, but 6,517 still equal the English source; 19,596 nonblank subtitle fields
remain null. Other existing translations were preserved. These counts are not a claim of Hungarian subtitle completeness.

The locals/3 and SCH/3 writers are implemented. An earlier partial package passed GUI-backend installation,
byte-exact restoration and a post-restore translation check on a copy. The newly expanded package has targeted
in-memory resource verification, not a new full installation/restore cycle or in-game appearance check.

Optional schema-8 `clear_subtitle_languages_on_overflow` lists subtitle slots that may be cleared, in priority order,
only if the translated resource exceeds the archive-part boundary. It is disabled by default; no language is implicit.
CINE/2 and verified SCH/3 slots support clearing text to spaces while preserving records and timing/speaker markers.
The replacement slot is protected. Insufficient savings or unsupported formats fail safely.
See the [translation configuration guide](docs/TRANSLATING.md#3-translate-the-json).
This capacity fallback has synthetic install/detect/byte-exact restore coverage, not in-game verification.

**Remaining:** continue subtitle translation and import repair, identify intentional foreign-language exceptions,
recover missing names, inspect unclassified resources, investigate fonts, verify the final package and proofread.

### Shadow of the Tomb Raider Trial

Steam build: `3668420`. **Status:** 🟡 Hungarian game test passed; Steam now English.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟡 TIGER v5; append-only selected-locals write and journaled restore |
| Text formats | 🟢 Keyed locals; 64-bit offsets |
| Resolved filenames | 🟡 92.24% |
| Text extraction | 🟡 Partial: keyed table, 38,055 texts |
| Translation / origin | 🟡 Imported HU + 77 completed/reconciled records; 38,055 nonblank fields filled |
| Proofreading | 🟡 Needs review |
| Binary format / need | 🟡 No font replacement required for observed text; full binary inventory incomplete |
| Binary localization | 🟡 Existing assets retained; installed Hungarian appearance user-verified |
| Game-specific guidance | 🟢 [Shadow Trial guidance](docs/GAME_TRANSLATION_GUIDE.md#shadow-of-the-tomb-raider-trial) |

The [Hungarian translation](translations/shadow-of-the-tomb-raider-trial/hu.json) reuses the full-game translation
through stable keys and source comparisons, with Trial-specific differences translated or explicitly accepted.
The earlier package passed a Steam game test on 2026-10-18. The subsequent 77-record completion/reconciliation
retains the Trial's timing markers; records without Trial markers remain unmarked, except the user-approved
1.980-second marker in record 38613. All 38,055 nonblank fields are filled; 1,290 blank source fields remain null.
The updated package passed a complete selected-text-archive GUI-backend copy cycle on 2026-10-26: installation,
installed-state detection, byte-exact and repeated restoration, then renewed translation availability. The original
backup and maintained package remained unchanged. This does not verify the new wording or timing in game.

**Remaining:** review wording and formatting, establish complete text coverage beyond the selected keyed table, and
broaden gameplay checks. See the
[import report](translations/shadow-of-the-tomb-raider-trial/provenance.json).

### Shadow of the Tomb Raider

Steam build: `11668867`. **Status:** 🟡 Hungarian import draft.

| Aspect | Status |
| --- | --- |
| Archive format / support | 🟡 TIGER v5; append-only selected-locals write and journaled restore |
| Text formats | 🟢 Keyed locals; 64-bit offsets |
| Resolved filenames | 🟡 91.41% |
| Text extraction | 🟡 Partial: keyed table, 38,234 texts |
| Translation / origin | 🟡 Imported HU; filled; method unknown |
| Proofreading | 🟡 Needs review |
| Binary format / need | 🔴 Font format/need not assessed |
| Binary localization | 🔴 No replacement; glyph/markup review pending |
| Game-specific guidance | 🟢 [Shadow guidance](docs/GAME_TRANSLATION_GUIDE.md#shadow-of-the-tomb-raider) |

The [Hungarian draft](translations/shadow-of-the-tomb-raider/hu.json) matches all 38,234 populated source records in
the examined text table.

**Remaining:** review translation quality and differences in timing markers, font markup
and private-use glyphs; establish complete game/DLC text coverage and verify writing, restoration and in-game
behavior. See the [extraction/import provenance](translations/shadow-of-the-tomb-raider/provenance.json).

The application provides both a command-line client and a four-step PySide6/Qt WebEngine graphical wizard when run
from source. The repository also contains a filtered PyInstaller one-file build, an Inno Setup installer definition
and a release-validation checklist. A clean native Windows build and clean-machine validation are still required
before publishing a standalone release.

## Features

- Extract interface text and subtitles into one language file, with optional font assets.
- Rebuild Bigfile v1 resources using locals v1, CINE v1 and RAW font handlers.
- Translate Underworld and Guardian of Light Bigfile v2 archives, including DLC and independent patch indexes.
- Export Temple of Osiris English text; write Hungarian resources with copy-verified TIGER v4 restoration.
- Install Temple of Osiris Unicode font supplements with copy-verified restoration and user-verified accents.
- Install supported Shadow keyed tables through the shared dry-run, transaction and restoration workflow.
- Preview changes with a dry run before writing game files.
- Install through a journaled transaction, with allocation and archive index updates.
- Restore original bytes, archive sizes and fonts from saved transaction data.
- Select English or Hungarian application messages independently of the translation language.

## Requirements

**Running from source:**

- Python **3.13 or 3.14**; the development environment currently uses `3.13.16`.
- Your own installation of a supported game/build, with access to its archive files.
- Write access to the game directory and the selected transaction directory when applying a translation.
- Free space for recovery data and temporary archive files. The dry run estimates the required space;
  there is no fixed minimum that fits every game.

The command-line application uses the Python standard library. The graphical client additionally requires PySide6.
Running from source on Windows requires native Windows Python 3.13 or 3.14; Bash and WSL are not required. Git is
needed for the clone command below; you can also download and extract the repository instead.

The standalone build targets **Windows 10 or later**, with Windows 11 as the initial test target. Native Windows
builds need their own environment; a WSL virtual environment cannot be reused for them. The checked-in packaging
workflow is implemented, but no standalone artifact is considered released until the native and clean-machine checks
have passed.

## Quick start

The main examples use **Windows Command Prompt (cmd.exe)** with Python 3.13 installed. Python 3.14 is also supported;
replace `py -3.13` with `py -3.14` when that is the installed version.
Run application commands from the repository root. In these examples, `^` continues a command onto the next line.

```bat
git clone https://github.com/zschopper/pytrtt.git
cd pytrtt
py -3.13 -m pytrtt --help
```

For a new checkout, create your machine-local configuration:

```bat
if not exist pytrtt.local.toml copy pytrtt.local.example.toml pytrtt.local.toml
```

Edit the relevant `install_dir` under `platforms.windows.games` for your installation.
The example contains placeholder paths; `pytrtt.local.toml` is ignored by Git. Keep an existing local
configuration when updating your checkout. An explicit `--game-dir "PATH"` overrides its installation path.

### Start the graphical client

Install the project and its PySide6 runtime dependency, then start the client from Windows Command Prompt or
PowerShell:

```bat
py -3.13 -m pip install -e .
scripts\run-gui.cmd
```

The graphical client displays the application version from `project.version` in `pyproject.toml`. Its English or
Hungarian interface preference is stored in `%LOCALAPPDATA%\PyTRTT\settings.ini`.

The graphical client discovers Steam and Epic Games installations, also accepts a custom folder, and uses the same
translation, validation and recovery services as the CLI. Its four visible steps cover game selection, installation
selection, operation and language selection, and progress/results. If a previous modifying operation was interrupted,
startup offers to restore the affected installation from its retained journal before normal use. Translation credits
embedded in a supported language file are available from the progress/result page.

Installed-state checks also validate a known build ID. If a revised translation package no longer matches the
installed text, an intact journal matching the current archive hashes enables **Verified restoration available**;
restore first, then check and install the new package. Recovery uses the journal's saved runtime and follows
applicable earlier patch journals. A different package must not bypass source-text or recovery-integrity checks.

### Why update checks and progress are separate

These checks address failures encountered while updating real translations, not just first-time installation:

- A source-text translation memory is not an installable, build-bound package. The GUI distinguishes missing record
  binding from unknown game modifications instead of treating the memory as a valid installation package.
- A previously translated string can differ from both the original English and a revised package's expected output.
  This does not alone prove file damage. Verified journals allow restoration before updating, while source validation
  and complete-file/payload integrity checks remain mandatory.
- A resource counter reaching 100% does not mean file copying, hashing, index planning or journal finalization has
  finished. Separate phase and byte progress explain this remaining work; debug logs record the package, build,
  resource identity and expected/actual text details when validation fails.

The Windows source launcher enables debug logging. The default log is
`%LOCALAPPDATA%\PyTRTT\logs\pytrtt-debug.log`; include the relevant failure details when reporting a problem.
TR2013's Setup and in-game interface share some strings but use different rendering contexts. Its maintained fonts
now support actual Hungarian double-acutes, avoiding the former need to choose between circumflexes in Setup and
missing glyphs in game. See the [game-specific verification limits](#tomb-raider-2013).

### Preview a translation

This example uses the configured Anniversary installation and bundled Hungarian language file:

```bat
py -3.13 -m pytrtt ^
  --translation-file translations/tomb-raider-anniversary/hu.json --ui-language en
```

The default action is a dry run: it reports the planned resource changes, recovery data size and
available space without modifying the game directory. Use `--ui-language hu` for Hungarian messages.

### Install and restore

Close the game before applying a translation, and wait for Steam downloads or updates to finish. The supplied GUI
launcher stores recovery journals below `<game directory>/PyTRTT Recovery/`; do not delete that directory while a
translation may still need restoration. The CLI defaults to
`<program directory>/transactions/<game-id>/<timestamp>/`. The GUI also searches the portable transaction root, the
`dist/transactions` root created by a standalone executable run from a source checkout, the former
`work/transactions` location and the user-data transaction folder for existing journals. Existing backups remain in
their original locations. CLI reports retain their user-data location.

The installation selector keeps separate folder choices for multiple copies of the same game. Status is checked
from the selected folder's files. A recovery journal must match that exact installation path and the saved file
hashes, so restoring one copy does not restore another copy with identical translated data.

Use `--transaction-dir` to choose a different, new transaction directory:

```bat
py -3.13 -m pytrtt ^
  --translation-file translations/tomb-raider-anniversary/hu.json ^
  --apply --transaction-dir work/transactions/tra/my-install
```

Keep the transaction directory: it contains the journal, original byte ranges and original RAW font
needed for restoration. Permanent full-archive backups are not required, although temporary staging
files can contain entire archive parts.

Restore the same installation using its saved transaction:

```bat
py -3.13 -m pytrtt ^
  --restore --game tra --transaction-dir work/transactions/tra/my-install
```

The transaction records the runtime settings, so restoration does not need the translation file or
a developer profile. It refuses unexpected archive changes. Restore before installing another
translation; automatic detection of an already installed package is still planned.

### Linux/WSL source usage

With Python 3.13 or 3.14 available, use the same CLI arguments with your interpreter instead of `py -3.13`:

```bash
python3.13 -m pytrtt --translation-file translations/tomb-raider-anniversary/hu.json --ui-language en
```

For a new checkout, create the configuration with `cp -n pytrtt.local.example.toml pytrtt.local.toml`
and set the `linux` installation paths. If using the supplied development environment, replace `python3.13`
with `bash scripts/dev.sh run --locked python`.

These source-usage examples match the current CLI. The Windows commands have not been executed as part
of this documentation update; native Windows application verification remains separate from Linux/WSL checks.

## Development and testing

The supplied setup and check scripts target **x86-64 Linux/WSL** and require Bash, Git, curl and network
access for setup. They install project-local Python and locked tools without changing the system interpreter
or shell profiles. Run from the repository root:

```bash
bash scripts/setup.sh
```

The setup script installs the development and packaging dependencies and runs the complete checks.
For subsequent checks:

```bash
# Complete checks: Ruff, formatting, strict mypy, Markdown and unit tests.
bash scripts/check.sh

# Unit tests only; no installed games or network access are required.
bash scripts/dev.sh run --locked pytest -q

# Optional local integration tests; select only the games you want to test.
bash scripts/dev.sh run --locked pytest --game tra -m integration -q
bash scripts/dev.sh run --locked pytest --game trld -m integration -q
```

Integration tests use local samples and original/translated game copies. Configure `samples_dir`,
`original_dir` and `translated_dir` in the local TOML file, or use the explicit pytest path options.
Missing optional samples are skipped. An installation path alone does not enable integration tests.
New behavior is developed with TDD; binary changes must preserve verified byte-level results.

### Standalone release data

Build the executable from native Windows Command Prompt with:

```bat
scripts\build-windows.cmd --clean
```

The script generates synchronized Windows version metadata, builds `dist\PyTRTT.exe`, and runs its packaged GUI smoke
test. To also create `dist\installer\PyTRTT-<version>-setup.exe`, pass `--installer` (optionally together with
`--clean`):

```bat
scripts\build-windows.cmd --clean --installer
```

Installer builds require Inno Setup 6. If it is missing, the standalone executable remains available but the script
exits with code 2 after reporting that the installer was not created. Complete the
[Windows GUI smoke checklist](docs/windows-gui-smoke-checklist.md) before publishing either artifact.

The Windows one-file build recursively includes release resources below `pytrtt/resources/`. Project-relative glob
exclusions are maintained in [`packaging/package-data.ignore`](packaging/package-data.ignore). Blank lines and lines
beginning with `#` are ignored. Rules are applied in order, and a later rule beginning with `!` includes a path excluded
by an earlier rule. For example:

```gitignore
**/.backups/**
pytrtt/resources/filelists/**
!pytrtt/resources/filelists/release-required.txt
```

Translation data uses an allowlist: every `package_available` document named by `gui_games.json` and every font asset
referenced by those documents is included automatically. Other translation files, including source exports, memories,
candidate lists and provenance, stay outside the executable. Whenever a publishable runtime file is added, moved or
removed, review this selection boundary. Add a new resource collection root to
[`packaging/pytrtt.spec`](packaging/pytrtt.spec) only when the file belongs outside the existing roots. Update
[`tests/test_package_data.py`](tests/test_package_data.py) when selection rules change, and verify a clean native Windows
build before release. Local backups, work products and reference material must remain outside the packaged data.

Before replacing `dist\PyTRTT.exe`, the Windows build archives the existing executable using its embedded product
version, for example `PyTRTT-v0.2.0.exe`. If that name already exists, it appends the first available numeric component:
`PyTRTT-v0.2.0.1.exe`, `PyTRTT-v0.2.0.2.exe`, and so on. An unreadable or invalid embedded version stops the build
instead of overwriting the previous executable.

| Directory | Purpose |
| --- | --- |
| `pytrtt/` | Shared services, format contracts, implementations, CLI and message catalogs |
| `profiles/` | Developer game settings; compiled into language files |
| `translations/` | Language files, provenance and required font assets |
| `scripts/` | Setup, extraction, compilation and maintenance tools |
| `tests/` | Game-independent tests and optional game integration tests |
| `ai-guidance/` | Task-specific contributor guidance |
| `work/` | Private planning documents, samples, exports, reports and transactions; ignored by Git |
| `references/` | Local historical and external references; ignored by Git |

The CLI and Qt GUI reuse the same service layer. Protocol contracts and explicit dependency wiring keep archive and
resource handling independent of game identities and user interfaces.
See the [contributor guidelines](AGENTS.md) for task-specific development guidance.

## Roadmap

- Complete the experimental game projects and verification tasks listed above.
- Produce and validate a clean native Windows EXE and installer; complete manifest-based translation packages.
- Complete the versioned release support registry and restoration previews.
- Support more archive versions, games and installed DLCs through tested handlers and profiles.
- Complete Windows scaling, accessibility and clean-machine release checks for the Qt GUI.

## Translation credits

The translations are collaborative works created by external contributors and communities;
the credits belong to those contributors. See [TRANSLATION_CREDITS.md](TRANSLATION_CREDITS.md) for attribution notes.

## Support and contributions

Report reproducible problems through [GitHub Issues](https://github.com/zschopper/pytrtt/issues).
Include the tool version, operating system, game/build, selected language and steps to reproduce.
For translation problems, send the generated diagnostic report to
[tombraidertranslations@gmail.com](mailto:tombraidertranslations@gmail.com).
Reports are stored in the user data directory; the CLI prints their location and does not send email automatically.

Want to translate a supported game into another language? Start with the [translation guide](docs/TRANSLATING.md),
then read the [game-specific guidance](docs/GAME_TRANSLATION_GUIDE.md) for the selected title.
Contributions to code, translations and testing are welcome. Include relevant checks with code changes;
new game support needs a profile and evidence from extraction, translation and restoration tests.

## License

The PyTRTT program code is licensed under the [MIT License](LICENSE).
This license does not automatically cover translation text, fonts, game data or external reference code;
those materials retain their respective rights and credits.
