"""Configuration via l'interface pour L'Hotellier Eau."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.util import dt as dt_util

from .api import LhotellierApi, LhotellierApiError, LhotellierAuthError, LhotellierData
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): TextSelector(TextSelectorConfig(type=TextSelectorType.EMAIL)),
        vol.Required(CONF_PASSWORD): _PASSWORD,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): _PASSWORD})


async def _validate(data: Mapping[str, Any]) -> LhotellierData:
    async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar()) as session:
        api = LhotellierApi(
            session, data[CONF_USERNAME], data[CONF_PASSWORD], dt_util.get_default_time_zone()
        )
        return await api.fetch_all()


def _error_key(err: Exception) -> str:
    if isinstance(err, LhotellierAuthError):
        return "invalid_auth"
    if isinstance(err, LhotellierApiError):
        return "cannot_connect"
    _LOGGER.exception("Erreur inattendue")
    return "unknown"


class LhotellierConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                data = await _validate(user_input)
            except Exception as err:  # noqa: BLE001
                errors["base"] = _error_key(err)
            else:
                ref = data.subscription.get("reference") or user_input[CONF_USERNAME].lower()
                await self.async_set_unique_id(ref)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=f"Eau – abonnement {ref}", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            new_data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            try:
                await _validate(new_data)
            except Exception as err:  # noqa: BLE001
                errors["base"] = _error_key(err)
            else:
                return self.async_update_reload_and_abort(entry, data=new_data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )
