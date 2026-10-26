# Translation Project Workflow

Use this workflow for a new game, build, DLC combination, or target language. Resume at the first unfinished phase;
do not repeat verified work unless inputs changed. Read `../planning.md` when updating scope, decisions, or status.

1. **Scope and evidence.** Identify game/platform/build/DLC, source and target languages, replacement language slot,
   requested output, and existing support. These languages and the UI language are separate.
   Read relevant project-plan sections; resolve local paths from TOML. Verify build and file stability before sampling.
   Load `../references.md` if using historical code or translations; record provenance and exact source revisions.
2. **Format and profile.** Load File Formats guidance before extraction or binary work.
   Confirm archive and text variants independently. Reuse verified handlers through a declarative profile;
   if a handler is missing, load Development guidance and implement/test it before claiming support.
   Keep game-specific behavior in profile data, not Python game branches.
3. **Read-only extraction.** Use `scripts/extract_strings.py` with an explicit profile, build, languages,
   game directory, and fresh output directory outside the game. Check its `--help` for current options.
   Store local outputs and samples in separate Git-ignored directories, using optional local guidance for their layout.
   Reconcile counts, empty/skipped resources, source text, and identifiers before translating.
4. **Translation package.** Load language guidelines, terminology, and QA for prose work.
   Keep maintained data in `translations/<game>/<language>.json`, required assets in `assets/`, and source evidence
   in provenance files. Preserve source records and translate in contextual batches; track unresolved/missing entries.
   Include validated `metadata.runtime`; `scripts/compile_translation.py` can embed a profile in a legacy document.
   Check current schema and parser behavior before introducing fields; accepted future schema changes are not available yet.
5. **Verification.** Load translation QA and File Formats guidance. Validate the package and run a read-only dry run
   with `python -m pytrtt --translation-file PATH --game-dir COPY` through the project wrapper.
   Exercise a representative small copy, then a full copy: apply with a transaction journal, restore, and compare
   original file sizes and SHA-256 values. Preserve the first recovery data; use explicit transaction/output paths.
   Test long/accented text, placeholders, empty/missing translations, language slots, and any font substitutions.
6. **Game test and handoff.** Check interface text, subtitles, line wrapping, glyphs, and language/DLC behavior in the game.
   Record extraction, writing, restoration, and appearance results separately for the exact build and language.
   Update the existing project plan and provenance with checks, remaining gaps, and the next action.
   Prepare releases only when requested, using accepted release decisions and verified assets; commit/publish when instructed.

Keep JSON text in correct Unicode. Do not copy another game's font, character substitutions, or language-slot
clearing/omission strategy without verifying it. Investigate font changes only when text display actually requires them;
install prepared assets, do not implement BMP editing in the translator.
