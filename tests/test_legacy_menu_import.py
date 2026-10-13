"""Tests for importing the historical TRA menu translation text format."""

import pytest

from pytrtt.packages.legacy_menu import LegacyMenuImportError, import_legacy_menu
from pytrtt.packages.translation import TranslationEntry, TranslationPackage


def make_package(*sources: str) -> TranslationPackage:
    return TranslationPackage(
        game_id="tomb-raider-anniversary",
        build_id="842717",
        resource_hash="7CD333D3",
        source_language="en",
        target_language="hu",
        entries=tuple(TranslationEntry(i, source, None) for i, source in enumerate(sources)),
    )


def test_imports_translation_comments_directives_and_aliases() -> None:
    package = make_package("Hello", "Hello again", "Delete me")
    legacy = """\ufeff; old export
@0000
#Hello
;Alternative wording
$SETUP
Helló

@0001
#Hello again
*0000

@0002
#Delete me
$DEL
Delete me

"""

    imported, report = import_legacy_menu(legacy, package)

    assert [entry.translation for entry in imported.entries] == ["Helló", "*0000", "?"]
    assert imported.entries[0].comment == "Alternative wording\nLegacy directive: $SETUP"
    assert "Legacy alias: *0000" in (imported.entries[1].comment or "")
    assert "Legacy directive: $DEL" in (imported.entries[2].comment or "")
    assert report.exact_source_matches == 3
    assert report.aliases_preserved == 1
    assert report.deleted_entries_replaced == 1


def test_import_removes_legacy_test_marker_from_translation() -> None:
    package = make_package("Hello")

    imported, _ = import_legacy_menu("@0000\n#Hello\n!TESZT! Jó reggelt\n", package)

    assert imported.entries[0].translation == "Jó reggelt"


def test_import_records_historical_source_differences() -> None:
    package = make_package("Current source.")
    legacy = "@0000\n#Old source!\nTranslated text\n"

    imported, report = import_legacy_menu(legacy, package)

    assert imported.entries[0].source == "Current source."
    assert imported.entries[0].translation == "Translated text"
    assert "Historical source differed: Old source!" in (imported.entries[0].comment or "")
    assert report.content_source_differences == 1


def test_rejects_duplicate_missing_and_cyclic_entries() -> None:
    package = make_package("A", "B")

    with pytest.raises(LegacyMenuImportError, match="duplicate"):
        import_legacy_menu("@0000\n#A\na\n\n@0000\n#A\na\n", package)

    with pytest.raises(LegacyMenuImportError, match="missing"):
        import_legacy_menu("@0000\n#A\na\n", package)

    with pytest.raises(LegacyMenuImportError, match="cycle"):
        import_legacy_menu("@0000\n#A\n*0001\n\n@0001\n#B\n*0000\n", package)
