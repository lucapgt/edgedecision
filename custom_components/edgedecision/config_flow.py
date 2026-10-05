"""Set-up: add-on address (tested automatically), fallback agent, model."""
from __future__ import annotations

import asyncio

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (CONF_EXECUTE, CONF_FALLBACK, CONF_MODEL, CONF_URL, DEFAULT_FALLBACK, DOMAIN, URL_CANDIDATES)


async def probe(hass, url: str) -> dict | None:
    try:
        async with async_get_clientsession(hass).get(url.rstrip("/") + "/health",
                                                     timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status == 200:
                return await r.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return None
    return None


def schema(d: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_URL, default=d.get(CONF_URL, URL_CANDIDATES[0])): str,
        vol.Required(CONF_FALLBACK, default=d.get(CONF_FALLBACK, DEFAULT_FALLBACK)):
            selector.ConversationAgentSelector(),
        vol.Required(CONF_MODEL, default=d.get(CONF_MODEL, "default")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=["default", "6L", "4L"], mode=selector.SelectSelectorMode.DROPDOWN)),
        vol.Required(CONF_EXECUTE, default=d.get(CONF_EXECUTE, True)): bool,
    })


class EdgeDecisionFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            if await probe(self.hass, user_input[CONF_URL]) is not None:
                return self.async_create_entry(title="EdgeDecision", data=user_input)
            errors["base"] = "cannot_connect"
            defaults = user_input
        else:
            defaults = {}
            for url in URL_CANDIDATES:  # pre-fill with the first address that answers
                if await probe(self.hass, url) is not None:
                    defaults = {CONF_URL: url}
                    break
        return self.async_show_form(step_id="user", data_schema=schema(defaults), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(entry):
        return EdgeDecisionOptions()


class EdgeDecisionOptions(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            if await probe(self.hass, user_input[CONF_URL]) is not None:
                return self.async_create_entry(data=user_input)
            errors["base"] = "cannot_connect"
        cur = {**self.config_entry.data, **self.config_entry.options, **(user_input or {})}
        return self.async_show_form(step_id="init", data_schema=schema(cur), errors=errors)
