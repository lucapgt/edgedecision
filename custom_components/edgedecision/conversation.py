"""The Assist agent: forwards each sentence to the EdgeDecision add-on."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta
from typing import Literal

import aiohttp
from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ulid import ulid_now

from .const import CONF_EXECUTE, CONF_FALLBACK, CONF_MODEL, CONF_URL, DEFAULT_FALLBACK, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)
TIMEOUT = aiohttp.ClientTimeout(total=10)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    agent = EdgeDecisionAgent(hass, entry)
    async_add_entities([agent])
    # new devices / names may have been added while HA was down: ask the add-on to rebuild its catalogue
    hass.async_create_task(agent.reload_catalog())


class EdgeDecisionAgent(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        cfg = {**entry.data, **entry.options}
        self.url = cfg.get(CONF_URL, DEFAULT_URL).rstrip("/")
        self.fallback = cfg.get(CONF_FALLBACK) or DEFAULT_FALLBACK
        self.model = cfg.get(CONF_MODEL, "default")
        self.execute = cfg.get(CONF_EXECUTE, True)
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": "EdgeDecision",
                                  "manufacturer": "EdgeDecision", "model": "Local decision engine"}
        self._last: dict = {}

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return ["it", "en", "es", "fr", "de", "nl", "pt", "pl", "sv"]

    @property
    def extra_state_attributes(self):
        return self._last

    # ----------------------------------------------------------- helpers
    def _area(self, user_input: conversation.ConversationInput) -> str | None:
        """Room of the microphone: satellite entity -> its area or its device's area; else the device's area."""
        devices = dr.async_get(self.hass)
        if user_input.satellite_id:
            ent = er.async_get(self.hass).async_get(user_input.satellite_id)
            if ent is not None:
                if ent.area_id:
                    return ent.area_id
                if ent.device_id and (dev := devices.async_get(ent.device_id)) and dev.area_id:
                    return dev.area_id
        if user_input.device_id and (dev := devices.async_get(user_input.device_id)):
            return dev.area_id
        return None

    def _device(self, user_input: conversation.ConversationInput) -> str | None:
        """HA device of the satellite that heard the sentence (its music player is used first)."""
        if user_input.satellite_id:
            ent = er.async_get(self.hass).async_get(user_input.satellite_id)
            if ent is not None and ent.device_id:
                return ent.device_id
        return user_input.device_id

    async def reload_catalog(self) -> None:
        try:
            async with async_get_clientsession(self.hass).post(self.url + "/reload", json={},
                                                               timeout=aiohttp.ClientTimeout(total=120)) as r:
                _LOGGER.debug("EdgeDecision catalogue reload: %s", r.status)
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            _LOGGER.warning("EdgeDecision add-on not reachable at %s: %s", self.url, e)

    async def _fallback(self, user_input, conversation_id, why: str) -> conversation.ConversationResult:
        _LOGGER.debug("EdgeDecision -> fallback agent %s (%s)", self.fallback, why)
        return await conversation.async_converse(
            self.hass, user_input.text, conversation_id, user_input.context, language=user_input.language,
            agent_id=self.fallback, device_id=user_input.device_id, satellite_id=user_input.satellite_id,
            extra_system_prompt=user_input.extra_system_prompt)

    async def _run_intent(self, spec: dict, user_input, default_reply: str) -> str:
        from homeassistant.util import dt as dt_util

        from .assist_text import REPLY, say_duration

        lang = (user_input.language or "it")[:2]
        R = REPLY.get(lang, REPLY["en"])
        slots = dict(spec.get("slots") or {})
        if spec.get("alarm_time"):  # "svegliami alle 7": a timer until the next 7:00 of this Home Assistant's clock
            hh, mm = (int(x) for x in str(spec["alarm_time"]).split(":"))
            now = dt_util.now()
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if target <= now:
                target = target + timedelta(days=1)
            secs = int((target - now).total_seconds())
            h, rest = divmod(secs, 3600)
            m, sec = divmod(rest, 60)
            slots.update({k: v for k, v in (("hours", h), ("minutes", m), ("seconds", sec)) if v})
        try:
            resp = await intent.async_handle(
                self.hass, DOMAIN, spec["intent"], {k: {"value": v} for k, v in slots.items()},
                text_input=user_input.text, context=user_input.context, language=user_input.language,
                device_id=user_input.device_id, satellite_id=user_input.satellite_id)
        except intent.IntentError as e:  # no timer running, device without timers, ...
            _LOGGER.debug("EdgeDecision intent %s failed: %s", spec.get("intent"), e)
            if "support" in type(e).__name__.lower() or "support" in str(e).lower():
                return R["no_device"]
            return R["no_timer"]
        if spec["intent"] == "HassTimerStatus":
            timers = (resp.speech_slots or {}).get("timers") or []
            if not timers:
                return R["no_timer"]
            alarm = str(R.get("alarm_name", "")).lower()
            for a in timers:  # "a che ora è la sveglia?": the alarm is the timer named "Sveglia" -> its clock time
                if alarm and str(a.get("name") or "").lower() == alarm:
                    at = dt_util.now() + timedelta(seconds=int(a.get("total_seconds_left") or 0))
                    return R["alarm_at"].format(t=f"{at.hour}:{at.minute:02d}")
            t = timers[0]
            left = say_duration(t.get("total_seconds_left") or 0, lang)
            return (R["status"] if t.get("is_active", True) else R["status_paused"]).format(d=left)
        return default_reply

    # -------------------------------------------------------------- main
    async def async_process(self, user_input: conversation.ConversationInput) -> conversation.ConversationResult:
        conversation_id = user_input.conversation_id or ulid_now()
        area = self._area(user_input)
        session = user_input.satellite_id or user_input.device_id or conversation_id
        payload = {"text": user_input.text, "context_area": area, "session": session, "execute": self.execute,
                   "lang": (user_input.language or "it")[:2], "device_id": self._device(user_input)}
        if self.model != "default":
            payload["model"] = self.model
        t0 = time.perf_counter()
        try:
            async with async_get_clientsession(self.hass).post(self.url + "/decide", json=payload,
                                                               timeout=TIMEOUT) as r:
                r.raise_for_status()
                out = await r.json()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
            _LOGGER.warning("EdgeDecision add-on error (%s): using %s", e, self.fallback)
            return await self._fallback(user_input, conversation_id, "add-on unreachable")

        d = out.get("decision", {})
        ex = out.get("execution") or {}
        self._last = {"text": user_input.text, "area": area, "policy": d.get("policy"), "reason": d.get("reason"),
                      "capability": d.get("capability"),
                      "parts": [f"{x.get('text')} -> {x.get('capability')}" for x in d.get("parts") or []],
                      "confidence": d.get("confidence"),
                      "latency_ms": d.get("latency_ms"), "total_ms": round((time.perf_counter() - t0) * 1000),
                      "reply": out.get("reply")}
        self.async_write_ha_state()
        self.hass.bus.async_fire(f"{DOMAIN}_decision", {**self._last, "execution": ex, "session": session})

        if d.get("policy") == "ESCALATE" and self.fallback and self.fallback != self.entity_id:
            return await self._fallback(user_input, conversation_id, d.get("reason", ""))

        response = intent.IntentResponse(language=user_input.language)
        if out.get("intent") and d.get("policy") == "EXECUTE" and self.execute:
            # timers, alarms, announcements: Home Assistant's own intents, on the satellite that heard the sentence
            response.async_set_speech(await self._run_intent(out["intent"], user_input, out.get("reply") or ""))
            return conversation.ConversationResult(response=response, conversation_id=conversation_id)
        if ex.get("error"):
            # the add-on puts a spoken explanation in "reply" ("Non ho trovato Radio DJ."), not the raw HTTP error
            response.async_set_error(intent.IntentResponseErrorCode.FAILED_TO_HANDLE, out.get("reply") or ex["error"])
        else:
            response.async_set_speech(out.get("reply") or "")
            if d.get("policy") == "REJECT" and d.get("reason") in ("unsupported", "unavailable", "invalid_param"):
                response.async_set_error(intent.IntentResponseErrorCode.NO_VALID_TARGETS, out.get("reply") or "")
        return conversation.ConversationResult(response=response, conversation_id=conversation_id,
                                               continue_conversation=d.get("policy") == "CLARIFY")
