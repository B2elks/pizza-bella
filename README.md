# Pizza Bella

AI-driven pizzabeställning via telefon med realtids-dashboard och SMS-notifikationer.

**Live demo:** [pizza.skyttberg.nu](https://pizza.skyttberg.nu)

## Hur det fungerar

1. Kunden ringer pizzerian
2. OpenAI Realtime API tar emot beställningen via röstsamtal
3. Ordern dyker upp direkt på dashboarden
4. Pizzabagaren hanterar ordern med knappar (I ugnen → Klar → Upphämtad)
5. Kunden får SMS vid varje steg via 46elks

```
Kund ringer
    ↓
46elks WebSocket → voice_agent.py ↔ OpenAI Realtime API
                        ↓
                   web_app.py (Flask)
                   ├── Dashboard med meny + ordrar
                   ├── Order-API
                   └── SMS via 46elks
```

## Funktioner

- **Röstbeställning** — OpenAI Realtime API med function calling
- **71 pizzor** — 8 kategorier (Standard, Inbakad, Special, Kebab, Kyckling, Fläskfilé, Oxfilé, Mexikansk)
- **Glutenfri botten** — +25 kr extra, agenten frågar automatiskt
- **SMS-flöde** — Tillagas → Klar att hämta → Feedback (1h efter upphämtning)
- **Ändra order** — Kunden får SMS att ringa tillbaka, agenten känner igen numret och visar befintlig order
- **Avbeställning** — Med SMS-notifikation till kunden
- **Live-dashboard** — Pollar var 3:e sekund, filtervy (Att göra / Klara / Alla)

## Tech stack

| Komponent | Teknologi |
|-----------|-----------|
| Röst-AI | OpenAI Realtime API (gpt-4o-realtime-preview) |
| Telefoni | 46elks WebSocket API |
| Backend | Flask + SQLite |
| Frontend | Vanilla HTML/CSS/JS |
| SMS | 46elks SMS API |

## Setup

```bash
# Klona och installera
git clone https://github.com/B2elks/pizza-bella.git
cd pizza-bella
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Konfigurera
cp .env.example .env
# Fyll i dina API-nycklar i .env

# Starta
python web_app.py 8096 &    # Dashboard på port 8096
python voice_agent.py 8095   # Voice agent på port 8095
```

## 46elks-konfiguration

1. Skaffa ett telefonnummer och ett WebSocket-nummer på [46elks.com](https://46elks.com)
2. Peka WebSocket-numrets `ws_url` mot din server: `ws://din-server:8095`
3. Sätt telefonnumrets `voice_start` till `{"connect":"+46007000XX"}` (ditt WS-nummer)

> **OBS:** Använd `--data-urlencode` vid curl mot 46elks API så att `+` inte blir mellanslag.

## Licens

MIT
