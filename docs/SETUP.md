# OpenClaw Engineering + OpenClaw setup (Brev)

## Architecture (what connects to what)

```text
You ──DM──► OpenClaw Discord channel (one bot token)
              │
              ▼ Nemotron + openclaw-engineering skill/MCP
         openclaw-engineering-api (CAD/FEA/CFD on this machine)
              │
              ├── OpenFOAM (CFD solver)
              ├── CalculiX (FEA)
              ├── Gmsh, Build123d, FreeCAD AppImage
              └── OnShape API (import/export STL) ← needs API keys
              │
              ▼ job complete
         OpenClaw hook → agent emails via Gmail + replies in Discord DM
```

**You do NOT run a separate `openclaw-engineering-discord` bot** for the demo. Discord and Gmail are **OpenClaw channels**, configured once on the gateway.

| Integration | Who handles it | Keys needed |
|-------------|----------------|-------------|
| Discord DM | OpenClaw `channels.discord` | `DISCORD_BOT_TOKEN` in `~/.openclaw/.env` |
| Gmail send | OpenClaw Gmail/webhooks | OAuth via `openclaw webhooks gmail setup` (not your Gmail password in openclaw_engineering) |
| Nemotron | OpenClaw + NVIDIA | `OPENCLAW_API_TOKEN` / Build API key (from `configure.sh`) |
| CAE backend | openclaw-engineering | Optional `OPENCLAW_ENGINEERING_DRY_RUN=1` for testing |
| OnShape | openclaw-engineering only | `ONSHAPE_ACCESS_KEY` + `ONSHAPE_SECRET_KEY` |

---

## Security — read this first

- **Never put your Gmail password in this repo or `~/.openclaw-engineering/.env`.** Use OpenClaw’s Gmail setup (OAuth / app password only inside OpenClaw’s own config flow).
- If you pasted a password in chat, **change it now** and enable 2FA on Google.
- OnShape uses **API keys** (not your login password) from https://dev-portal.onshape.com/

---

## 1. OpenClaw on Brev (you)

