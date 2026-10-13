# References and Provenance

- Use the project plan's reference section for exact source paths, commits, game inventory, and baseline decisions.
  The accepted historical TRA/TRL baseline is `references/saját/080423-01.trtr2/`;
  do not generalize the later C# master to every older game.
- Local code references include `references/Tomb-Raider-Translator/`, `references/TrRebootModTools/`,
  and `references/translatr/`. Inspect relevant historical revisions and record the exact commit for findings.
- References are read-only analysis material, not imports, dependencies, test targets, or release content.
  Do not automatically run reference applications, initialize submodules, or alter unrelated historical code.
- Before copying code, verify its license and record its origin. Treat code, translations, fonts, and game-data rights
  separately; a code license does not license all referenced assets.
- Keep source/asset provenance beside maintained translations; record hashes and the scope of verified comparisons.
  Logical agreement does not prove the exact build source of a released executable.
- Local inventories, exploratory filelists, name candidates, and reports stay under `work/` or `references/`.
  A candidate filename needs a matching hash in the target game's index before promotion to a runtime filelist.
- Installed paths, download completion, format similarity, and available translations are not proof of game support.
  Verify stable build inputs before sampling and keep copyrighted samples out of version control.
