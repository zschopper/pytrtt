from pathlib import Path

from scripts.review_name_candidates import review_candidates


def test_adds_hex_offset_and_marks_recomputed_hash_as_known(tmp_path: Path) -> None:
    candidate_file = tmp_path / "name-candidates.txt"
    candidate_file.write_text(
        "[LC2.exe]\nCANDIDATE\t00000000\tpc-w\\local\\locals.bin\tindex-match: False\n",
        encoding="utf-8",
    )
    review_file = tmp_path / "candidate-review.tsv"
    review_file.write_text(
        "exe\toffset\tencoding\thash_bits\thash\tkind\tname\tindex_match\n"
        "LC2\t16\tascii/utf-8\t32\t00000000\trelative_path\tpc-w\\local\\locals.bin\tFalse\n",
        encoding="utf-8",
    )
    hashes = {"lctoo": {0x7CD333D3}}

    stats = review_candidates(candidate_file, review_file, hashes, {"LC2": (32, ["lctoo"])})

    assert candidate_file.read_text(encoding="utf-8") == (
        "[LC2.exe]\nKNOWN\t00000010\t7CD333D3\tpc-w\\local\\locals.bin\tindex-match: True\n"
    )
    assert stats.newly_known == 1


def test_keeps_candidate_when_recomputed_hash_is_absent_and_updates_hash(tmp_path: Path) -> None:
    candidate_file = tmp_path / "name-candidates.txt"
    candidate_file.write_text(
        "[LC2]\nCANDIDATE\tDEADBEEF\told.txt\tindex-match: False\n", encoding="utf-8"
    )
    review_file = tmp_path / "candidate-review.tsv"
    review_file.write_text(
        "exe\toffset\tencoding\thash_bits\thash\tkind\tname\tindex_match\n"
        "LC2\t26\tascii/utf-8\t32\t12345678\tbasename\told.txt\tFalse\n",
        encoding="utf-8",
    )

    stats = review_candidates(
        candidate_file, review_file, {"lctoo": set()}, {"LC2": (32, ["lctoo"])}
    )

    assert candidate_file.read_text(encoding="utf-8") == (
        "[LC2]\nCANDIDATE\t0000001A\t1D019E1B\told.txt\tindex-match: False\n"
    )
    assert stats.newly_known == 0
    assert stats.still_candidates == 1


def test_preserves_existing_known_rows(tmp_path: Path) -> None:
    candidate_file = tmp_path / "name-candidates.txt"
    original = "[LC2]\nKNOWN\t00000010\t7CD333D3\tpc-w\\local\\locals.bin\tindex-match: True\n"
    candidate_file.write_text(original, encoding="utf-8")
    review_file = tmp_path / "candidate-review.tsv"
    review_file.write_text("exe\toffset\tencoding\thash_bits\thash\tkind\tname\tindex_match\n")

    stats = review_candidates(
        candidate_file,
        review_file,
        {"lctoo": {0x7CD333D3}},
        {"LC2": (32, ["lctoo"])},
    )

    assert candidate_file.read_text(encoding="utf-8") == original
    assert stats.newly_known == 0
    assert stats.already_known == 1


def test_rechecks_edited_known_row_and_demotes_it_when_hash_is_absent(tmp_path: Path) -> None:
    candidate_file = tmp_path / "name-candidates.txt"
    candidate_file.write_text(
        "[LC2.exe]\nKNOWN\t00000010\t7CD333D3\told.txt\tindex-match: True\n",
        encoding="utf-8",
    )
    review_file = tmp_path / "candidate-review.tsv"
    review_file.write_text("exe\toffset\tencoding\thash_bits\thash\tkind\tname\tindex_match\n")

    stats = review_candidates(
        candidate_file, review_file, {"lctoo": set()}, {"LC2": (32, ["lctoo"])}
    )

    assert candidate_file.read_text(encoding="utf-8") == (
        "[LC2.exe]\nCANDIDATE\t00000010\t1D019E1B\told.txt\tindex-match: False\n"
    )
    assert stats.invalidated_known == 1
