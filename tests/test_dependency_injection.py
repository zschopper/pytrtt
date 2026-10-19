"""Core workflows accept structural collaborators without archive files or inheritance."""

from dataclasses import dataclass, field, replace
from pathlib import Path

from pytrtt.archives.contracts import (
    ArchiveHandler,
    ArchiveResource,
    ArchiveWritePlan,
    PlannedFile,
    PlannedWrite,
    ResourceReplacement,
)
from pytrtt.config import ArchiveSettings, RuntimeSettings
from pytrtt.formats.contracts import TextFormatHandler, TextOptions
from pytrtt.packages.translation import TranslationEntry
from pytrtt.services.translation import TranslationService
from tests.test_generic_translation import document


@dataclass
class MemoryPlan:
    writes: tuple[PlannedWrite, ...] = ()
    files: dict[str, PlannedFile] = field(default_factory=dict)
    index_data: dict[str, bytes] = field(default_factory=dict)
    backup_bytes: int = 0
    sufficient_space: bool = True

    def validate_inputs(self, _directory: Path) -> None:
        return None


@dataclass
class MemoryArchive:
    replacements: tuple[ResourceReplacement, ...] = ()
    applied: tuple[ArchiveWritePlan, Path, RuntimeSettings] | None = None
    restored: Path | None = None

    def resources(self) -> tuple[ArchiveResource, ...]:
        return (ArchiveResource(0x12345678, 0xFFFFFFE1, 1),)

    def read(self, resource: ArchiveResource) -> bytes:
        return b"A"

    def plan(self, replacements: tuple[ResourceReplacement, ...]) -> ArchiveWritePlan:
        self.replacements = replacements
        return MemoryPlan()

    def apply(
        self, plan: ArchiveWritePlan, transaction_dir: Path, runtime: RuntimeSettings
    ) -> Path:
        self.applied = (plan, transaction_dir, runtime)
        return transaction_dir / "journal.json"

    def restore(self, transaction_dir: Path) -> None:
        self.restored = transaction_dir


class MemoryTextFormat:
    def extract(self, data: bytes, subtitle_language: int) -> tuple[TranslationEntry, ...]:
        return (TranslationEntry(0, data.decode(), None),)

    def write(
        self, data: bytes, entries: tuple[TranslationEntry, ...], options: TextOptions
    ) -> bytes:
        translated = [options.text(e) for e in entries if e.translation is not None]
        return translated[0].encode() if translated else data


class MemoryRegistry:
    def __init__(self) -> None:
        # These assignments also verify structural compatibility under strict mypy.
        self.handler: ArchiveHandler = MemoryArchive()
        self.format: TextFormatHandler = MemoryTextFormat()

    def __bool__(self) -> bool:
        # An explicitly injected dependency must not be replaced based on truthiness.
        return False

    def archive(self, directory: Path, settings: ArchiveSettings) -> ArchiveHandler:
        return self.handler

    def text_format(self, format_name: str, version: int) -> TextFormatHandler:
        return self.format


def test_injected_handlers_extract_without_a_game_or_binary_parser(tmp_path: Path) -> None:
    registry = MemoryRegistry()
    service = TranslationService(registry)
    doc = document()
    assert doc.runtime is not None
    result = service.extract(
        tmp_path / "absent-game", doc.metadata, doc.runtime, {0x12345678: "data/locals.bin"}
    )
    assert result.document.menu[0].entries == (TranslationEntry(0, "A", None),)
    assert result.document.subtitles == ()
    assert not (tmp_path / "absent-game").exists()


def test_injected_handlers_plan_apply_and_restore_without_files(tmp_path: Path) -> None:
    registry = MemoryRegistry()
    service = TranslationService(registry)
    doc = replace(document(), subtitles=())
    result = service.plan(tmp_path / "absent-game", doc, package_dir=tmp_path)
    assert isinstance(registry.handler, MemoryArchive)
    assert registry.handler.replacements == (
        ResourceReplacement("Menu 12345678", 0x12345678, 0xFFFFFFE1, "Ação ő".encode()),
    )
    assert result.missing_translations == ()
    assert result.plan is not None
    transaction = tmp_path / "transaction"
    assert service.apply(result, transaction) == transaction / "journal.json"
    assert registry.handler.applied == (result.plan, transaction, doc.runtime)
    service.restore(tmp_path / "absent-game", transaction, doc.runtime)
    assert registry.handler.restored == transaction
    assert list(tmp_path.iterdir()) == []


def test_missing_translation_uses_injected_handler_and_preserves_source(tmp_path: Path) -> None:
    registry = MemoryRegistry()
    service = TranslationService(registry)
    doc = document()
    resource = replace(doc.menu[0], entries=(TranslationEntry(0, "A", None),))
    result = service.plan(
        tmp_path / "absent-game", replace(doc, menu=(resource,), subtitles=()), package_dir=tmp_path
    )
    assert result.plan is None
    assert [(m.section, m.entry_id, m.source) for m in result.missing_translations] == [
        ("menu", 0, "A")
    ]
    assert service.apply(result, tmp_path / "transaction") is None
    assert isinstance(registry.handler, MemoryArchive)
    assert registry.handler.applied is None


def test_composition_creates_independent_registries_and_preserves_legacy_factory() -> None:
    from pytrtt.composition import create_handler_registry, create_translation_service
    from pytrtt.registry import default_registry

    first = create_handler_registry()
    second = default_registry()
    first.formats.clear()
    assert second.text_format("locals", 1).extract(
        bytes.fromhex("000000000200000000000000100000004100"), 0
    ) == (TranslationEntry(0, "A", None),)
    assert create_translation_service().registry is not first


def test_handler_contracts_support_runtime_checks_and_structural_implementations() -> None:
    assert isinstance(MemoryArchive(), ArchiveHandler)
    assert isinstance(MemoryTextFormat(), TextFormatHandler)
