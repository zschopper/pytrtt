# PyTRTT Agent Instructions

PyTRTT is a Python Tomb Raider Translation Toolkit. These instructions apply to this repository;
parent Laravel/PHP guidance does not apply.

- If `guidance/user-local-guidance.md` exists, read it first and apply it as the highest-priority repository guidance.
  Its local decisions override conflicting instructions in this file, `ai-guidance/`, and nested repository guidance,
  subject to system/developer instructions and the user's explicit task instructions.
  It is optional, private, and Git-ignored; do not require or create it in another maintainer's checkout.
- Read [ai-guidance/README.md](ai-guidance/README.md), then only the guidance needed for the current task.
- Keep repository guidance in English.
- Preserve existing behavior, user edits, staged changes, and unrelated files. Commit or publish only when requested.
- Run project commands from the repository root through `bash scripts/dev.sh`; do not alter system Python or shell profiles.
- For documentation tasks, read [ai-guidance/documentation.md](ai-guidance/documentation.md).
- Local paths and installed games do not authorize writing to game installations or running integration tests.
  Use explicit output paths and game copies for verification; preserve the first recovery backup.
