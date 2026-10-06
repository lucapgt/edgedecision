# EdgeDecision and EdgeSTT with Docker (experimental)

For **Home Assistant Container** (or Core) users, e.g. Raspberry Pi OS with Docker, who have no add-on store. The
images are the same as the add-ons; only the way they are started changes.

> **Experimental:** this procedure has not been tested on a real installation yet. If you try it, please tell me how
> it went by opening an issue on GitHub.

## Requirements

- Docker with Docker Compose, on the **same computer** as Home Assistant.
- Home Assistant started with `network_mode: host`, as in the official guide (the most common set-up).
- About 2 GB of free RAM: a 4 GB Raspberry Pi 5 is fine.
- A Home Assistant **access token**: your profile → Security → *Long-lived access tokens* → Create.

## 1. Get the repository

```bash
git clone https://github.com/Lucapgt/edgedecision.git
cd edgedecision/docker
cp .env.example .env
nano .env          # paste the token after HA_TOKEN=
```

If Home Assistant runs on another computer or port, remove the `#` from the `HA_URL` and `HA_WS` lines and put its
address there.

## 2. Choose language and options

- `edgedecision/options.json`: `"lang"` is the language of the replies (`en`, `it`, `es`…). The other options are the
  same as the add-on's, described in [DOCS.md](../edgedecision/DOCS.md).
- `edgestt/options.json`: `"language"` is the speech-recognition language. Home Assistant sends the pipeline's
  language anyway.

## 3. Start

```bash
docker compose up -d --build
docker compose logs -f
```

The first time takes a few minutes: the images are built and EdgeSTT downloads the speech model (about 475 MB, only
once, into `edgestt/models`). It is ready when the logs show:

- EdgeSTT: `Listening on tcp://0.0.0.0:10300`
- EdgeDecision: `model 7c loaded…` and `Home Assistant catalog: … entities`

If EdgeDecision keeps saying `Home Assistant not ready`, check the token and the address in `.env`.

## 4. Connect Home Assistant

1. **EdgeSTT**: Settings → Devices & services → Add integration → **Wyoming Protocol** → host `127.0.0.1`, port
   `10300`.
2. **EdgeDecision integration**: through HACS (Custom repositories → `https://github.com/Lucapgt/edgedecision`, type
   Integration) or by copying the repository's `custom_components/edgedecision` folder into Home Assistant's
   `config/custom_components/`. Restart Home Assistant, then Add integration → **EdgeDecision**. The address is
   `http://127.0.0.1:8765` (usually found automatically).
3. **Assist**: Settings → Voice assistants → your assistant → Speech-to-text **EdgeSTT**, Conversation agent
   **EdgeDecision**.

## Updating

```bash
cd edgedecision
git pull
cd docker
docker compose up -d --build
```

## Notes

- Ports 8765 and 10300 are open only on this computer (`127.0.0.1`), not to the rest of your network.
- To stop everything: `docker compose down`. The downloaded speech model stays in `edgestt/models`.
