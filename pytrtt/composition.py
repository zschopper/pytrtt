"""Explicit application wiring shared by console, developer tools and future GUI clients."""

from pytrtt.archives.bigfile import BigFileV1Handler
from pytrtt.formats.handlers import CineV1Handler, LocalsV1Handler, RawHandler
from pytrtt.registry import HandlerRegistry
from pytrtt.services.translation import TranslationService


def create_handler_registry() -> HandlerRegistry:
    """Each client owns its format registrations; there is no global mutable registry."""
    registry = HandlerRegistry()
    registry.archives[("bigfile", 1)] = BigFileV1Handler
    registry.formats[("locals", 1)] = LocalsV1Handler()
    registry.formats[("cine", 1)] = CineV1Handler()
    registry.formats[("raw", 1)] = RawHandler()
    return registry


def create_translation_service() -> TranslationService:
    return TranslationService(create_handler_registry())
