"""Intégration L'Hotellier Eau (Agence en ligne)."""
from __future__ import annotations

from pathlib import Path

import aiohttp

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, EVENT_COMPONENT_LOADED, Platform
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .api import LhotellierApi
from .const import CARD_FILE, CARD_URL, DOMAIN, VERSION
from .coordinator import LhotellierConfigEntry, LhotellierCoordinator

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Carte servie par Home Assistant et chargée dans l'interface : aucune ressource à ajouter."""
    if hass.http is None:
        return True
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / CARD_FILE), cache_headers=False)]
    )
    if "frontend" in hass.config.components:
        _add_card(hass)
    else:

        @callback
        def _frontend_loaded(event: Event) -> None:
            if event.data.get("component") == "frontend":
                _add_card(hass)
                unsub()

        unsub = hass.bus.async_listen(EVENT_COMPONENT_LOADED, _frontend_loaded)
    return True


@callback
def _add_card(hass: HomeAssistant) -> None:
    from homeassistant.components.frontend import add_extra_js_url

    add_extra_js_url(hass, f"{CARD_URL}?v={VERSION}")


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