1. Deploy [OpenClaw on Brev](https://brev.nvidia.com) and run `configure.sh` with your **NVIDIA Build API key**.
2. Confirm the web UI chat works.

---

## 2. Install openclaw_engineering

```bash
git clone https://github.com/SaahithV6/OpenClaw Engineeringgineer.git
cd OpenClaw Engineeringgineer
chmod +x setup.sh
./setup.sh
```

This installs CAE tools, FreeCAD **AppImage**, Python venv, and registers the **openclaw-engineering MCP** server + skill. It does **not** start a second Discord bot by default.

---

## 3. Discord (private DM via OpenClaw)

### Create the bot (once)

1. https://discord.com/developers/applications → **New Application** (e.g. `OpenClaw`).
2. **Bot** → enable **Message Content Intent** → **Reset Token** → copy token.
3. OAuth2 → URL Generator → `bot` + `applications.commands` → invite to your private server.
4. Discord app: **Developer Mode** on → copy your **User ID**.
5. Server → Privacy → allow **Direct Messages** from server members.

### Configure OpenClaw (not openclaw_engineering)

```bash
# ~/.openclaw/.env
DISCORD_BOT_TOKEN=your_bot_token_here
```

```bash
cd ~/OpenClaw Engineeringgineer
openclaw config patch --file config/openclaw.discord.patch.json5
openclaw gateway restart   # or restart via Brev / launch script
```

### Pair for DMs

DM your bot once. OpenClaw uses **pairing** by default — approve the pairing in OpenClaw UI/CLI if prompted.

Talk in **DM**: *"Optimize a rear wing for my 914: 200 lbs downforce at 40 mph sea level"* and attach STL when the agent asks.

Official docs: https://docs.openclaw.ai/channels/discord

---

## 4. Gmail (via OpenClaw — not openclaw-engineering SMTP)

On the Brev instance:

```bash
openclaw webhooks gmail setup --account you@gmail.com
openclaw webhooks gmail run
```

Follow the OAuth / `gogcli` prompts. OpenClaw’s agent sends mail when a job finishes (see hooks below).

Help: https://www.getopenclaw.ai/help/email-gmail-integration

Set default recipient in `~/.openclaw_engineering/.env` (optional):

```bash
OPENCLAW_ENGINEERING_NOTIFY_EMAIL=you@gmail.com
```

---

## 5. OpenClaw hooks (job complete → Discord + email)

So openclaw-engineering can tell Nemotron to deliver results:

```bash
# ~/.openclaw/.env
OPENCLAW_HOOK_TOKEN=$(openssl rand -hex 24)
```

```bash
openclaw config patch --file config/openclaw.hooks.patch.json5
openclaw gateway restart
```

When a job completes, openclaw-engineering writes `DELIVERY.json` and POSTs to `/hooks/agent`. The agent attaches `REPORT.md` + `result.stl` via Gmail and confirms in your Discord DM.

---

## 6. OpenClaw Engineering MCP + agent instructions

Already done by `setup.sh`:

- MCP server in `~/.openclaw/openclaw.json`
- Skill `~/.openclaw/skills/openclaw-engineering/SKILL.md`

Optional: add text from [`config/openclaw.openclaw_engineering-agent.md`](../config/openclaw.openclaw_engineering-agent.md) to your agent system prompt.

---

## 7. OnShape API keys

1. Log in at https://dev-portal.onshape.com/ (same Google account as CAD is fine).
2. **Create API key** → copy **Access key** and **Secret key**.
3. Open your document in OnShape → URL contains:
   - `documents/<DOCUMENT_ID>/w/<WORKSPACE_ID>/e/<ELEMENT_ID>`
4. Put in `~/.openclaw_engineering/.env`:

```bash
ONSHAPE_ACCESS_KEY=...
ONSHAPE_SECRET_KEY=...
ONSHAPE_DOCUMENT_ID=...
ONSHAPE_WORKSPACE_ID=...
ONSHAPE_ELEMENT_ID=...
```

OpenClaw Engineering will **export** STL before solve and **upload** `result.stl` after (same filename when configured).

---

## 8. OpenFOAM (CFD solver)

OpenClaw Engineering runs **OpenFOAM** (`simpleFoam`) on meshes from Gmsh — that is the CFD solve.

Install OpenFOAM ESI v2312 on Brev per your license, then:

```bash
which simpleFoam
openclaw-engineering-doctor
```

**Optuna** (optional) only picks wing angles/chord between OpenFOAM runs; it does not replace OpenFOAM. Default is **off**; the pass-loop optimizer runs several OpenFOAM cases in parallel on 64 CPUs.

---

## 9. Verify

```bash
~/.local/share/openclaw_engineering/venv/bin/openclaw-engineering-doctor
OPENCLAW_ENGINEERING_DRY_RUN=1 ~/.local/share/openclaw_engineering/venv/bin/openclaw-engineering-doctor --dry-test
```

---

## 10. Demo script (Porsche 914)

1. **DM OpenClaw** (not a second bot): attach your **914 STL**, e.g.  
   *"Rear wing, NACA style, 200 lbs downforce at 40 mph, sea level — replace my STL and email full spec."*
2. Or **downforce kit**: *"Full kit: splitter, diffuser, louvres, air dam, venturi over windshield."*
3. Answer speed / downforce / elevation if Nemotron asks.
4. Backend: constrained wing/kit CAD → attach → Gmsh → **OpenFOAM** optimization → **10–130 mph sweep** → **CalculiX wing stress** → reinforcement notes.
5. **Email** (`REPORT.md` with all iterations + speed table + FEA zones) + **result.stl** replaces 914 in OnShape when configured.

**Geometry:** wings use **NACA 2412** extrusion only (no random AI blobs). GrabCAD link in report if you want a catalog reference to upload as `reference_stl`.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| OpenClaw 403 | Re-run `configure.sh`, check NVIDIA API key |
| Discord no reply | Pairing, Message Content Intent, `DISCORD_BOT_TOKEN` in `~/.openclaw/.env` |
| No email | `openclaw webhooks gmail run`; do not use SMTP password in openclaw-engineering |
| OnShape export fails | Check document/workspace/element IDs and API keys |
| CFD “fake” metrics | Install OpenFOAM or use `OPENCLAW_ENGINEERING_DRY_RUN=1` for pipeline test only |
