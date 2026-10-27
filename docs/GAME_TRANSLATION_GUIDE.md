# Game Translation Guidance

This document supplements the [translation workflow](TRANSLATING.md) with the details that are specific to each
supported game. Support is tied to the exact builds in the [current support table](../README.md#current-support);
contact the maintainer before starting a different build, platform, edition, or DLC set.

## Adding Your Language

Start by telling the maintainer which game, exact build, platform, DLC set, and language you want to translate. The
maintainer can provide a build-specific JSON template, an English story transcript where one exists, or both. Translate
only the `translation` values in JSON, or translate the dialogue in the transcript while retaining its headings,
speakers, order, notes, and repeated lines. Preserve JSON identifiers, source text, placeholders, control codes, markup,
timing data, and meaningful line breaks. Record translator and reviewer credits, note intentional exceptions, and
review the result in context. Send the completed JSON translation and/or translated transcript to the maintainer, who
will match transcript lines to the exact game records, bind translation-memory content when necessary, prepare any
required fonts and runtime settings, validate installation and restoration on the supported build, and create the
release. Translators do not need to edit game archives or build the release themselves.

Existing translations may be used as translation memory, but a memory is a language reference rather than an
installable package: one memory unit can match several physical occurrences, and similar source text can have different
meanings in different scenes. The maintainer reconciles it against a fresh extraction using source language, exact text,
resource identity, record identity, and context, and rejects conflicting matches. Working English transcripts are also
editorial aids rather than binary release content; walkthrough order and scene boundaries help translation, while the
game export remains the authoritative source for exact wording, repeated records, markers, and identifiers. A release
contains only the tested, build-bound language documents and their required assets, not source exports, memories,
working transcripts, provenance notes, or local recovery data.

You can also help translate the PyTRTT application by contributing a catalog matching
[`pytrtt/resources/locales/en.json`](../pytrtt/resources/locales/en.json). The application language and the target
language of a game translation are independent, so an application catalog can be contributed with or without a game
translation.

## Tomb Raider: Legend Demo

The Legend Demo uses the older Bigfile/1 archive with separate interface and CINE/1 subtitle text, and it needs a
language-appropriate RAW font for characters not covered by the original game. Its setup program is a separate
non-Unicode component, so accented setup text must also be checked with the target language selected for non-Unicode
Windows programs. Keep the demo translation separate from the full Legend package even when much of the wording is
shared.

## Tomb Raider: Legend

Legend uses Bigfile/1, locals/1 interface text, and CINE/1 subtitles; a complete language package may also need a RAW
replacement font. Translate the extracted full-game records rather than treating the Demo as an installable template,
and check menus, HUD text, subtitles, accented characters, and line wrapping in the supported full-game build.

## Tomb Raider: Anniversary

Anniversary uses the same broad Bigfile/1, locals/1, and CINE/1 format family as Legend, but its identifiers, resources,
and translation package are build-specific. Languages that need characters outside the stock font require a verified
RAW replacement font. The maintained Brazilian Portuguese package is still a draft, so it is useful reference material
only after its wording and in-game behavior have been independently reviewed.

## Tomb Raider: Anniversary Demo

The Anniversary Demo has its own build and package even though its maintained text is derived from the full game. Its
translatable game interface and subtitles can use the Anniversary wording where source records match, but the setup
program's error dialogs remain English in the verified Hungarian configuration. Test the demo and its setup behavior
separately rather than assuming the full-game result applies.

## Tomb Raider: Underworld

Underworld uses Bigfile/2 archives, including independently indexed archive families, and its maintained package covers
interface and subtitle formats that differ from the Legend-era games. The current Steam font does not contain all
Hungarian double-acute glyphs, while the official Hungarian font uses a different table and atlas; compatible font
replacement is still pending. For a new language, identify required glyphs early and let the maintainer prepare and
verify font assets instead of copying assets or substitutions from another game.

## Tomb Raider: Underworld Demo

The Underworld Demo currently has only a limited archive-index inventory: it has no dedicated profile, verified text
extraction, or installable translation package. Do not start by adapting the full Underworld JSON, because the demo's
text formats, resource identities, and build behavior have not been established. Contact the maintainer first so the
demo can be researched and a build-specific template can be produced before translation begins.

## Lara Croft and the Guardian of Light

Guardian of Light uses Bigfile/2 with base, patch, and five DLC layers, so identical-looking text may occur in several
physical resources that must retain their own identities. Its historical translation survives as a source-text memory;
placeholders such as `{0}` must be rebound to the actual control icon in each target record instead of copied literally.
The current Hungarian package uses a verified font supplement and a runtime mapping from double-acute characters to
repaired fallback glyph slots; that mapping is specific to that package and must not be reused automatically for another
language. Translation and testing should cover the installed DLC set as well as the base game.

## Tomb Raider (2013)

Tomb Raider (2013) combines TIGER/3 archives with locals/2 interface text, CINE/2 cinematics, SCH/1 subtitles, and fonts
embedded in DRM collections. Its historical TMX import is a source-text memory: legacy `tuid`, CINE block numbers, and
SCH timestamps are context, not unique game-record IDs, and one memory unit may cover several occurrences. It must be
bound to a fresh extraction of the exact supported build before release, with Russian-source entries kept distinct from
English ones. Keep the resulting package and its font assets together, use real Unicode text without inheriting the old
Hungarian circumflex substitution, and check both cinematic and in-game subtitle paths because successful archive
validation does not prove that every screen or scene renders correctly.

## Lara Croft and the Temple of Osiris

Temple of Osiris uses TIGER/4 archives selected through several base, language, and update indexes; replacements are
appended instead of rewriting the original archive data. Its fonts use embedded GFx resources, and the maintained
Hungarian package adds real Unicode glyphs rather than character substitutions. Some online notices can be delivered by
a server and may not exist in the extracted game text, so report an apparently untranslated notice before adding a
guessed local record; also follow the game's terminology notes in its translation provenance.

## Rise of the Tomb Raider

Rise uses TIGER/4 with many physical patch and DLC layers, locals/3 interface text, and both CINE/2 and SCH/3 subtitles.
Repeated records are intentional, source-only matching can mix contexts, and text imported from the French slot is not
evidence of a target-language translation. Its English story transcript follows walkthrough order and deliberately
excludes repeated combat alerts and unrelated ambient dialogue; translate repeated lines as supplied, because they may
represent distinct heard variants, and do not silently expand its editorial scope. Preserve each resource identity,
timing and speaker metadata when the maintainer transfers the transcript into JSON, and flag intentional
foreign-language dialogue. Subtitle capacity fallback and language-slot clearing are maintainer-controlled technical
settings. Keep Hungarian `ŐőŰű` as real Unicode in the translation JSON: the maintained DIN-Bold font candidate adds
these missing glyphs, while DIN Next CYR already includes them. Do not reintroduce circumflex substitutions or alter
the multilingual `FONT VALIDATION` developer samples. Font appearance still requires an in-game check; see the
[package provenance](../translations/rise-of-the-tomb-raider/provenance.json) for current verification scope.
Unclassified content remains outside the extracted-text coverage claim.

## Shadow of the Tomb Raider Trial

The Trial uses a selected keyed-locals table in TIGER/5 archives, and stable keys can reuse full-game wording only when
the source and Trial context agree. Do not copy full-game timing markers into Trial records: preserve the Trial's own
markers and leave unmarked records unmarked unless a specific exception is approved. Current support covers the selected
text table rather than every possible localized asset, so wording, formatting, glyphs, and gameplay appearance still
need Trial-specific review.

## Shadow of the Tomb Raider

The full game also uses keyed locals in TIGER/5, but its records and supported build are separate from the Trial. Its
English story transcript is ordered against a walkthrough and can be translated as a coherent script, but the extracted
keyed table remains authoritative when the maintainer maps that script back into the package. Keep keys, record IDs,
timing markers, font markup, and private-use glyphs exactly as extracted while translating the visible text. Current
extraction and writing support targets the selected keyed table, so do not claim complete game or DLC coverage until
the maintainer has classified the remaining resources and verified installation, restoration, fonts, and in-game
behavior.
