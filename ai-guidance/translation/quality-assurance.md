# Translation Quality Assurance

- Compare source and translation for omissions, additions, meaning, fluency, grammar, voice, and terminology.
- Reconcile source/translation entries by resource and identifier; report missing strings and unexpected duplicates.
  Preserve intentional repeated text and empty source entries.
- Verify placeholders, markup, control sequences, line breaks, escape sequences, comments, and identifiers.
- Distinguish missing `translation` (original retained and reported) from explicit `translation: ""`
  (written as a single space). Do not normalize source whitespace or silently fill missing translations.
- Validate the actual package schema/runtime, referenced asset hashes, encoding, and target-format constraints.
  Load File Formats guidance for resource writing; use the project workflow for dry run/apply/restore/game verification.
- Report unresolved items and actual coverage with entry references; do not equate complete text data with game support.
