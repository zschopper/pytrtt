# PyTRTT - Tomb Raider Translation Toolkit

*Forged in Python, Built for Adventure.*

PyTRTT extracts, installs and restores Tomb Raider translations. It is the Python successor to the
C# TRTR2 project, with shared archive and resource handlers selected by format and version.

Translations are editable UTF-8 JSON files, grouped by resource, with source text, translation and
translator comments. Game profiles supply technical settings during development; compiled language
files carry the configuration needed to apply the translation.

## Current support

| Game | Platform / Steam build | Language | Status |
| --- | --- | --- | --- |
| Tomb Raider: Anniversary | PC Steam / `842717` | Hungarian | Supported: menus, subtitles and font replacement |
| Tomb Raider: Anniversary | PC Steam / `842717` | Brazilian Portuguese | Draft; review and in-game testing pending |
| Tomb Raider: Legend | PC Steam / `251820` | Hungarian | Supported: menus, subtitles and font replacement |
| Tomb Raider: Legend Demo | PC Steam / `251815` | Hungarian | Supported: menus, subtitles and font replacement |
| Shadow of the Tomb Raider Trial | PC Steam / `3668420` | — | Next project; no translation yet |

The Anniversary, Legend and Legend Demo translations are supported for the listed Steam builds. Shadow Trial
requires archive/text format investigation and new support before translation work. Other games and formats are planned.
The current application runs from source through a CLI. A standalone Windows executable and a GUI
are planned; their build and distribution workflows are not available yet.

## Features

- Extract menu and subtitle text into one language file, with optional font assets.
- Rebuild Bigfile v1 resources using locals v1, CINE v1 and RAW font handlers.
- Preview changes with a dry run before writing game files.
- Install through a journaled transaction, with allocation and archive index updates.
- Restore original bytes, archive sizes and fonts from saved transaction data.
- Select English or Hungarian application messages independently of the translation language.

## Requirements

**Running from source:**

- Python **3.13**; the development environment uses `3.13.16`.
- Your own installation of a supported game/build, with access to its archive files.
- Write access to the game directory and the selected transaction directory when applying a translation.
- Free space for recovery data and temporary archive files. The dry run estimates the required space;
  there is no fixed minimum that fits every game.

The application currently has no third-party runtime dependencies. Running it from source on Windows
requires native Windows Python 3.13; Bash and WSL are not required. Git is needed for the clone command below;
you can also download and extract the repository instead.

The planned standalone release targets **Windows 10 or later**, with Windows 11 as the initial test target.
It will use a PyInstaller onefile EXE and will not require a separate Python installation.
Native Windows builds need their own environment; a WSL virtual environment cannot be reused for them.

## Quick start

The main examples use **Windows Command Prompt (cmd.exe)** with Python 3.13 installed.
Run application commands from the repository root. In these examples, `^` continues a command onto the next line.

```bat
git clone https://github.com/zschopper/pytrtt.git
cd pytrtt
py -3.13 -m pytrtt --help
```

For a new checkout, create your machine-local configuration:

```bat
if not exist pytrtt.local.toml copy pytrtt.local.example.toml pytrtt.local.toml
```

Edit the relevant `install_dir` under `platforms.windows.games` for your installation.
The example contains placeholder paths; `pytrtt.local.toml` is ignored by Git. Keep an existing local
configuration when updating your checkout. An explicit `--game-dir "PATH"` overrides its installation path.

### Preview a translation

This example uses the configured Anniversary installation and bundled Hungarian language file:

```bat
py -3.13 -m pytrtt ^
  --translation-file translations/tomb-raider-anniversary/hu.json --ui-language en
```

The default action is a dry run: it reports the planned resource changes, recovery data size and
available space without modifying the game directory. Use `--ui-language hu` for Hungarian messages.

### Install and restore

Close the game before applying a translation, and wait for Steam downloads or updates to finish.
Choose a new transaction directory for each installation:

```bat
py -3.13 -m pytrtt ^
  --translation-file translations/tomb-raider-anniversary/hu.json ^
  --apply --transaction-dir work/transactions/tra/my-install
```

Keep the transaction directory: it contains the journal, original byte ranges and original RAW font
needed for restoration. Permanent full-archive backups are not required, although temporary staging
files can contain entire archive parts.

