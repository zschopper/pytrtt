# Testing and Verification

- For new behavior, first write a behavior test and confirm it fails for the expected reason; implement minimally,
  then refactor with green tests. Include meaningful error and boundary cases.
- Use temporary directories and protocol fakes for unit tests; avoid internal mocks, network, and installed games.
  Expected bytes/fixtures must be independent of the implementation's formulas.
- Verify shared services with game-independent fixtures as well as targeted game tests.
  Hypothesis supplements deterministic examples. Toolchain smoke tests do not prove translator correctness.
- Game-sample tests require `integration`, `game(ID, build=BUILD)`, and `game_samples`.
  Missing optional samples use `game_samples.require(...)` to skip. Default pytest excludes integration tests.
- Run integration tests only when explicitly requested, on copies:
  `bash scripts/dev.sh run --locked pytest --game tra -m integration`.
  Repeat `--game` for multiple games; `--samples-dir PATH` and `--game-copy tra=PATH` override sample locations.
- Run checks appropriate to the change and report their actual results. Full checks: `bash scripts/check.sh`;
  targeted tests: `bash scripts/dev.sh run --locked pytest tests/TEST_FILE.py -q` (replace the filename).
- New source directories must be covered by Ruff, mypy, and the check script.
  Documentation changes require Markdown lint; no new behavior tests are needed for prose-only edits.
- For binary changes, verify structural invariants, unchanged bytes, and restoration, not just successful execution.
  Review the final diff for accidental edits; claim in-game success only after an actual game test.
