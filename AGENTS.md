# PyTRTT Agent Instructions

PyTRTT is a Python Tomb Raider Translation Toolkit. These instructions apply to this repository;
parent Laravel/PHP guidance does not apply.

- Read [ai-guidance/README.md](ai-guidance/README.md), then only the guidance needed for the current task.
- Keep guidance in English. Discuss work in Hungarian unless the user requests another language.
- When available, use the private `work/docs/project_hu.md` as the single source of local project status and decisions.
  Read relevant sections only; otherwise use README, maintained artifacts, and the current task.
  Do not treat proposals as accepted decisions or require private files in a fresh clone.
- Preserve existing behavior, user edits, staged changes, and unrelated files. Commit or publish only when requested.
- Run project commands from the repository root through `bash scripts/dev.sh`; do not alter system Python or shell profiles.
- Before editing an existing document, preserve its original bytes in the adjacent `.backups/` directory:
  `bash scripts/dev.sh run --locked python scripts/backup_document.py PATH`.
  Use Europe/Budapest timestamps; never overwrite backups. If a timestamp collides, retry in the next second.
- For documentation tasks, read [ai-guidance/documentation.md](ai-guidance/documentation.md).
  Private documents under `work/docs/` also follow their local `AGENTS.md`.
- Local paths and installed games do not authorize writing to game installations or running integration tests.
  Use explicit output paths and game copies for verification; preserve the first recovery backup.
