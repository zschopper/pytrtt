# Text Encoding and Storage

- Determine encoding, byte order, terminators, length prefixes, pointer tables, and compression before editing.
  Character count differs from encoded byte length; original text length does not establish a storage limit.
- Preserve control codes, placeholders, escapes, language metadata, empty source text, and required whitespace.
- For growing text, update sizes, offsets, references, and alignment, or report that safe relocation is unsupported.
  Never silently replace unsupported characters or normalize binary data.
- Keep translation JSON in correct Unicode; font substitutions are game-specific runtime data,
  not a reason to store altered spelling in the editable document. Preserve substitution-disabled records.
- Clearing a subtitle slot to a space and omitting its records are different explicit operations;
  verify both in the target game/build rather than inheriting another project's policy.
- Test accented/multibyte text, empty and missing translations, shared pointers, and boundary lengths where supported.
