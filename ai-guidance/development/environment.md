# Environment and Tooling

- Develop in WSL/Linux; the standalone Windows release requires a separate native Windows build environment.
- Use `.python-version`, `pyproject.toml`, and `uv.lock` as the version/dependency sources.
  `scripts/dev.sh` selects project-local pyenv, CPython, uv, and `.venv`; do not use system Python.
- Setup: `bash scripts/setup.sh`; locked sync: `bash scripts/dev.sh sync --locked --all-groups`.
  Setup or sync may need network access; do not run them when the existing environment suffices.
- Add dependencies only for a concrete need; update and verify the lockfile when dependencies change.
- Machine paths belong in ignored `pytrtt.local.toml`; its tracked template is `pytrtt.local.example.toml`.
  Use `pytrtt/environment.py` for application, tool, and test path resolution; preserve existing local configuration.
- Explicit CLI paths take precedence. Tests use `original_dir`/`translated_dir`, not the installed game by default.
  Distinguish working directory, explicit game directory, and tool location.
- Local configuration is neither a game profile nor translation data; exclude it from language JSON and releases.
- `.tools/`, `.venv/`, caches, `.backups/`, `references/`, and `work/` are local material, not release content.
  Keep required runtime filelists in `pytrtt/resources/filelists/` and font assets inside translation packages.
- For release tasks, read the accepted packaging/version/license decisions in the project plan;
  do not treat a planned Windows build or manifest as implemented.
