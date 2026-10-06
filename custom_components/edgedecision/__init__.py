"""EdgeDecision conversation agent for Assist.

Every sentence goes to the EdgeDecision add-on (small local model, ~0.2 s on a Raspberry Pi 5):
  EXECUTE  -> the add-on runs the action, Assist says "Fatto."
  CLARIFY  -> Assist asks the question and keeps listening (continue_conversation)
  REJECT   -> short answer ("Va bene.", "Non posso farlo...")
  ESCALATE -> the sentence is handed to a fallback agent (Home Assistant's own, or an LLM agent)
"""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["conversation"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _heal_url(hass, entry)
    entry.async_on_unload(entry.add_update_listener(_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _heal_url(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """If the saved address does not answer (add-on reinstalled from another source), use the one that does."""
    from .config_flow import find_url, probe
    from .const import CONF_URL
    cur = {**entry.data, **entry.options}.get(CONF_URL)
    if cur and await probe(hass, cur, 3) is not None:
        return
    url = await find_url(hass, 2)  # at boot the add-on may still be starting: keep it short
    if url and url != cur:
        _LOGGER.info("EdgeDecision add-on found at %s (was %s)", url, cur)
        if CONF_URL in entry.options:
            hass.config_entries.async_update_entry(entry, options={**entry.options, CONF_URL: url})
        else:
            hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_URL: url})


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
