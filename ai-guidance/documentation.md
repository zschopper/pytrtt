# Documentation

- Follow the root instructions for backups before each existing-document edit, including lint fixes.
  Never overwrite, lint, format, or automatically delete `.backups/` contents.
- Use UTF-8, LF, and a final newline. Use one top-level heading, sequential heading levels, blank lines around
  headings/lists/code blocks, language-tagged code fences, and prose lines of at most 120 characters.
  Avoid tabs and trailing spaces; do not artificially wrap tables or code blocks.
- Keep public guidance in English. Private `_hu` documents remain Hungarian under ignored `work/docs/`;
  follow `work/docs/AGENTS.md` when editing them. Do not require private files in published instructions or public checks.
- Distinguish requirements, decisions, proposals, implementation, and verified results. Link technical claims to files
  or exact commits; verify local links and commands, and label commands not actually run.
- Update superseded statements when requirements change. Maintain one local project plan and its decision lists.
- Run the project Markdown linter after document changes. Do not hide failures by broadly disabling rules.
  Public documents are checked by `bash scripts/check.sh`; check private documents explicitly when they change:

```bash
bash scripts/dev.sh run --locked pymarkdown --config .pymarkdown.json scan work/docs/AGENTS.md work/docs/project_hu.md
```
