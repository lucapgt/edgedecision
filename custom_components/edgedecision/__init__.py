"""EdgeDecision conversation agent for Assist.

Every sentence goes to the EdgeDecision add-on (small local model, ~0.2 s on a Raspberry Pi 5):
  EXECUTE  -> the add-on runs the action, Assist says "Fatto."
  CLARIFY  -> Assist asks the question and keeps listening (continue_conversation)
  REJECT   -> short answer ("Va bene.", "Non posso farlo...")
  ESCALATE -> the sentence is handed to a fallback agent (Home Assistant's own, or an LLM agent)
"""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

PLATFORMS = ["conversation"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _reload(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
