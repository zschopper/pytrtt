# Architecture

- Inspect existing boundaries and preserve stable interfaces. Keep archives, text formats, translation services,
  and CLI/GUI presentation separate. Services do not print or depend on UI or developer game profiles.
- Select handlers by format/version, never by game identity. Game names belong in data and targeted tests.
- Put game-specific technical data in declarative `profiles/` JSON; embed all required runtime data in the
  translation document's `metadata.runtime`. Profiles and translation packages cannot execute or import code.
- Use `archives/contracts.py` and `formats/contracts.py` for handlers; register concrete handlers explicitly
  at the composition root. Avoid dynamic imports, plugin frameworks, service locators, and mutable globals.
- Prefer small components and explicit constructor dependencies; use method injection for operation-specific inputs.
  Use `typing.Protocol` for interchangeable contracts and `abc.ABC` for needed shared behavior or runtime enforcement.
  Do not create an interface for every class or add a DI framework without a concrete need.
- Text handlers consume bytes/streams and return complete rebuilt resources without global game state.
  Archive handlers own placement, capacity, relocation, and index updates.
- Source text alone is not unique, and physical offsets are not stable record identifiers.
- Reuse the existing translation service and composition root for new clients and scripts; avoid unrelated refactors.
