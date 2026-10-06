# EdgeDecision ed EdgeSTT con Docker (sperimentale)

Per chi usa **Home Assistant Container** (o Core), per esempio su Raspberry Pi OS con Docker, e quindi non ha lo
store degli add-on. Le immagini sono le stesse degli add-on; cambia solo il modo di avviarle.

> **Sperimentale:** questa procedura non è ancora stata provata su un'installazione reale. Se la provi, raccontami
> com'è andata aprendo una segnalazione su GitHub.

## Cosa serve

- Docker con Docker Compose, sullo **stesso computer** di Home Assistant.
- Home Assistant avviato con `network_mode: host`, come nella guida ufficiale (è il caso più comune).
- Circa 2 GB di RAM liberi: un Raspberry Pi 5 da 4 GB va bene.
- Un **token di accesso** di Home Assistant: il tuo profilo → Sicurezza → *Token di accesso a lunga durata* → Crea.

## 1. Scarica il repository

```bash
git clone https://github.com/Lucapgt/edgedecision.git
cd edgedecision/docker
cp .env.example .env
nano .env          # incolla il token dopo HA_TOKEN=
```

Se Home Assistant è su un altro computer o su un'altra porta, togli il `#` dalle righe `HA_URL` e `HA_WS` e metti il
suo indirizzo.

## 2. Scegli lingua e opzioni

- `edgedecision/options.json`: `"lang"` è la lingua delle risposte (`it`, `en`, `es`…). Le altre opzioni sono le
  stesse dell'add-on, descritte in [DOCS.md](../edgedecision/DOCS.md).
- `edgestt/options.json`: `"language"` è la lingua del riconoscimento vocale. Home Assistant manda comunque quella
  della pipeline.

## 3. Avvia

```bash
docker compose up -d --build
docker compose logs -f
```

La prima volta ci vuole qualche minuto: si costruiscono le immagini ed EdgeSTT scarica il modello vocale (circa
475 MB, solo la prima volta, nella cartella `edgestt/models`). È pronto quando nei log compaiono:

- EdgeSTT: `Listening on tcp://0.0.0.0:10300`
- EdgeDecision: `model 7c loaded…` e `Home Assistant catalog: … entities`

Se EdgeDecision ripete `Home Assistant not ready`, controlla il token e l'indirizzo nel file `.env`.

## 4. Collega Home Assistant

1. **EdgeSTT**: Impostazioni → Dispositivi e servizi → Aggiungi integrazione → **Wyoming Protocol** → host
   `127.0.0.1`, porta `10300`.
2. **Integrazione EdgeDecision**: con HACS (Repository personalizzati → `https://github.com/Lucapgt/edgedecision`, tipo
   Integrazione) oppure copiando la cartella `custom_components/edgedecision` del repository in `config/custom_components/`
   di Home Assistant. Riavvia Home Assistant, poi Aggiungi integrazione → **EdgeDecision**. L'indirizzo è
   `http://127.0.0.1:8765` (di solito viene trovato da solo).
3. **Assist**: Impostazioni → Assistenti vocali → il tuo assistente → Riconoscimento vocale **EdgeSTT**, Agente di
   conversazione **EdgeDecision**.

## Aggiornare

```bash
cd edgedecision
git pull
cd docker
docker compose up -d --build
```

## Note

- Le porte 8765 e 10300 sono aperte solo su questo computer (`127.0.0.1`), non sul resto della rete.
- Per fermare tutto: `docker compose down`. Il modello vocale scaricato resta nella cartella `edgestt/models`.
