"""Intégration L'Hotellier Eau (Agence en ligne)."""
from __future__ import annotations

import aiohttp

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.util import dt as dt_util

from .api import LhotellierApi
from .coordinator import LhotellierConfigEntry, LhotellierCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LhotellierConfigEntry) -> bool:
    # Session dédiée avec ses propres cookies (le portail utilise JSESSIONID)
    session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
    # Fermer la session au déchargement (rechargement, suppression)
    entry.async_on_unload(session.close)
    api = LhotellierApi(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        dt_util.get_default_time_zone(),
    )
    coordinator = LhotellierCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LhotellierConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
