"""Home Assistant adapter.

HA  --(REST + WebSocket)-->  generic Catalog (areas, entities, features, states)
Decision  --(service call)-->  HA

The core never imports this module: other adapters (robots, BMS, industrial PLCs...) only need to
produce a Catalog and execute a Decision.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import requests

from ..core.registry import build_capabilities, default_actions
from ..core.types import Area, Catalog, Decision, Entity

# HA feature bitmasks
COVER_SET_POSITION, COVER_STOP = 4, 8
MP_PAUSE, MP_VOLUME_SET, MP_NEXT, MP_PLAY = 1, 4, 32, 16384
FAN_SET_SPEED = 1
VACUUM_RETURN_HOME = 16

SUPPORTED_DOMAINS = {"light", "switch", "input_boolean", "cover", "climate", "media_player", "fan", "lock", "sensor",
                     "binary_sensor", "vacuum", "scene", "alarm_control_panel", "weather",
                     # round 7
                     "valve", "water_heater", "humidifier", "lawn_mower", "button", "script", "automation", "person",
                     "todo"}
SENSOR_CLASSES = {"temperature", "humidity", "power", "energy", "battery", "carbon_dioxide", "pm25", "illuminance",
                  "gas", "water"}
BINARY_CLASSES = {"window", "door", "garage_door", "opening", "moisture", "smoke", "gas", "motion", "occupancy",
                  "carbon_monoxide"}
COVER_OPEN_TILT, COVER_CLOSE_TILT, COVER_SET_TILT = 16, 32, 128
MP_SELECT_SOURCE, MP_SHUFFLE_SET = 2048, 32768
CLIMATE_PRESET = 16
HUMIDIFIER_MODES = 1
TODO_CREATE = 1
GATE_WORDS = re.compile(r"cancell|gate|port[oó]n|portail|\btor\b|hek|port[aã]o|brama|grind|garage|box", re.I)

from ..core.virtual import NAMES as VIRTUAL_NAMES  # noqa: E402  (names of the virtual entities, 9 languages)

# entities that are not in Home Assistant's registry but stand for what Assist itself can do
VIRTUAL = [Entity(id="assist.voice", domain="assist", name="Assistente vocale"),
           Entity(id="home.house", domain="home", name="Casa")]


class HomeAssistant:
    def __init__(self, url: str, token: str, timeout: int = 10, verify_ssl: bool = True, ws_url: Optional[str] = None):
        """ws_url: override for the WebSocket endpoint (inside a HA add-on: ws://supervisor/core/websocket)."""
        self.url = url.rstrip("/")
        self.ws_override = ws_url
        self.token = token
        self.timeout = timeout
        self.verify = verify_ssl
        self.h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        self.virtual = True   # timers / alarms / announcements (via the integration) and "the whole house"
        self.allow_off_all = False  # "spegni tutto": off unless enabled (one misheard sentence must not darken the house)

    # ----------------------------------------------------------------- REST
    def get(self, path):
        r = requests.get(self.url + path, headers=self.h, timeout=self.timeout, verify=self.verify)
        r.raise_for_status()
        return r.json()

    def weather_forecast(self, entity_id: str, kind: str = "daily") -> list:
        """Daily forecast of a weather entity (service weather.get_forecasts, which returns data)."""
        r = requests.post(f"{self.url}/api/services/weather/get_forecasts?return_response", headers=self.h,
                          json={"entity_id": entity_id, "type": kind}, timeout=self.timeout, verify=self.verify)
        r.raise_for_status()
        resp = r.json().get("service_response") or {}
        return (resp.get(entity_id) or {}).get("forecast") or []

    def call_service(self, domain: str, service: str, data: dict):
        r = requests.post(f"{self.url}/api/services/{domain}/{service}", headers=self.h, json=data,
                          timeout=self.timeout, verify=self.verify)
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------ WebSocket
    def ws_lists(self) -> dict:
        """Area / entity / device registries (+ exposed entities) via the WebSocket API."""
        try:
            import websocket  # websocket-client
        except ImportError:
            print("websocket-client not installed: areas come from entity names only")
            return {}
        ws_url = self.ws_override or (re.sub(r"^http", "ws", self.url) + "/api/websocket")
        sslopt = None if self.verify else {"cert_reqs": 0}
        ws = websocket.create_connection(ws_url, timeout=self.timeout, sslopt=sslopt)
        try:
            json.loads(ws.recv())
            ws.send(json.dumps({"type": "auth", "access_token": self.token}))
            if json.loads(ws.recv()).get("type") != "auth_ok":
                raise RuntimeError("HA websocket auth failed")
            out = {}
            for i, (key, typ) in enumerate([("floors", "config/floor_registry/list"),
                                             ("areas", "config/area_registry/list"),
                                             ("entities", "config/entity_registry/list"),
                                             ("devices", "config/device_registry/list"),
                                             ("exposed", "homeassistant/expose_entity/list")], start=1):
                ws.send(json.dumps({"id": i, "type": typ}))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("id") == i:
                        break
                out[key] = msg.get("result") if msg.get("success") else None
            # the list above has no aliases / device class: ask for the full entries of the relevant entities
            ids = [e["entity_id"] for e in (out.get("entities") or [])
                   if e["entity_id"].split(".")[0] in SUPPORTED_DOMAINS]
            if ids:
                ws.send(json.dumps({"id": 99, "type": "config/entity_registry/get_entries", "entity_ids": ids}))
                while True:
                    msg = json.loads(ws.recv())
                    if msg.get("id") == 99:
                        break
                full = msg.get("result") if msg.get("success") else None
                if isinstance(full, dict):
                    for e in out["entities"]:
                        f = full.get(e["entity_id"]) or {}
                        for k in ("aliases", "device_class", "original_device_class"):
                            if k in f and k not in e:
                                e[k] = f[k]
            return out
        finally:
            ws.close()

    # -------------------------------------------------------------- catalog
    def build_catalog(self, only_exposed: bool = True, include_domains=None) -> Catalog:
        states = self.get("/api/states")
        reg = self.ws_lists()
        areas = [Area(id=a["area_id"], name=a["name"], aliases=list(a.get("aliases") or []), floor=a.get("floor_id"))
                 for a in (reg.get("areas") or [])]
        floors = {f["floor_id"]: {"name": f.get("name"), "aliases": list(f.get("aliases") or []), "level": f.get("level")}
                  for f in (reg.get("floors") or [])}
        ent_reg = {e["entity_id"]: e for e in (reg.get("entities") or [])}
        dev_area = {d["id"]: d.get("area_id") for d in (reg.get("devices") or [])}
        exposed = None
        ex = reg.get("exposed")
        if only_exposed and isinstance(ex, dict) and ex.get("exposed_entities"):
            exposed = {k for k, v in ex["exposed_entities"].items() if v.get("conversation")}
        domains = set(include_domains or SUPPORTED_DOMAINS)
        ents = []
        for s in states:
            eid = s["entity_id"]
            domain = eid.split(".")[0]
            if domain not in domains:
                continue
            if exposed is not None and eid not in exposed:
                continue
            er = ent_reg.get(eid, {})
            if er.get("hidden_by") or er.get("disabled_by") or er.get("entity_category"):
                continue
            e = convert_entity(s, er, dev_area)
            if e is not None:
                ents.append(e)
        link_players(ents, ent_reg, {d["id"]: d for d in (reg.get("devices") or [])})
        # features some players report only while playing (sources, shuffle, track buttons on Music Assistant
        # players): once seen they are kept, so the catalogue does not change (and is not rebuilt) every minute
        sticky = self.__dict__.setdefault("_sticky", {})
        for e in ents:
            old_f, old_a = sticky.get(e.id, (set(), {}))
            feats = set(e.features or []) | old_f
            attrs = dict(old_a, **{k: v for k, v in (e.attributes or {}).items() if v})
            sticky[e.id] = (feats, attrs)
            e.features, e.attributes = sorted(feats), attrs
        cfg = {}
        try:
            cfg = self.get("/api/config")
        except Exception:  # noqa: BLE001
            pass
        lang = (cfg.get("language") or "it")[:2]
        if self.virtual:
            ents += [Entity(id=v.id, domain=v.domain, name=VIRTUAL_NAMES.get(lang, VIRTUAL_NAMES["en"])[v.id])
                     for v in VIRTUAL]
        caps = build_capabilities(areas, ents, default_actions())
        used = {c.action for c in caps}
        return Catalog(areas, ents, [a for a in default_actions() if a.action in used], caps,
                       {"source": "homeassistant", "home_lang": lang, "location": cfg.get("location_name"),
                        "floors": floors})

    def refresh_states(self, catalog: Catalog):
        """Cheap state refresh (no re-embedding needed)."""
        for s in self.get("/api/states"):
            eid = s["entity_id"]
            if eid.startswith("input_boolean."):
                eid = "switch.__ib__" + eid.split(".", 1)[1]
            e = catalog.entities.get(eid)
            if e is not None:
                e.state = convert_state(e.domain, s)

    # -------------------------------------------------------------- execute
    def execute(self, decision: Decision, catalog: Catalog, dry_run: bool = False) -> dict:
        if decision.parts:
            # EXECUTE: all parts; CLARIFY: the clear parts, the question is about another one;
            # ESCALATE (only some parts understood): nothing - the whole request goes to the other agent
            if decision.policy not in ("EXECUTE", "CLARIFY"):
                return {"executed": False}
            return {"parts": [self.execute(p, catalog, dry_run) for p in decision.parts]}
        if decision.policy != "EXECUTE" or not decision.capability:
            return {"executed": False}
        spec = catalog.actions[decision.action]
        if decision.action.startswith("assist."):
            # carried out by the integration (Home Assistant intents on the satellite that heard the sentence)
            return {"executed": False, "assist": True}
        if spec.kind == "read":
            return {"executed": True, "read": {e: catalog.entities[e].state for e in decision.entities
                                               if e in catalog.entities}}
        if decision.action == "home.turn_off_all":
            if not self.allow_off_all:
                return {"executed": False, "error": "off_all_disabled"}
            from ..core.states import protected
            done = []
            for dom in ("light", "media_player", "fan", "switch"):
                ids = [e.id for e in catalog.entities.values() if e.domain == dom and not protected(e)
                       and str(e.state.get("state", "")) not in ("off", "standby", "unavailable")]
                if not ids:
                    continue
                d2, srv = ("homeassistant", "turn_off") if dom == "switch" else (dom, "turn_off")
                data = {"entity_id": [ha_entity_id(x) for x in ids]}
                if not dry_run:
                    self.call_service(d2, srv, data)
                done.append({"service": f"{d2}.{srv}", "data": data})
            return {"executed": not dry_run, "dry_run": dry_run, "calls": done}
        m = dict(spec.execute or {})
        if decision.action == "climate.set_preset_mode" and decision.resolved.get("preset"):
            decision.params = dict(decision.params, preset=decision.resolved["preset"])
        if not m.get("service"):
            return {"executed": False, "error": f"no service mapping for {decision.action}"}
        domain, service = m["service"].split(".", 1)
        if any(e.startswith("switch.__ib__") for e in decision.entities):
            domain = "homeassistant"  # input_boolean exposed as switch: generic turn_on/turn_off
        values = {**decision.params, **decision.resolved}
        data = {"entity_id": [ha_entity_id(e) for e in decision.entities]}
        for k, v in (m.get("data") or {}).items():
            data[k] = fill_template(v, values)
        data = {k: v for k, v in data.items() if v is not None}
        if dry_run:
            return {"executed": False, "dry_run": True, "service": f"{domain}.{service}", "data": data}
        try:
            self.call_service(domain, service, data)
        except Exception:  # noqa: BLE001
            if f"{domain}.{service}" != "music_assistant.play_media" or "media_type" not in data:
                raise
            # "radio DJ" may not be a station Music Assistant knows by that kind: search any kind, with the kind
            # word back in the name ("Radio DJ")
            kind = data.get("media_type")
            data = {k: v for k, v in data.items() if k != "media_type"}
            if kind == "radio" and "radio" not in str(data.get("media_id", "")).lower():
                data["media_id"] = f"Radio {data.get('media_id', '')}".strip()
            self.call_service(domain, service, data)
        return {"executed": True, "service": f"{domain}.{service}", "data": data}


def ha_entity_id(eid: str) -> str:
    # input_boolean entities are exposed as switches in the generic model
    return eid.replace("switch.__ib__", "input_boolean.")


def fill_template(v, values: dict):
    """'{brightness}', '-{step}', '{volume/100}' or {enum_value: mapped} -> concrete value."""
    if isinstance(v, dict):
        for key in values.values():
            if isinstance(key, str) and key in v:
                return v[key]
        return None
    if not isinstance(v, str):
        return v
    m = re.fullmatch(r"(-?)\{(\w+)(?:/(\d+))?\}", v)
    if not m:
        return v
    neg, name, div = m.groups()
    if name not in values:
        return None
    x = values[name]
    if isinstance(x, (int, float)):
        x = float(x) / float(div) if div else float(x)
        x = -x if neg else x
        return int(x) if float(x).is_integer() and not div else round(x, 3)
    return x


def convert_state(domain: str, s: dict) -> dict:
    a = s.get("attributes", {})
    st = {"state": s.get("state")}
    if domain == "light" and a.get("brightness") is not None:
        st["brightness"] = round(a["brightness"] / 255 * 100)
    if domain == "cover" and a.get("current_position") is not None:
        st["position"] = a["current_position"]
    if domain == "climate":
        if a.get("temperature") is not None:
            st["temperature"] = a["temperature"]
        if a.get("current_temperature") is not None:
            st["current_temperature"] = a["current_temperature"]
    if domain == "media_player":
        if a.get("volume_level") is not None:
            st["volume"] = round(a["volume_level"] * 100)
        if a.get("media_title"):
            st["media_title"] = a["media_title"]
    if domain == "fan" and a.get("percentage") is not None:
        st["percentage"] = a["percentage"]
    if domain == "weather":
        for k in ("temperature", "humidity", "wind_speed"):
            if a.get(k) is not None:
                st[k] = a[k]
    if domain == "binary_sensor" and a.get("device_class") not in BINARY_ALARM:
        st["state"] = {"on": "open", "off": "closed"}.get(s.get("state"), s.get("state"))
    if domain == "valve" and a.get("current_position") is not None:
        st["position"] = a["current_position"]
    if domain == "water_heater":
        if a.get("temperature") is not None:
            st["temperature"] = a["temperature"]
        if a.get("current_temperature") is not None:
            st["current_temperature"] = a["current_temperature"]
    if domain == "humidifier" and a.get("humidity") is not None:
        st["humidity"] = a["humidity"]
    if domain == "media_player" and a.get("source"):
        st["source"] = a["source"]
    if domain == "climate" and a.get("preset_mode"):
        st["preset"] = a["preset_mode"]
    return st


BINARY_ALARM = {"moisture", "smoke", "gas", "motion", "occupancy", "carbon_monoxide"}


def _hex12(text: str) -> set:
    return set(re.findall(r"[0-9a-f]{12}", re.sub(r"[:\-_]", "", str(text).lower())))


def _norm_name(text: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", clean_name(str(text or "")).lower()).split())


def link_players(ents: list, ent_reg: dict, devices: dict) -> None:
    """Media players: remember their HA device and platform, and pair each Music Assistant player with the player of
    the same speaker (a Voice PE has an ESPHome player and, once added to Music Assistant, a second one): same device,
    a MAC address / entity id in the Music Assistant device identifiers, or the same device name. A twin without a
    room takes its twin's room ("metti radio deejay" said in the living room finds the living-room speaker)."""
    players = [e for e in ents if e.domain == "media_player"]
    info = {}
    for e in players:
        er = ent_reg.get(e.id, {})
        dev = devices.get(er.get("device_id") or "") or {}
        e.attributes = dict(e.attributes or {}, device=er.get("device_id"), platform=er.get("platform"))
        info[e.id] = (er, dev)
    for ma in [e for e in players if (e.attributes or {}).get("platform") == "music_assistant"]:
        er, dev = info[ma.id]
        ids = " ".join(str(x) for pair in dev.get("identifiers") or [] for x in pair)
        ids_hex = _hex12(ids)
        names = {_norm_name(x) for x in (dev.get("name"), dev.get("name_by_user"), er.get("original_name")) if x}
        best = None
        for o in players:
            if o is ma or (o.attributes or {}).get("platform") == "music_assistant":
                continue
            oer, odev = info[o.id]
            macs = {_hex12(c[1]).pop() for c in odev.get("connections") or [] if len(c) > 1 and _hex12(c[1])}
            onames = {_norm_name(x) for x in (odev.get("name"), odev.get("name_by_user"), oer.get("original_name"))
                      if x}
            if (oer.get("device_id") and oer.get("device_id") == er.get("device_id")) or o.id in ids \
                    or (macs & ids_hex) or (dev.get("via_device_id") and dev.get("via_device_id") == odev.get("id")):
                best = o
                break
            if best is None and names & onames:
                best = o
        if best is not None:
            ma.attributes["twin"], best.attributes["twin"] = best.id, ma.id
            if not ma.area and best.area:
                ma.area = best.area
            elif not best.area and ma.area:
                best.area = ma.area


_IP = re.compile(r"[\(\[]?\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b[\)\]]?")
_MAC = re.compile(r"\b[0-9a-f]{2}(?:[:-][0-9a-f]{2}){5}\b", re.I)
_AT = re.compile(r"@\w*")


def clean_name(name: str) -> str:
    """A name that can be said: no IP / MAC addresses, no "@ES" tags, no entity-id underscores
    ("SHIELD Android TV@ES(192.168.0.42)" -> "SHIELD Android TV", "media_player.shield_2" -> "shield 2")."""
    raw = str(name or "")
    n = _MAC.sub(" ", _IP.sub(" ", raw))
    n = _AT.sub(" ", n)
    n = re.sub(r"[\(\[]\s*[\)\]]", " ", n)
    if " " not in n.strip() and ("_" in n or "." in n):
        n = n.split(".", 1)[-1].replace("_", " ")
    n = " ".join(n.split()).strip(" -_,;:@")
    return n or raw


def convert_entity(s: dict, er: dict, dev_area: dict) -> Optional[Entity]:
    eid = s["entity_id"]
    domain = eid.split(".")[0]
    a = s.get("attributes", {})
    name = clean_name(er.get("name") or a.get("friendly_name") or er.get("original_name") or eid)
    area = er.get("area_id") or dev_area.get(er.get("device_id"))
    dc = a.get("device_class") or er.get("device_class") or er.get("original_device_class")
    feats: list[str] = []
    attrs: dict = {}
    sf = int(a.get("supported_features") or 0)
    if domain == "input_boolean":
        domain = "switch"
        eid = "switch.__ib__" + eid.split(".", 1)[1]
    if domain == "light":
        modes = set(a.get("supported_color_modes") or [])
        if modes - {"onoff"}:
            feats.append("brightness")
        if modes & {"hs", "xy", "rgb", "rgbw", "rgbww"}:
            feats.append("color")
        if "color_temp" in modes or modes & {"rgbww"}:
            feats.append("color_temp")
    elif domain == "cover":
        if sf & COVER_SET_POSITION:
            feats.append("position")
        if sf and not sf & COVER_STOP:
            feats.append("no_stop")  # e.g. a garage door that can only open / close
        if sf & COVER_OPEN_TILT and sf & COVER_CLOSE_TILT:
            feats.append("tilt")
        if sf & COVER_SET_TILT:
            feats.append("tilt_position")
        if dc in ("blind", "shade", "roller", "window"):
            dc = "shutter"
        elif dc in ("curtain",):
            dc = "curtain"
        elif dc in ("garage",):
            dc = "garage"
        elif dc in ("gate",):
            dc = "gate"
        elif dc in ("awning",):
            dc = "awning"
        elif dc == "door":
            dc = "door"
        else:
            dc = "shutter"
    elif domain == "climate":
        modes = a.get("hvac_modes") or []
        attrs = {"min_temp": a.get("min_temp", 7), "max_temp": a.get("max_temp", 35), "hvac_modes": modes}
        if len([m for m in modes if m != "off"]) > 1:
            feats.append("hvac_modes")
        if sf & CLIMATE_PRESET and a.get("preset_modes"):
            feats.append("presets")
            attrs["presets"] = list(a["preset_modes"])
    elif domain == "media_player":
        if sf & MP_VOLUME_SET:
            feats.append("volume")
        if sf & (MP_PAUSE | MP_PLAY):
            feats.append("playback")
        if sf & MP_NEXT:
            feats.append("tracks")
        if er.get("platform") == "music_assistant":
            feats.append("search")  # Music Assistant finds songs, artists, playlists and radio stations by name
        if sf & MP_SELECT_SOURCE and a.get("source_list"):
            feats.append("sources")
            attrs = {"sources": list(a["source_list"])[:40]}
        if sf & MP_SHUFFLE_SET:
            feats.append("shuffle")
        dc = "tv" if dc == "tv" else "speaker"
    elif domain == "fan":
        if sf & FAN_SET_SPEED:
            feats.append("speed")
    elif domain == "vacuum":
        if sf & VACUUM_RETURN_HOME:
            feats.append("return_home")
    elif domain == "sensor":
        if dc not in SENSOR_CLASSES:
            return None
        attrs = {"unit": a.get("unit_of_measurement", "")}
    elif domain == "binary_sensor":
        if dc not in BINARY_CLASSES:
            return None
        if dc in ("door", "garage_door"):
            dc = "door"
        elif dc in ("window", "opening"):
            dc = "window"
    elif domain == "valve":
        dc = "gas" if (dc == "gas" or re.search(r"\bgas\b|gaz", name, re.I)) else "water"
    elif domain == "water_heater":
        attrs = {"min_temp": a.get("min_temp", 30), "max_temp": a.get("max_temp", 75)}
    elif domain == "humidifier":
        feats.append("humidity")
        attrs = {"min_humidity": a.get("min_humidity", 20), "max_humidity": a.get("max_humidity", 90)}
        dc = dc or "humidifier"
    elif domain == "button":
        dc = "gate" if GATE_WORDS.search(name) else (dc or "generic")
    elif domain == "todo":
        if not sf & TODO_CREATE:
            return None
    elif domain == "person":
        pass
    aliases = [x for x in (er.get("aliases") or []) if isinstance(x, str) and x.strip()]
    return Entity(id=eid, domain=domain, name=name, area=area, aliases=aliases, device_class=dc, features=feats,
                  state=convert_state(domain, s), attributes=attrs)


# ------------------------------------------------------------ spoken replies
MESSAGES = {
    "it": {"ok": "Fatto.", "ambiguous": "Intendi {opts}?", "low_confidence": "Non sono sicuro: intendi {opts}?",
           "missing_param": "A che valore?", "invalid_param": "Il valore richiesto non è valido.",
           "confirm_high_risk": "Confermi l'operazione su {opts}?", "cancelled": "Va bene, lascio stare.", "not_understood": "Non ho capito, puoi ripetere?", "unsupported": "Non posso farlo con i dispositivi disponibili.",
           "unavailable": "Il dispositivo non è raggiungibile.", "noop": "Va bene.", "escalate": "Ci penso...",
           "read": "{name}: {state}."},
    "en": {"ok": "Done.", "ambiguous": "Do you mean {opts}?", "low_confidence": "I'm not sure: do you mean {opts}?",
           "missing_param": "To what value?", "invalid_param": "That value is not valid.",
           "confirm_high_risk": "Please confirm the action on {opts}.", "cancelled": "Okay, cancelled.", "not_understood": "Sorry, I didn't catch that. Can you say it again?", "unsupported": "I can't do that with the available devices.",
           "unavailable": "That device is unavailable.", "noop": "Okay.", "escalate": "Let me think...",
           "read": "{name}: {state}."},
    "es": {"ok": "Hecho.", "ambiguous": "¿Te refieres a {opts}?", "low_confidence": "No estoy seguro: ¿te refieres a {opts}?",
           "missing_param": "¿A qué valor?", "invalid_param": "Ese valor no es válido.",
           "confirm_high_risk": "¿Confirmas la acción en {opts}?", "cancelled": "Vale, lo dejo.", "not_understood": "No te he entendido, ¿puedes repetirlo?", "unsupported": "No puedo hacerlo con los dispositivos disponibles.",
           "unavailable": "El dispositivo no está disponible.", "noop": "Vale.", "escalate": "Déjame pensar...",
           "read": "{name}: {state}."},
}


# 0.8.2: replies when Home Assistant refuses the call, and for options switched off
EXTRA_MESSAGES = {
    "it": {"failed": "Non ci sono riuscito: {name} ha restituito un errore.", "not_found": "Non ho trovato {content}.",
           "off_all_disabled": "Il comando per spegnere tutta la casa è disattivato nelle impostazioni."},
    "en": {"failed": "I couldn't do it: {name} returned an error.", "not_found": "I couldn't find {content}.",
           "off_all_disabled": "Turning off the whole house is disabled in the settings."},
    "es": {"failed": "No lo he conseguido: {name} ha devuelto un error.", "not_found": "No he encontrado {content}.",
           "off_all_disabled": "Apagar toda la casa está desactivado en los ajustes."},
    "fr": {"failed": "Je n'ai pas réussi : {name} a renvoyé une erreur.", "not_found": "Je n'ai pas trouvé {content}.",
           "off_all_disabled": "La commande pour tout éteindre est désactivée dans les réglages."},
    "de": {"failed": "Das hat nicht geklappt: {name} hat einen Fehler gemeldet.",
           "not_found": "Ich habe {content} nicht gefunden.",
           "off_all_disabled": "Alles ausschalten ist in den Einstellungen deaktiviert."},
    "nl": {"failed": "Dat is niet gelukt: {name} gaf een fout.", "not_found": "Ik heb {content} niet gevonden.",
           "off_all_disabled": "Alles uitzetten is uitgeschakeld in de instellingen."},
    "pt": {"failed": "Não consegui: {name} devolveu um erro.", "not_found": "Não encontrei {content}.",
           "off_all_disabled": "Desligar a casa toda está desativado nas definições."},
    "pl": {"failed": "Nie udało się: {name} zgłosił błąd.", "not_found": "Nie znalazłem: {content}.",
           "off_all_disabled": "Wyłączanie całego domu jest wyłączone w ustawieniach."},
    "sv": {"failed": "Det gick inte: {name} gav ett fel.", "not_found": "Jag hittade inte {content}.",
           "off_all_disabled": "Att stänga av hela huset är avstängt i inställningarna."},
}


def error_reply(decision: Decision, catalog: Catalog, lang: str, error: str) -> str:
    """What to say when Home Assistant refused the call (never "Fatto.")."""
    X = EXTRA_MESSAGES.get(lang, EXTRA_MESSAGES["en"])
    if error == "off_all_disabled":
        return X["off_all_disabled"]
    content = (decision.params or {}).get("content")
    if decision.action == "media_player.play_content" and content:
        return X["not_found"].format(content=content)
    try:
        name = spoken_target(catalog, decision.capability, lang) if decision.capability else "Home Assistant"
    except Exception:  # noqa: BLE001
        name = "Home Assistant"
    return X["failed"].format(name=name)


def _lang_mod(lang: str):
    from ..core import lang as L
    return L.get(lang)


def _ensure_messages(lang: str) -> None:
    if lang not in MESSAGES and _lang_mod(lang) is not None:
        MESSAGES[lang] = dict(MESSAGES["en"], **_lang_mod(lang).MESSAGES)


def _tokens(text: str) -> list:
    from ..core.specific import tokens
    return tokens(text)


def reply(decision: Decision, catalog: Catalog, lang: str = "it") -> str:
    from ..core.render import state_summary, target_parts

    _ensure_messages(lang)
    M = MESSAGES.get(lang, MESSAGES["en"])
    if decision.parts and decision.policy == "CLARIFY":
        from dataclasses import replace as _replace
        done = multi_reply(decision.parts, catalog, lang)
        return f"{done} {reply(_replace(decision, parts=[]), catalog, lang)}"
    if decision.parts:
        if decision.policy != "EXECUTE":
            return M["escalate"] if decision.policy == "ESCALATE" else M["unsupported"]
        return multi_reply(decision.parts, catalog, lang)

    def label(cap_id):
        return spoken_target(catalog, cap_id, lang)

    if decision.policy == "EXECUTE" and decision.reason in ("self_time", "self_date"):
        from ..core.clock import clock_reply
        return clock_reply(decision.reason[5:], lang)
    if decision.policy == "EXECUTE" and decision.reason == "self_location":
        area = (decision.params or {}).get("area") or ""
        return {"it": "Sono in {a}.", "en": "I'm in the {a}.", "es": "Estoy en {a}.", "fr": "Je suis dans {a}.",
                "de": "Ich bin im Raum {a}.", "nl": "Ik ben in {a}.", "pt": "Estou em {a}.", "pl": "Jestem w: {a}.",
                "sv": "Jag är i {a}."}.get(lang, "I'm in the {a}.").format(a=area)
    if decision.policy == "EXECUTE":
        spec = catalog.actions.get(decision.action)
        if decision.action == "weather.get_state" and decision.entities:
            from ..core.weather import weather_reply
            e = catalog.entities[decision.entities[0]]
            day = (decision.params or {}).get("day")
            return weather_reply(e.state or {}, day, (e.attributes or {}).get("forecast"), lang)
        if decision.action and decision.action.startswith("assist."):
            from ..core.assist import assist_reply
            return assist_reply(decision, lang)
        if decision.action == "todo.add_item" and decision.entities:
            from ..core import states as S
            item = (decision.params or {}).get("item") or ""
            lst = catalog.entities[decision.entities[0]].name if decision.entities[0] in catalog.entities else ""
            return S.W2.get(lang, S.W2["en"])["list_added"].format(item=item, list=lst)
        if decision.action == "home.get_state":
            from ..core import states as S
            return S.home_reply(catalog, lang)
        if spec and spec.kind == "read":
            from ..core import states as S
            ents = [catalog.entities[e] for e in decision.entities if e in catalog.entities]
            cap = catalog.cap(decision.capability) if decision.capability and catalog.has_cap(decision.capability) else None
            kind = cap.target_kind if cap is not None else None
            if decision.action == "person.get_state" and (kind in ("all_group", "floor_group") or len(ents) > 1):
                return S.people_reply(ents, lang)
            if kind in ("all_group", "floor_group") and decision.reason not in ("ok_room_state",):
                return S.house_reply(ents, lang, count=bool(set(_tokens(decision.text or "")) & S.COUNT_WORDS))
            if kind == "area_group":
                return S.area_reply(ents, catalog.area_name(cap.target.split(":")[1]), lang)
            if decision.reason == "ok_house_state":   # "ci sono luci accese?"
                from ..core.specific import tokens as _tok
                return S.house_reply(ents, lang, count=bool(set(_tok(decision.text or "")) & S.COUNT_WORDS))
            if decision.reason == "ok_room_state":    # "la luce del salone è accesa?" with two lights
                area = catalog.area_name(ents[0].area) if ents and ents[0].area else None
                return S.area_reply(ents, area, lang)
            return " ".join(M["read"].format(name=e.name, state=S.describe(e, lang)) for e in ents)
        return M["ok"]
    if decision.policy == "CLARIFY":
        key = decision.reason.split(":")[0]
        if key == "missing_param" and decision.action == "media_player.play_content":
            from ..core.media import WHAT_TO_PLAY
            return WHAT_TO_PLAY.get(lang, WHAT_TO_PLAY["en"])
        if key == "missing_param" and decision.missing_params:
            from ..core.assist import ask_missing
            q = ask_missing(decision.missing_params[0], lang)
            if q:
                return q
        names = list(dict.fromkeys(label(a["capability"]) for a in decision.alternatives[:4]
                                   if a["capability"] != "NO_ACTION"))
        if key == "confirm_high_risk" or not names:
            names = [label(decision.capability)] if decision.capability else ["?"]
        orw = {"it": " o ", "en": " or ", "es": " o "}.get(lang) or getattr(_lang_mod(lang), "OR", " / ")
        opts = names[0] if len(names) == 1 else ", ".join(names[:-1]) + orw + names[-1]
        verb = _INF.get((decision.action or "").split(".")[-1], {}).get(lang)
        if len(names) == 1 and key in ("ambiguous", "low_confidence") and verb:
            # "Spende la luce in camera" -> "Vuoi spegnere le luci in Camera?" (a yes must not turn them on)
            return {"it": "Vuoi {v} {o}?", "en": "Do you want to {v} {o}?", "es": "¿Quieres {v} {o}?"}[lang].format(
                v=verb, o=opts)
        return M.get(key, M["low_confidence"]).format(opts=opts)
    if decision.policy == "ESCALATE":
        return M["escalate"]
    return M.get(decision.reason, M["unsupported"])


# infinitive of the action, for a question about one device ("Vuoi spegnere ...?")
_INF = {"turn_on": {"it": "accendere", "en": "turn on", "es": "encender"},
        "turn_off": {"it": "spegnere", "en": "turn off", "es": "apagar"},
        "open": {"it": "aprire", "en": "open", "es": "abrir"},
        "close": {"it": "chiudere", "en": "close", "es": "cerrar"}}


# ------------------------------------------------ several commands: say what was done
_DOING = {  # action suffix -> (it, en, es)
    "turn_on": ("accendo", "turning on", "enciendo"), "turn_off": ("spengo", "turning off", "apago"),
    "open": ("apro", "opening", "abro"), "close": ("chiudo", "closing", "cierro"), "stop": ("fermo", "stopping", "paro"),
    "set_position": ("regolo", "setting", "ajusto"), "set_brightness": ("regolo", "setting", "ajusto"),
    "set_color": ("cambio colore a", "changing the colour of", "cambio el color de"),
    "set_color_temp": ("regolo", "setting", "ajusto"), "set_temperature": ("regolo", "setting", "ajusto"),
    "set_hvac_mode": ("regolo", "setting", "ajusto"), "set_speed": ("regolo", "setting", "ajusto"),
    "volume_set": ("regolo il volume di", "setting the volume of", "ajusto el volumen de"),
    "brightness_up": ("alzo", "raising", "subo"), "brightness_down": ("abbasso", "lowering", "bajo"),
    "temperature_up": ("alzo", "raising", "subo"), "temperature_down": ("abbasso", "lowering", "bajo"),
    "volume_up": ("alzo il volume di", "turning up", "subo el volumen de"),
    "volume_down": ("abbasso il volume di", "turning down", "bajo el volumen de"),
    "play_content": ("metto la musica su", "playing music on", "pongo música en"),
    "play": ("faccio partire", "playing", "reproduzco"), "pause": ("metto in pausa", "pausing", "pauso"),
    "next_track": ("vado avanti su", "skipping on", "paso al siguiente en"),
    "previous_track": ("torno indietro su", "going back on", "vuelvo atrás en"),
    "mute": ("tolgo l'audio a", "muting", "silencio"), "lock": ("chiudo a chiave", "locking", "cierro con llave"),
    "unlock": ("apro", "unlocking", "abro"), "start": ("avvio", "starting", "inicio"),
    "return_to_base": ("mando alla base", "sending home", "envío a la base"), "activate": ("attivo", "activating", "activo"),
    "arm_away": ("inserisco", "arming", "activo"), "arm_home": ("inserisco", "arming", "activo"),
    "disarm": ("disinserisco", "disarming", "desactivo"),
}
_DONE = {  # the same, in the past ("cosa hai fatto?")
    "turn_on": ("ho acceso", "turned on", "encendí"), "turn_off": ("ho spento", "turned off", "apagué"),
    "open": ("ho aperto", "opened", "abrí"), "close": ("ho chiuso", "closed", "cerré"), "stop": ("ho fermato", "stopped", "paré"),
    "set_position": ("ho regolato", "set", "ajusté"), "set_brightness": ("ho regolato", "set", "ajusté"),
    "set_color": ("ho cambiato colore a", "changed the colour of", "cambié el color de"),
    "set_color_temp": ("ho regolato", "set", "ajusté"), "set_temperature": ("ho regolato", "set", "ajusté"),
    "set_hvac_mode": ("ho regolato", "set", "ajusté"), "set_speed": ("ho regolato", "set", "ajusté"),
    "volume_set": ("ho regolato il volume di", "set the volume of", "ajusté el volumen de"),
    "brightness_up": ("ho alzato", "raised", "subí"), "brightness_down": ("ho abbassato", "lowered", "bajé"),
    "temperature_up": ("ho alzato", "raised", "subí"), "temperature_down": ("ho abbassato", "lowered", "bajé"),
    "volume_up": ("ho alzato il volume di", "turned up", "subí el volumen de"),
    "volume_down": ("ho abbassato il volume di", "turned down", "bajé el volumen de"),
    "play_content": ("ho messo la musica su", "played music on", "puse música en"),
    "play": ("ho fatto partire", "played", "reproduje"), "pause": ("ho messo in pausa", "paused", "pausé"),
    "next_track": ("sono andato avanti su", "skipped on", "pasé al siguiente en"),
    "previous_track": ("sono tornato indietro su", "went back on", "volví atrás en"),
    "mute": ("ho tolto l'audio a", "muted", "silencié"), "lock": ("ho chiuso a chiave", "locked", "cerré con llave"),
    "unlock": ("ho aperto", "unlocked", "abrí"), "start": ("ho avviato", "started", "inicié"),
    "return_to_base": ("ho mandato alla base", "sent home", "envié a la base"),
    "activate": ("ho attivato", "activated", "activé"), "arm_away": ("ho inserito", "armed", "activé"),
    "arm_home": ("ho inserito", "armed", "activé"), "disarm": ("ho disinserito", "disarmed", "desactivé"),
}
_GROUP = {  # group key -> (it plural with article, en, es)
    "light": ("le luci", "the lights", "las luces"), "cover.shutter": ("le tapparelle", "the shutters", "las persianas"),
    "cover": ("le tapparelle", "the covers", "las persianas"), "switch": ("le prese", "the switches", "los enchufes"),
    "fan": ("i ventilatori", "the fans", "los ventiladores"), "media_player": ("i dispositivi", "the players", "los equipos"),
    "climate": ("i termostati", "the thermostats", "los termostatos"),
}
_ALL = ("tutte", "all", "todas")
_ALL_M = ("tutti", "all", "todos")
_IN = ("in", "in", "en")
_AND = (" e ", " and ", " y ")


def _short(suffix: str) -> str:
    """Action suffix -> key of DOING / DONE in core/lang/<lang>.py."""
    if suffix in ("set_position", "set_brightness", "set_color_temp", "set_temperature", "set_hvac_mode", "set_speed"):
        return "set"
    if suffix in ("brightness_up", "temperature_up"):
        return "up"
    if suffix in ("brightness_down", "temperature_down"):
        return "down"
    if suffix in ("arm_away", "arm_home"):
        return "arm"
    return suffix


def spoken_target(cat: Catalog, cap_id: str, lang: str) -> str:
    i = {"it": 0, "en": 1, "es": 2}.get(lang)
    cap = cat.cap(cap_id)
    if i is None and _lang_mod(lang) is not None and cap.target_kind != "entity":
        m = _lang_mod(lang)
        key = cap.target.split(":")[-1]
        pick = lambda t: t.get(key) or t.get(key.split(".")[0]) or t["_"]  # noqa: E731
        if cap.target_kind == "all_group":
            return pick(m.GROUP_ALL)
        if cap.target_kind == "floor_group":
            return f"{pick(m.GROUP)} {m.IN} {cat.floor_name(cap.target.split(':')[1])}"
        return f"{pick(m.GROUP)} {m.IN} {cat.area_name(cap.target.split(':')[1])}"
    i = 1 if i is None else i
    if cap.target_kind == "entity":
        e = cat.entities.get(cap.target)
        return e.name if e else cap.target
    key = cap.target.split(":")[-1]
    grp = _GROUP.get(key) or _GROUP.get(key.split(".")[0]) or ("i dispositivi", "the devices", "los dispositivos")
    noun = grp[i]
    if cap.target_kind == "all_group":
        masc = noun.startswith(("i ", "los "))
        return f"{(_ALL_M if masc else _ALL)[i]} {noun}"
    if cap.target_kind == "floor_group":
        return f"{noun} {_IN[i]} {cat.floor_name(cap.target.split(':')[1])}"
    return f"{noun} {_IN[i]} {cat.area_name(cap.target.split(':')[1])}"


def multi_reply(parts: list, cat: Catalog, lang: str, past: bool = False) -> str:
    """"Spengo tutte le luci e accendo TV taverna." - so that the user hears what was done.
    past=True: "ho spento tutte le luci e ho acceso TV taverna" (answer to "cosa hai fatto?")."""
    i = {"it": 0, "en": 1, "es": 2}.get(lang)
    m = _lang_mod(lang) if i is None else None
    i = 1 if i is None else i
    said = []
    for p in parts:
        spec = cat.actions.get(p.action or "")
        if spec is not None and spec.kind == "read":
            if not past:
                said.append(reply(p, cat, lang).rstrip("."))
            continue
        suffix = (p.action or "").split(".")[-1]
        if m is not None:
            v = (m.DONE if past else m.DOING).get(_short(suffix))
            verb = (v,) * 3 if v else None
        else:
            verb = (_DONE if past else _DOING).get(suffix)
        if verb is None or not p.capability:
            return reply(Decision(policy="EXECUTE", reason="ok"), cat, lang)
        said.append(f"{verb[i]} {spoken_target(cat, p.capability, lang)}")
    if not said:
        return ""
    conj = m.AND if m is not None else _AND[i]
    text = ", ".join(said[:-1]) + conj + said[-1] if len(said) > 1 else said[0]
    return text if past else text[:1].upper() + text[1:] + "."


_WHAT_DONE = re.compile(r"\b(?:cosa hai fatto|che hai fatto|cos'hai fatto|che cosa hai fatto|ultime (?:cose|azioni)|"
                        r"what did you (?:just )?do|what have you done|last actions|"
                        r"qu[eé] (?:has|hiciste) hecho|qu[eé] hiciste|[uú]ltimas acciones|"
                        # noun phrases without a verb ("ultimi comandi eseguiti", "letzte Befehle"), 9 languages
                        r"ultim[ie] (?:comandi|operazioni|azioni|richieste)|comandi eseguiti|"
                        r"(?:last|latest|recent) (?:commands|actions)|commands (?:you )?(?:ran|executed)|"
                        r"[uú]ltim[oa]s (?:comandos|órdenes|ordenes)|comandos ejecutados|"
                        r"derni[eè]res? (?:commandes|actions)|letzten? (?:befehle|aktionen)|"
                        r"laatste (?:opdrachten|commando'?s|acties)|"
                        r"[uú]ltim[oa]s (?:a[cç][oõ]es|ordens)|comandos executados|"
                        r"ostatnie (?:polecenia|komendy|akcje)|senaste (?:kommandon|åtgärderna|åtgärder))\b", re.IGNORECASE)
_AGO = {"now": ("poco fa", "just now", "hace un momento"), "min": ("{n} minuti fa", "{n} minutes ago", "hace {n} minutos"),
        "hour": ("{n} ore fa", "{n} hours ago", "hace {n} horas")}
_NOTHING = ("Non ho ancora eseguito niente.", "I haven't done anything yet.", "Todavía no he hecho nada.")


def is_history_question(text: str) -> bool:
    return bool(_WHAT_DONE.search(text or ""))


def history_reply(entries: list, cat: Catalog, lang: str, now: float, n: int = 3) -> str:
    """entries: newest last, each {"t": time, "decision": Decision} of an executed command."""
    i = {"it": 0, "en": 1, "es": 2}.get(lang)
    m = _lang_mod(lang) if i is None else None
    i = 1 if i is None else i
    ago_t = {k: (v,) * 3 for k, v in m.AGO.items()} if m is not None else _AGO
    nothing = m.NOTHING if m is not None else _NOTHING[i]
    out = []
    for h in reversed(entries):
        d = h["decision"]
        said = multi_reply(d.parts or [d], cat, lang, past=True)
        generic = MESSAGES.get(lang, MESSAGES["en"]).get("ok", "")
        if not said or said.strip(" .") == generic.strip(" ."):
            continue  # nothing to tell ("Fatto.") - e.g. a timer: say the commands that can be described
        said = said.rstrip(" .")
        dt = now - h["t"]
        ago = ago_t["now"][i] if dt < 60 else (ago_t["min"][i].format(n=int(dt // 60)) if dt < 3600
                                              else ago_t["hour"][i].format(n=int(dt // 3600)))
        fmt = getattr(m, "HISTORY_FMT", None) if m is not None else None
        if fmt:  # word order of the language, e.g. Swedish "Jag stängde av ... (nyss)"
            t = fmt.format(said=said, ago=ago)
            out.append(t[:1].upper() + t[1:])
        else:
            out.append(f"{ago[:1].upper() + ago[1:]} {said}")
        if len(out) == n:
            break
    return ". ".join(out) + "." if out else nothing
