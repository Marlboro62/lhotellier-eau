"""Coordinateur de mise à jour L'Hotellier Eau."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LhotellierApi, LhotellierApiError, LhotellierAuthError, LhotellierData
from .const import DOMAIN, UPDATE_INTERVAL
from .statistics import async_import_history

_LOGGER = logging.getLogger(__name__)

type LhotellierConfigEntry = ConfigEntry[LhotellierCoordinator]


class LhotellierCoordinator(DataUpdateCoordinator[LhotellierData]):
    config_entry: LhotellierConfigEntry

    def __init__(self, hass: HomeAssistant, entry: LhotellierConfigEntry, api: LhotellierApi) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.api = api

    async def _async_update_data(self) -> LhotellierData:
        try:
            data = await self.api.fetch_all()
        except LhotellierAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except LhotellierApiError as err:
            raise UpdateFailed(str(err)) from err
        # Anciens relevés et factures dans les statistiques longue durée (tableau Énergie)
        async_import_history(self.hass, str(self.config_entry.unique_id), data)
        return data
