# OpenClaw Engineering (Brev executor)

**OpenClaw** is the product you use (Discord DM, Gmail, Nemotron). This repo is the **CAE executor** it calls via MCP — not a separate platform.

```text
You ──DM──► OpenClaw (Discord + Nemotron on Brev)
              │
              ▼  MCP: openclaw_engineering_*
         Executor (this repo): dynamic sculpt engine → Gmsh → OpenFOAM / CalculiX
              │
              ▼  hook + Gmail skill
         Email REPORT.md + result.stl
```

## What you configure

| Where | What |
|-------|------|
| OpenClaw (`~/.openclaw/.env`) | NVIDIA, `DISCORD_BOT_TOKEN`, Gmail, `OPENCLAW_HOOK_TOKEN` |
| Executor (`~/.openclaw-engineering/.env`) | OnShape API keys only |
| OpenClaw skill | `skills/openclaw-engineering/SKILL.md` — **proactive Discord Q&A + geometry_spec** |

## Install on Brev

```bash
./setup.sh
openclaw config patch --file config/openclaw.discord.patch.json5
openclaw config patch --file config/openclaw.hooks.patch.json5
```

**Start here:** **[docs/OPENCLAW_START.md](docs/OPENCLAW_START.md)** (Brev + Discord + Gmail + OnShape + autonomous agent)

Docs: [ORCHESTRATION_FLOW.md](docs/ORCHESTRATION_FLOW.md) · [SCULPT_ENGINE.md](docs/SCULPT_ENGINE.md) · [SETUP.md](docs/SETUP.md)

## CLI (testing only)

```bash
openclaw-engineering-doctor
OPENCLAW_ENGINEERING_DRY_RUN=1
```

OpenClaw demos should **not** use the CLI; the agent submits JobSpec JSON via MCP.
