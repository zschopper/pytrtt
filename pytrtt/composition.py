"""Explicit application wiring shared by console, developer tools and GUI clients."""

from pytrtt.archives.bigfile import BigFileV1Handler
from pytrtt.archives.bigfile_v2 import BigFileV2Handler
from pytrtt.archives.tiger_v3 import TigerV3Handler
from pytrtt.archives.tiger_v4 import TigerV4Handler
from pytrtt.formats.handlers import CineV1Handler, CineV3Handler, LocalsV1Handler, RawHandler
from pytrtt.formats.locals_v3 import LocalsV3Handler
from pytrtt.formats.reboot_text import (
    CineV2Handler,
    LocalsV2Handler,
    SchV1Handler,
    SchV2Handler,
    SchV3Handler,
)
from pytrtt.registry import HandlerRegistry
from pytrtt.services.translation import TranslationService


def create_handler_registry() -> HandlerRegistry:
    """Each client owns its format registrations; there is no global mutable registry."""
    registry = HandlerRegistry()
    registry.archives[("bigfile", 1)] = BigFileV1Handler
    registry.archives[("bigfile", 2)] = BigFileV2Handler
    registry.archives[("tiger", 3)] = TigerV3Handler
    registry.archives[("tiger", 4)] = TigerV4Handler
    registry.formats[("locals", 1)] = LocalsV1Handler()
    registry.formats[("cine", 1)] = CineV1Handler()
    registry.formats[("locals", 2)] = LocalsV2Handler()
    registry.formats[("locals", 3)] = LocalsV3Handler()
    registry.formats[("cine", 2)] = CineV2Handler()
    registry.formats[("cine", 3)] = CineV3Handler()
    registry.formats[("sch", 1)] = SchV1Handler()
    registry.formats[("sch", 2)] = SchV2Handler()
    registry.formats[("sch", 3)] = SchV3Handler()
    registry.formats[("raw", 1)] = RawHandler()
    return registry


def create_translation_service() -> TranslationService:
    return TranslationService(create_handler_registry())
