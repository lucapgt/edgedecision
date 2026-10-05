"""Entry point of the Home Assistant add-on (see ha-addon/edgedecision).

Reads /data/options.json (written by the Supervisor from the add-on configuration page):
  mode        demo           -> built-in test home (41 devices), nothing in your house is touched
              homeassistant  -> your Home Assistant entities (exposed to Assist), via the Supervisor API
  model       6L | 7b        -> the model in /app/bundles/<model> (6L: round 6, the default; 7b: round 7b, with
                                 timers, alarms, whole house, second-home devices); only that one is loaded
  threads     CPU threads for ONNX Runtime (Raspberry Pi 5: 4)
  lang        language of the spoken replies
  expose_all  also use entities not exposed to Assist
  allow_off_all  "spegni tutto" / "turn everything off" may switch off the whole house (default: off)
  save_history   write every decision to /share/edgedecision/history.jsonl (default: off)

In homeassistant mode new / renamed / moved devices are picked up automatically within a minute.

At start-up it prints a short benchmark of every model in the add-on log.
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
from pathlib import Path

from .cli import make_engine, run_server
from .core.types import Catalog

APP = Path(os.environ.get("EDGE_APP", "/app"))


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def bench(name, eng, n=15):
    texts = ["accendi la luce del soggiorno", "turn off the kitchen lights", "sube la persiana del salón al 50%",
             "che temperatura c'è in camera?", "raccontami una barzelletta", "abbassa un po' la luce",
             "set the thermostat to 21 degrees", "apaga todas las luces"]
    for t in texts[:3]:
        eng.decide(t)
    lat = []
    for _ in range(n):
        for t in texts:
            lat.append(eng.decide(t).latency_ms)
    lat.sort()
    log(f"benchmark {name}: {len(lat)} decisions  p50={statistics.median(lat):.0f} ms  "
        f"p95={lat[int(len(lat) * .95) - 1]:.0f} ms  max={lat[-1]:.0f} ms")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    opt_file = Path(os.environ.get("EDGE_OPTIONS", "/data/options.json"))
    opts = json.loads(opt_file.read_text()) if opt_file.exists() else {}
    mode = opts.get("mode", "demo")
    default = opts.get("model", "6L")
    threads = int(opts.get("threads", 4))
    lang = opts.get("lang", "it")

    # only the chosen model is loaded (memory on the Raspberry Pi); "load_all" loads every bundle found
    found = sorted(p.name for p in (APP / "bundles").iterdir() if (p / "model.int8.onnx").exists()) \
        if (APP / "bundles").exists() else []
    order = [default] + ([m for m in found if m != default] if opts.get("load_all") else [])
    if not (APP / "bundles" / default / "model.int8.onnx").exists() and found:
        log(f"model {default} not found, using {found[0]}")
        order = [found[0]]
    engines = {}
    for m in order:
        b = APP / "bundles" / m
        if (b / "model.int8.onnx").exists():
            t0 = time.time()
            engines[m] = make_engine(str(b), threads)
            log(f"model {m} loaded from {b} in {time.time() - t0:.1f} s")
    if not engines:
        log("no model found in /app/bundles")
        sys.exit(1)

    ha = None
    if mode == "homeassistant":
        from .adapters.homeassistant import HomeAssistant

        token = os.environ.get("SUPERVISOR_TOKEN", "")
        url = os.environ.get("EDGE_HA_URL", "http://supervisor/core")
        ws = os.environ.get("EDGE_HA_WS", "ws://supervisor/core/websocket")
        token = os.environ.get("EDGE_HA_TOKEN", token)
        ha = HomeAssistant(url, token, ws_url=ws)
        ha.allow_off_all = bool(opts.get("allow_off_all", False))  # "spegni tutto" (off by default)
        for attempt in range(1000):  # Home Assistant may still be starting
            try:
                cat = ha.build_catalog(only_exposed=not opts.get("expose_all", False))
                break
            except Exception as e:  # noqa: BLE001
                log(f"Home Assistant not ready ({e.__class__.__name__}: {e}); retrying in 10 s")
                time.sleep(10)
        log(f"Home Assistant catalog: {len(cat.areas)} areas, {len(cat.entities)} entities, "
            f"{len(cat.capabilities)} capabilities")
    else:
        cat = Catalog.load(APP / "data" / "demo_home.json")
        log(f"DEMO mode: built-in test home, {len(cat.entities)} devices, {len(cat.capabilities)} capabilities "
            "(nothing in your house is controlled)")

    for name, eng in engines.items():
        t0 = time.time()
        eng.set_catalog(cat)
        log(f"{name}: catalog prepared in {time.time() - t0:.1f} s")
        bench(name, eng)
    run_server(engines, cat, ha, "0.0.0.0", 8765, lang, 2.0, opts.get("expose_all", False),
               testset=str(APP / "data" / ("casa_prova_test.jsonl" if ha else "gold_test.jsonl")),
               history_file="/share/edgedecision/history.jsonl" if opts.get("save_history") else None)


if __name__ == "__main__":
    main()
