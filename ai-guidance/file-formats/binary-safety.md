# Binary Safety

- Validate counts, byte order, offsets, alignment, sizes, integer limits, references, checksums, padding, and part boundaries.
  Guard out-of-bounds reads, overflow, invalid ranges, and partial writes; preserve unknown bytes.
- Rebuild text blocks and dependent sizes/offsets when content grows; never truncate or null unknown data to fit.
- Dry run and apply must share the write plan; revalidate files before execution. Prefer atomic replacement;
  preserve transaction recovery data and allow only one modifying operation per game directory.
- Stop on unexpected file changes instead of weakening source/hash checks. Preserve recovery journals;
  restoring before a different package and detecting an already-installed package follow the project plan's state rules.
- Verify unchanged regions and rebuilt structure; exercise interrupted writes and restoration where behavior changes.
  Prove restored physical files match original sizes and SHA-256, including repeated restoration.
- Do not weaken integrity checks to pass a fixture or claim a planned state-management feature already exists.
