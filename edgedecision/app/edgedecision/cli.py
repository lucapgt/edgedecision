"""EdgeDecision command line.

  python -m edgedecision.cli decide  --bundle bundle --catalog data/gold/demo_home.json "accendi la luce del soggiorno"
  python -m edgedecision.cli repl    --bundle bundle --catalog data/gold/demo_home.json
  python -m edgedecision.cli ha-export --url http://homeassistant.local:8123 --token TOKEN --out data/my_home.json
  python -m edgedecision.cli serve   --bundle bundle --ha-url http://homeassistant.local:8123 --token TOKEN --port 8765
  python -m edgedecision.cli bench   --bundle bundle --catalog data/gold/demo_home.json --threads 4
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .core.engine import EdgeDecisionEngine
from .core.policy import PolicyConfig
from .core.types import Catalog


def _utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass


def make_engine(bundle: str, threads=None) -> EdgeDecisionEngine:
    from .runtime.onnx_backend import OnnxBackend

    b = Path(bundle)
    backend = OnnxBackend(str(b), threads=threads)
    pol = PolicyConfig.load(b / "policy.json") if (b / "policy.json").exists() else PolicyConfig()
    return EdgeDecisionEngine(backend, pol)


def load_catalog(a):
    ha = None
    if getattr(a, "ha_url", None):
        from .adapters.homeassistant import HomeAssistant

        ha = HomeAssistant(a.ha_url, a.token or os.environ.get("HA_TOKEN", ""), verify_ssl=not a.insecure)
        cat = ha.build_catalog(only_exposed=not getattr(a, "all_entities", False))
    else:
        cat = Catalog.load(a.catalog)
    return cat, ha


def fmt(d) -> str:
    s = f"{d.policy:<8} {d.reason:<22} conf={d.confidence:.2f}"
    if d.capability:
        s += f"  -> {d.capability}"
    if d.params:
        s += f"  params={d.params}"
    if d.resolved and d.resolved != d.params:
        s += f"  resolved={d.resolved}"
    if d.parts:
        s += "\n" + "\n".join("   + " + fmt(p) for p in d.parts)
    if d.policy == "CLARIFY" and d.alternatives:
        s += "\n   options: " + ", ".join(f"{x['capability']} ({x['prob']:.2f})" for x in d.alternatives[:4])
    s += f"   [{d.latency_ms:.0f} ms]"
    return s


def cmd_decide(a):
    eng = make_engine(a.bundle, a.threads)
    cat, ha = load_catalog(a)
    eng.set_catalog(cat)
    d = eng.decide(a.text, a.context_area)
    if a.json:
        print(json.dumps(d.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        print(fmt(d))
        from .adapters.homeassistant import reply
        print("reply:", reply(d, cat, a.lang))
    if ha is not None and (a.execute or a.dry_run):
        print(json.dumps(ha.execute(d, cat, dry_run=not a.execute), ensure_ascii=False))


def cmd_repl(a):
    from .adapters.homeassistant import reply

    eng = make_engine(a.bundle, a.threads)
    cat, ha = load_catalog(a)
    eng.set_catalog(cat)
    print(f"{len(cat.capabilities)} capabilities loaded. Type a command ('@area text' sets the user's area, 'q' quits).")
    while True:
        try:
            t = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if t in ("q", "quit", "exit"):
            break
        ctx = None
        if t.startswith("@"):
            ctx, _, t = t[1:].partition(" ")
        if ha is not None:
            ha.refresh_states(cat)
        d = eng.decide(t, ctx, session="repl")  # answers to its questions ("la seconda", "sì") are understood
        print(fmt(d))
        print("  reply:", reply(d, cat, a.lang))
        if ha is not None and (a.execute or a.dry_run):
            print("  ", json.dumps(ha.execute(d, cat, dry_run=not a.execute), ensure_ascii=False))


def cmd_ha_export(a):
    from .adapters.homeassistant import HomeAssistant

    ha = HomeAssistant(a.url, a.token or os.environ.get("HA_TOKEN", ""), verify_ssl=not a.insecure)
    cat = ha.build_catalog(only_exposed=not a.all_entities)
    cat.save(a.out)
    doms = {}
    for e in cat.entities.values():
        doms[e.domain] = doms.get(e.domain, 0) + 1
    print(f"saved {a.out}: {len(cat.areas)} areas, {len(cat.entities)} entities {doms}, "
          f"{len(cat.capabilities)} capabilities, language={cat.meta.get('home_lang')}")


def cmd_bench(a):
    import statistics

    eng = make_engine(a.bundle, a.threads)
    cat, _ = load_catalog(a)
    eng.set_catalog(cat)
    texts = ["accendi la luce del soggiorno", "turn off the kitchen lights", "sube la persiana del salón al 50%",
             "che temperatura c'è in camera?", "raccontami una barzelletta", "abbassa un po' la luce",
             "set the thermostat to 21 degrees", "apaga todas las luces"]
    for t in texts[:2]:
        eng.decide(t)
    lat = []
    t0 = time.time()
    for _ in range(a.n):
        for t in texts:
            d = eng.decide(t)
            lat.append(d.latency_ms)
    lat.sort()
    print(f"{len(lat)} decisions, threads={a.threads}, top_k={eng.policy.top_k}: "
          f"p50={statistics.median(lat):.1f} ms  p95={lat[int(len(lat) * .95) - 1]:.1f} ms  "
          f"throughput={len(lat) / (time.time() - t0):.1f}/s  model={eng.backend.model_file}")


def cmd_serve(a):
    engines = {}
    for i, spec in enumerate((a.bundles or f"default={a.bundle}").split(",")):
        name, _, path = spec.partition("=")
        engines[name.strip()] = make_engine(path.strip(), a.threads)
    cat, ha = load_catalog(a)
    run_server(engines, cat, ha, a.host, a.port, a.lang, a.refresh_seconds, a.all_entities, a.verbose,
               testset=getattr(a, "testset", None))


def catalog_signature(cat) -> tuple:
    """What the model sees of a home: when it changes the capabilities must be embedded again."""
    ents = tuple(sorted((e.id, e.name, e.area or "", e.device_class or "", tuple(e.features), tuple(e.aliases))
                        for e in cat.entities.values()))
    areas = tuple(sorted((a.id, a.name, tuple(a.aliases)) for a in cat.areas.values()))
    return ents, areas


def run_server(engines: dict, cat, ha, host="0.0.0.0", port=8765, lang="it", refresh_seconds=2.0,
               all_entities=False, verbose=False, testset=None, watch_seconds=60.0, history_file=None):
    """HTTP API.

    POST /decide {"text", "context_area"?, "session"?, "execute"?, "lang"?, "model"?}
         -> {"decision", "reply", "execution"?, "model"}
    POST /reload   rebuild the catalog from Home Assistant (after adding / renaming devices)
    GET  /health   {"ok", "capabilities", "models"}
    GET  /info     platform, CPU, library versions, models
    GET  /testset  the hand-written test set (for scripts/remote_test.py)
    GET  /testset/<lang>   test set of the translated test home in that language (for scripts/test_langs.py)
    POST /decide {..., "home": "<lang>"}  decide on the translated test home (data/homes/casa_<lang>_home.json):
                   decisions only, nothing is executed, the real catalogue is not touched
    GET  /states   current state of every device of the catalogue (Home Assistant mode)
    With Home Assistant the catalogue is also checked every `watch_seconds`: new, renamed or moved devices
    are picked up without restarting.
    """
    import platform

    from collections import deque

    from .adapters.homeassistant import history_reply, is_history_question, reply

    default = next(iter(engines))
    for eng in engines.values():
        eng.set_catalog(cat)
    lock = threading.Lock()
    state = {"cat": cat, "last_refresh": 0.0}
    history: deque = deque(maxlen=50)   # every decision (GET /history)
    done: deque = deque(maxlen=20)      # executed commands ("cosa hai fatto?")

    def info():
        import numpy
        import onnxruntime
        import tokenizers
        return {"platform": platform.platform(), "machine": platform.machine(), "cpus": os.cpu_count(),
                "python": platform.python_version(), "onnxruntime": onnxruntime.__version__,
                "tokenizers": tokenizers.__version__, "numpy": numpy.__version__,
                "models": {k: {"file": getattr(e.backend, "model_file", ""), "layers": e.backend.meta.get("layers")}
                           for k, e in engines.items()},
                "default_model": default, "capabilities": len(state["cat"].capabilities),
                "entities": len(state["cat"].entities), "source": "homeassistant" if ha else "catalog file"}

    def rebuild(force=False):
        new = ha.build_catalog(only_exposed=not all_entities)
        if not force and catalog_signature(new) == catalog_signature(state["cat"]):
            return False
        t0 = time.time()
        with lock:
            for eng in engines.values():
                eng.set_catalog(new)
            state["cat"] = new
        print(f"catalogue updated: {len(new.entities)} entities, {len(new.capabilities)} capabilities "
              f"({time.time() - t0:.1f} s)", flush=True)
        return True

    def watch():
        while True:
            time.sleep(watch_seconds)
            try:
                rebuild()
            except Exception as e:  # noqa: BLE001  (HA restarting...)
                print(f"catalogue check failed: {e}", flush=True)

    test_engines: dict = {}

    def test_engine(model, home):
        """An engine on a translated test home (same model and policy, own catalogue); built on first use."""
        key = (model, home)
        if key not in test_engines:
            base, _, sfx = home.partition("_")  # "fr" or "fr_r6"
            f = Path(testset).parent / "homes" / f"casa_{base}_home{'_' + sfx if sfx else ''}.json" if testset else None
            if f is None or not base.isalnum() or not (sfx == "" or sfx.isalnum()) or not f.exists():
                return None
            from .core.engine import EdgeDecisionEngine
            h = json.loads(f.read_text(encoding="utf-8"))
            e = EdgeDecisionEngine(engines[model].backend, engines[model].policy)
            e.set_catalog(Catalog.from_dict(h.get("catalog", h)))
            test_engines[key] = e
        return test_engines[key]

    if ha is not None and watch_seconds:
        threading.Thread(target=watch, daemon=True).start()

    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj, raw=None):
            body = raw if raw is not None else json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"ok": True, "capabilities": len(state["cat"].capabilities), "models": list(engines)})
            elif self.path == "/info":
                self._send(200, info())
            elif self.path == "/testset" and testset and Path(testset).exists():
                self._send(200, None, raw=Path(testset).read_bytes())
            elif self.path.startswith("/testset/") and testset:
                key = self.path.split("/")[-1]  # "fr" or "fr_r6" (round-6 sentences)
                home, _, sfx = key.partition("_")
                f = Path(testset).parent / "homes" / f"casa_{home}_test{'_' + sfx if sfx else ''}.jsonl"
                self._send(200, None, raw=f.read_bytes()) if f.exists() else self._send(404, {"error": "no test set"})
            elif self.path == "/history":
                self._send(200, list(history))
            elif self.path == "/states" and ha is not None:
                with lock:
                    ha.refresh_states(state["cat"])
                    state["last_refresh"] = time.time()
                    out = {k: e.state for k, e in state["cat"].entities.items()}
                self._send(200, out)
            else:
                self._send(404, {"error": "not found"})

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                req = json.loads(self.rfile.read(n) or b"{}")
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid json"})
            if self.path == "/reload" and ha is not None:
                changed = rebuild(force=bool(req.get("force")))
                return self._send(200, {"ok": True, "changed": changed, "capabilities": len(state["cat"].capabilities),
                                        "entities": len(state["cat"].entities)})
            with lock:
                if self.path != "/decide":
                    return self._send(404, {"error": "not found"})
                name = req.get("model") or default
                if name not in engines:
                    name = default  # the add-on loads only the chosen model; an old client asking "6L" gets it
                eng = engines[name]
                if req.get("home"):  # translated test home: decisions only
                    teng = test_engine(name, str(req["home"]))
                    if teng is None:
                        return self._send(400, {"error": f"unknown test home {req['home']}"})
                    d = teng.decide(req.get("text", ""), req.get("context_area"), session=req.get("session"),
                                    lang=req.get("lang"))
                    return self._send(200, {"decision": d.to_dict(), "model": name, "home": req["home"]})
                if ha is not None and time.time() - state["last_refresh"] > refresh_seconds:
                    ha.refresh_states(state["cat"])
                    state["last_refresh"] = time.time()
                lang_ = req.get("lang", lang)
                if is_history_question(req.get("text", "")):  # "cosa hai fatto?"
                    text_ = history_reply(list(done), state["cat"], lang_, time.time())
                    return self._send(200, {"decision": {"policy": "EXECUTE", "reason": "history", "parts": []},
                                            "reply": text_, "model": name})
                # session = the voice satellite (or any id): lets "la seconda" / "sì" answer the previous question
                session = req.get("session") or req.get("context_area") or "default"
                d = eng.decide(req.get("text", ""), req.get("context_area"), session=str(session),
                               lang=req.get("lang") or lang, device=req.get("device_id"))
                cat_ = eng.catalog or state["cat"]  # with the virtual entities the model was trained with
                spec_ = cat_.actions.get(d.action or "")
                if ha is not None and d.policy == "EXECUTE" and spec_ is not None and spec_.kind == "read" \
                        and time.time() - state["last_refresh"] > 1.0:
                    ha.refresh_states(state["cat"])  # a question about states gets the states of this moment
                    state["last_refresh"] = time.time()
                if ha is not None and d.policy == "EXECUTE" and d.action == "weather.get_state" and d.entities:
                    # the forecast is not part of the entity state: ask Home Assistant just for this answer
                    try:
                        ent = state["cat"].entities[d.entities[0]]
                        ent.attributes = dict(ent.attributes or {}, forecast=ha.weather_forecast(d.entities[0]))
                    except Exception as e:  # noqa: BLE001  (old HA, weather integration without daily forecast)
                        print(f"weather forecast not available: {e}", flush=True)
                out = {"decision": d.to_dict(), "reply": reply(d, cat_, req.get("lang", lang)), "model": name}
                from .core.assist import intent_for
                it_ = intent_for(d, req.get("lang", lang))
                if it_:  # timers, alarms, announcements: run by the integration on the satellite that heard it
                    out["intent"] = it_
                if d.reason == "history":  # "wat heb je gedaan?" recognised by the model (languages without regex)
                    out["reply"] = history_reply(list(done), state["cat"], lang_, time.time())
                    out["decision"]["policy"] = "EXECUTE"
                if ha is not None and req.get("execute"):
                    try:
                        out["execution"] = ha.execute(d, cat_, dry_run=False)
                        state["last_refresh"] = 0.0  # the next request reads the new states
                    except Exception as e:  # noqa: BLE001  (HA refused the call, network...)
                        out["execution"] = {"executed": False, "error": str(e)}
                ex = out.get("execution") or {}
                failed = [(d, ex)] if ex.get("error") else \
                    [(pd, pe) for pd, pe in zip(d.parts, ex.get("parts") or []) if (pe or {}).get("error")]
                if failed:  # Home Assistant refused the call: say so, never "Fatto."
                    from .adapters.homeassistant import error_reply
                    fd, fe = failed[0]
                    print(f"execution failed ({fd.capability}): {fe.get('error')}", flush=True)
                    out["reply"] = error_reply(fd, cat_, req.get("lang", lang), str(fe.get("error")))
                    ex = dict(ex, error=fe.get("error"))
                    out["execution"] = ex
                acted = bool(d.parts) or (bool(d.capability) and getattr(spec_, "kind", "") != "read"
                                          and d.action != "assist.timer_status")  # "what did you do?": actions only
                if (d.policy == "EXECUTE" or (d.policy == "CLARIFY" and d.parts)) and acted and not ex.get("error") \
                        and (ex or ha is None):
                    done.append({"t": time.time(), "decision": d})
                rec = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "text": req.get("text", ""),
                       "context_area": req.get("context_area"), "session": session, "policy": d.policy,
                       "reason": d.reason, "capability": d.capability,
                       "parts": [p.capability for p in d.parts], "reply": out["reply"],
                       "executed": bool(ex) and not ex.get("error"), "error": ex.get("error"),
                       "latency_ms": round(d.latency_ms)}
                history.append(rec)
                if history_file:  # option "save_history": kept across restarts, rotated at 2 MB
                    try:
                        hf = Path(history_file)
                        hf.parent.mkdir(parents=True, exist_ok=True)
                        if hf.exists() and hf.stat().st_size > 2_000_000:
                            hf.replace(hf.with_suffix(".old.jsonl"))
                        with hf.open("a", encoding="utf-8") as f:
                            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                    except OSError as e:
                        print(f"history not saved: {e}", flush=True)
            self._send(200, out)

        def log_message(self, fmt_, *args):
            if verbose:
                super().log_message(fmt_, *args)

    srv = ThreadingHTTPServer((host, port), H)
    print(f"EdgeDecision listening on http://{host}:{port}  models={list(engines)} (default {default})  "
          f"capabilities={len(cat.capabilities)}", flush=True)
    srv.serve_forever()


def main():
    _utf8()
    ap = argparse.ArgumentParser(prog="edgedecision")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, catalog=True):
        p.add_argument("--bundle", default="bundle")
        p.add_argument("--threads", type=int, default=None)
        p.add_argument("--lang", default="it")
        if catalog:
            p.add_argument("--catalog", default="data/gold/demo_home.json")
            p.add_argument("--ha-url", dest="ha_url")
            p.add_argument("--token", default=None, help="HA long-lived token (or env HA_TOKEN)")
            p.add_argument("--insecure", action="store_true")
            p.add_argument("--all-entities", dest="all_entities", action="store_true",
                           help="include entities not exposed to Assist")

    p = sub.add_parser("decide")
    common(p)
    p.add_argument("text")
    p.add_argument("--context-area", dest="context_area")
    p.add_argument("--json", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--dry-run", dest="dry_run", action="store_true")
    p.set_defaults(fn=cmd_decide)

    p = sub.add_parser("repl")
    common(p)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--dry-run", dest="dry_run", action="store_true")
    p.set_defaults(fn=cmd_repl)

    p = sub.add_parser("ha-export")
    p.add_argument("--url", required=True)
    p.add_argument("--token", default=None)
    p.add_argument("--out", default="data/my_home.json")
    p.add_argument("--insecure", action="store_true")
    p.add_argument("--all-entities", dest="all_entities", action="store_true")
    p.set_defaults(fn=cmd_ha_export)

    p = sub.add_parser("bench")
    common(p)
    p.add_argument("-n", type=int, default=20)
    p.set_defaults(fn=cmd_bench)

    p = sub.add_parser("serve")
    common(p)
    p.add_argument("--bundles", default=None, help="several models: 6L=bundle6,4L=bundle4 (request field 'model')")
    p.add_argument("--testset", default="data/gold/gold_test.jsonl")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--refresh-seconds", dest="refresh_seconds", type=float, default=2.0)
    p.add_argument("--verbose", action="store_true")
    p.set_defaults(fn=cmd_serve)

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
