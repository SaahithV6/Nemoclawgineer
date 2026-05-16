# OpenClaw Engineering (Brev executor)

**OpenClaw** is the product you use (Discord DM, Gmail, Nemotron). This repo is the **CAE executor** it calls via MCP — not a separate platform.

```text
You ──DM──► OpenClaw (Discord + Nemotron on Brev)
              │
              ▼  MCP: openclaw_engineering_*
         Executor (this repo): Build123d → Gmsh → OpenFOAM / CalculiX
              │
              ▼  hook + Gmail skill
         Email REPORT.md + result.stl
```

## What you configure

| Where | What |
|-------|------|
| OpenClaw (`~/.openclaw/.env`) | NVIDIA, `DISCORD_BOT_TOKEN`, Gmail, `OPENCLAW_HOOK_TOKEN` |
| Executor (`~/.openclaw-engineering/.env`) | OnShape API keys only |
| OpenClaw skill | `skills/openclaw-engineering/SKILL.md` — **agent infers every demo** |

## Install on Brev

```bash
./setup.sh
openclaw config patch --file config/openclaw.discord.patch.json5
openclaw config patch --file config/openclaw.hooks.patch.json5
```

Docs: **[docs/ORCHESTRATION_FLOW.md](docs/ORCHESTRATION_FLOW.md)** (full flow) · [docs/SETUP.md](docs/SETUP.md) · [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

## CLI (testing only)

```bash
openclaw-engineering-doctor
NEMCLAW_DRY_RUN=1  # legacy env alias still works as OPENCLAW_ENGINEERING_DRY_RUN
```

OpenClaw demos should **not** use the CLI; the agent submits JobSpec JSON via MCP.