Restore the same installation using its saved transaction:

```bat
py -3.13 -m pytrtt ^
  --restore --game tra --transaction-dir work/transactions/tra/my-install
```

The transaction records the runtime settings, so restoration does not need the translation file or
a developer profile. It refuses unexpected archive changes. Restore before installing another
translation; automatic detection of an already installed package is still planned.

### Linux/WSL source usage

With Python 3.13 available, use the same CLI arguments with your interpreter instead of `py -3.13`:

```bash
python3.13 -m pytrtt --translation-file translations/tomb-raider-anniversary/hu.json --ui-language en
```

For a new checkout, create the configuration with `cp -n pytrtt.local.example.toml pytrtt.local.toml`
and set the `linux` installation paths. If using the supplied development environment, replace `python3.13`
with `bash scripts/dev.sh run --locked python`.

These source-usage examples match the current CLI. The Windows commands have not been executed as part
of this documentation update; native Windows application verification remains separate from Linux/WSL checks.

## Development and testing

The supplied setup and check scripts target **x86-64 Linux/WSL** and require Bash, Git, curl and network
access for setup. They install project-local Python and locked tools without changing the system interpreter
or shell profiles. Run from the repository root:

```bash
bash scripts/setup.sh
```

The setup script installs the development and packaging dependencies and runs the complete checks.
For subsequent checks:

```bash
# Complete checks: Ruff, formatting, strict mypy, Markdown and unit tests.
bash scripts/check.sh

# Unit tests only; no installed games or network access are required.
bash scripts/dev.sh run --locked pytest -q

# Optional local integration tests; select only the games you want to test.
bash scripts/dev.sh run --locked pytest --game tra -m integration -q
bash scripts/dev.sh run --locked pytest --game trld -m integration -q
```

Integration tests use local samples and original/translated game copies. Configure `samples_dir`,
`original_dir` and `translated_dir` in the local TOML file, or use the explicit pytest path options.
Missing optional samples are skipped. An installation path alone does not enable integration tests.
New behavior is developed with TDD; binary changes must preserve verified byte-level results.

| Directory | Purpose |
| --- | --- |
| `pytrtt/` | Shared services, format contracts, implementations, CLI and message catalogs |
| `profiles/` | Developer game settings; compiled into language files |
| `translations/` | Language files, provenance and required font assets |
| `scripts/` | Setup, extraction, compilation and maintenance tools |
| `tests/` | Game-independent tests and optional game integration tests |
| `ai-guidance/` | Task-specific contributor guidance |
| `work/` | Private planning documents, samples, exports, reports and transactions; ignored by Git |
| `references/` | Local historical and external references; ignored by Git |

The shared service layer can be reused by a future GUI. Protocol contracts and explicit dependency
wiring keep archive and resource handling independent of game identities and user interfaces.
See the [contributor guidelines](AGENTS.md) for task-specific development guidance.

## Roadmap

- Investigate Shadow of the Tomb Raider Trial archive/text formats and implement read-only text extraction.
- Build and test the standalone Windows EXE and manifest-based translation packages.
- Add package/installation state detection, game discovery and restoration previews.
- Support more archive versions, games and installed DLCs through tested handlers and profiles.
- Add a GUI using the existing shared services and message catalogs.

## Translation credits

The translations are collaborative works created by external contributors and communities;
the credits belong to those contributors. See [TRANSLATION_CREDITS.md](TRANSLATION_CREDITS.md) for attribution notes.

## Support and contributions

Report reproducible problems through [GitHub Issues](https://github.com/zschopper/pytrtt/issues).
Include the tool version, operating system, game/build, selected language and steps to reproduce.
For translation problems, send the generated diagnostic report to
[tombraidertranslations@gmail.com](mailto:tombraidertranslations@gmail.com).
Reports are stored in the user data directory; the CLI prints their location and does not send email automatically.

Want to translate a supported game into another language? Start with the [translation guide](docs/TRANSLATING.md).
Contributions to code, translations and testing are welcome. Include relevant checks with code changes;
new game support needs a profile and evidence from extraction, translation and restoration tests.

## License

The PyTRTT program code is licensed under the [MIT License](LICENSE).
This license does not automatically cover translation text, fonts, game data or external reference code;
those materials retain their respective rights and credits.
