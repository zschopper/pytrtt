# References and Provenance

- Use the available project plan and optional local guidance for source paths, commits, game inventory, and baseline decisions.
  Inspect relevant historical revisions and record the exact commit for findings;
  do not generalize a later master revision to every older game.
- References are read-only analysis material, not imports, dependencies, test targets, or release content.
  Do not automatically run reference applications, initialize submodules, or alter unrelated historical code.
- Before copying code, verify its license and record its origin. Treat code, translations, fonts, and game-data rights
  separately; a code license does not license all referenced assets.
- Keep source/asset provenance beside maintained translations; record hashes and the scope of verified comparisons.
  Logical agreement does not prove the exact build source of a released executable.
- Local inventories, exploratory filelists, name candidates, and reports stay in Git-ignored directories.
  A candidate filename needs a matching hash in the target game's index before promotion to a runtime filelist.
- Installed paths, download completion, format similarity, and available translations are not proof of game support.
  Verify stable build inputs before sampling and keep copyrighted samples out of version control.
