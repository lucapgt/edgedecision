"""Exercise the real intent response code with Home Assistant's timer response contract."""
import ast
import importlib.util
import logging
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "edgedecision"
NOW = datetime(2026, 10, 6, 21, 0, tzinfo=timezone.utc)
ha_util = types.ModuleType("homeassistant.util")
ha_util.dt = types.SimpleNamespace(now=lambda: NOW)
sys.modules["homeassistant"] = types.ModuleType("homeassistant")
sys.modules["homeassistant.util"] = ha_util
sys.modules["edge_test"] = types.ModuleType("edge_test")
spec = importlib.util.spec_from_file_location("edge_test.assist_text", ROOT / "assist_text.py")
texts = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = texts
spec.loader.exec_module(texts)

class IntentError(Exception):
    pass

intent = types.SimpleNamespace(IntentError=IntentError, async_handle=AsyncMock())
tree = ast.parse((ROOT / "conversation.py").read_text())
agent = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "EdgeDecisionAgent")
method = next(n for n in agent.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "_run_intent")
namespace = {"__name__": "edge_test.conversation", "__package__": "edge_test",
             "timedelta": timedelta, "intent": intent, "DOMAIN": "edgedecision",
             "_LOGGER": logging.getLogger("test")}
exec(compile(ast.Module(body=[method], type_ignores=[]), "conversation.py", "exec"), namespace)
run_intent = namespace["_run_intent"]

class AlarmStatusTests(unittest.IsolatedAsyncioTestCase):
    async def call_status(self, timers, lang="it"):
        intent.async_handle.reset_mock(side_effect=True)
        intent.async_handle.return_value = types.SimpleNamespace(speech_slots={"timers": timers})
        user = types.SimpleNamespace(language=lang, text="C'è una sveglia impostata",
                                     context=object(), device_id="voice-pe", satellite_id="assist_satellite.voice")
        result = await run_intent(types.SimpleNamespace(hass=object()),
                                  {"intent": "HassTimerStatus", "slots": {}}, user, "fallback")
        self.assertEqual(intent.async_handle.call_args.kwargs["device_id"], "voice-pe")
        self.assertEqual(intent.async_handle.call_args.kwargs["satellite_id"], "assist_satellite.voice")
        return result

    async def test_alarm_status_in_all_nine_languages(self):
        expected = {"it": "La sveglia è alle 22:00.", "en": "The alarm is set for 22:00.",
                    "es": "La alarma está puesta a las 22:00.", "fr": "Le réveil est réglé à 22:00.",
                    "de": "Der Wecker ist auf 22:00 Uhr gestellt.", "nl": "De wekker staat op 22:00.",
                    "pt": "O alarme está marcado para as 22:00.", "pl": "Budzik jest ustawiony na 22:00.",
                    "sv": "Väckarklockan är ställd på 22:00."}
        for lang, reply in expected.items():
            with self.subTest(lang=lang):
                alarm = {"name": texts.REPLY[lang]["alarm_name"], "total_seconds_left": 3600, "is_active": True}
                self.assertEqual(await self.call_status([alarm], lang), reply)

    async def test_no_timer(self):
        self.assertEqual(await self.call_status([]), "Non c'è nessun timer attivo.")

    async def test_regular_timer(self):
        timer = {"name": "Pasta", "total_seconds_left": 90, "is_active": True}
        self.assertEqual(await self.call_status([timer]), "Mancano 1 minuto e 30 secondi.")

    async def test_paused_timer(self):
        timer = {"name": "Pasta", "total_seconds_left": 90, "is_active": False}
        self.assertEqual(await self.call_status([timer]), "Il timer è in pausa, mancano 1 minuto e 30 secondi.")

if __name__ == "__main__":
    unittest.main()
