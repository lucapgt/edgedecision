"""Set-up: add-on address (tested automatically), fallback agent, model."""
from __future__ import annotations

import asyncio

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (CONF_EXECUTE, CONF_FALLBACK, CONF_MODEL, CONF_URL, DEFAULT_FALLBACK, DEFAULT_URL, DOMAIN,
                    URL_CANDIDATES)


async def probe(hass, url: str, timeout: float = 5) -> dict | None:
    try:
        async with async_get_clientsession(hass).get(url.rstrip("/") + "/health",
                                                     timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            if r.status == 200:
                return await r.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return None
    return None


def candidates(hass) -> list[str]:
    """Addresses where the add-on may answer: first the ones the Supervisor knows, then the usual ones."""
    urls: list[str] = []
    try:
        from homeassistant.components.hassio import get_addons_info
        for slug in (get_addons_info(hass) or {}):
            if slug == "edgedecision" or slug.endswith("_edgedecision"):
                urls.append(f"http://{slug.replace('_', '-')}:8765")
    except Exception:  # noqa: BLE001 - not a Supervisor installation, or API changed: use the static list
        pass
    return list(dict.fromkeys(urls + URL_CANDIDATES))


async def find_url(hass, timeout: float = 5) -> str | None:
    for url in candidates(hass):
        if await probe(hass, url, timeout) is not None:
            return url
    return None


def schema(d: dict) -> vol.Schema:
    return vol.Schema({
        vol.Required(CONF_URL, default=d.get(CONF_URL, DEFAULT_URL)): str,
        vol.Required(CONF_FALLBACK, default=d.get(CONF_FALLBACK, DEFAULT_FALLBACK)):
            selector.ConversationAgentSelector(),
        vol.Required(CONF_MODEL, default=d.get(CONF_MODEL, "default")): selector.SelectSelector(
            selector.SelectSelectorConfig(options=["default", "7c"], mode=selector.SelectSelectorMode.DROPDOWN)),
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
            url = await find_url(self.hass)  # pre-fill with the first address that answers
            defaults = {CONF_URL: url} if url else {}
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
