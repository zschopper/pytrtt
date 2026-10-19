# Documentation

- Git-tracked documents use Git history. Apply any private document backup policy from optional local guidance.
- Use UTF-8, LF, and a final newline. Use one top-level heading, sequential heading levels, blank lines around
  headings/lists/code blocks, language-tagged code fences, and prose lines of at most 120 characters.
  Avoid tabs and trailing spaces; do not artificially wrap tables or code blocks.
- Keep public guidance in English. Do not require private files in published instructions or public checks.
- Distinguish requirements, decisions, proposals, implementation, and verified results. Link technical claims to files
  or exact commits; verify local links and commands, and label commands not actually run.
- Update superseded statements when requirements change. Maintain one local project plan and its decision lists.
- Run the project Markdown linter after document changes. Do not hide failures by broadly disabling rules.
  Public documents are checked by `bash scripts/check.sh`; check changed private documents explicitly with the same config.
