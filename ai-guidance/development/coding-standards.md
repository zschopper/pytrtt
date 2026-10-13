# Coding Standards

- Follow the supported Python version and existing conventions. Keep code, identifiers, comments, and docstrings English.
- User-facing program messages belong in the shared localization catalogs, with an English base catalog;
  interface language and translation target language are independent.
- Type public boundaries, parameters, and returns precisely; use appropriate `Protocol`, `Callable`, and built-in generics.
  Avoid unmotivated `Any`, suppression, and annotations inconsistent with runtime behavior.
- Prefer the standard library and existing dependencies. For dependency/tool changes, read `environment.md`.
- Preserve CLI behavior, configuration, errors, and public APIs unless the task requires a change.
  Keep edits focused; do not rewrite unaffected code or reformat unrelated modules.
