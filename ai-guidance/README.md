# Task Guidance

Load the union of files needed for the actual work. Do not load every domain merely because this is a translation tool.
Paths below are relative to this directory. Root instructions always apply.

- Planning, priorities, decisions, status: [planning.md](planning.md).
- New or extended game/build/language project: [translation/project-workflow.md](translation/project-workflow.md).
- Translate/proofread strings: [guidelines](translation/guidelines.md),
  [terminology](translation/terminology.md), [QA](translation/quality-assurance.md).
- Python behavior, architecture, dependencies: [architecture](development/architecture.md),
  [coding standards](development/coding-standards.md), [testing](development/testing.md).
- Environment, tools, local paths, packaging: [environment](development/environment.md).
- Extract, inspect, rebuild, install, restore: [archives](file-formats/archive-handling.md),
  [binary safety](file-formats/binary-safety.md), [encoding](file-formats/text-encoding.md).
- Historical code, reference translations, provenance: [references.md](references.md).
- Documents, including these instructions: [documentation.md](documentation.md).

For a new translation project, start with its workflow and load domain guidance as each phase needs it.
For import/export code, combine Development, translation QA, and File Formats; add language guidance if editing prose.
For a dependency-injection refactor, load Development only. Planning alone does not require binary-format guidance.

Keep instructions durable: workflows and invariants belong here; current counts, builds, paths, and results belong
in the project plan or provenance/report files. Link to those sources instead of duplicating their contents.
