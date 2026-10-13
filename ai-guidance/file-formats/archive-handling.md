# Archive Handling

- Establish exact archive/text variants, build, ordering, identifiers, metadata, and alignment before parsing or rebuilding.
  BIGFILE and TIGER are not interchangeable; shared archive versions do not prove identical resources or patch support.
- Preserve unknown fields and unchanged content. Fail clearly on unsupported or malformed data.
- Treat reading, rebuilding, and placement as distinct operations; test round trips with representative fixtures.
- Use explicit outputs and stable game copies. Installed game paths are not automatic write/test targets;
  do not run or modify historical reference applications automatically.
- Preserve original font recovery assets and the first transaction backup. Verify patch loading and DLC handling
  separately for each game/build; follow `binary-safety.md` for installation and restoration.
- Never version copyrighted game samples; keep local samples and reports under `work/`.
