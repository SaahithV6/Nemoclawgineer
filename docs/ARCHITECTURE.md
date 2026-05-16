# Architecture

## Two layers, one product: OpenClaw

| Layer | What the user sees |
|-------|-------------------|
| **OpenClaw** | Discord DM, Gmail, Nemotron, skills, MCP, hooks |
| **openclaw-engineering** (this repo) | Silent executor on Brev: mesh, OpenFOAM, CalculiX, reports |

There is no separate user-facing "nemoclaw" platform.

## Who plans the demo?

**The OpenClaw agent** reads `skills/openclaw-engineering/SKILL.md` and submits a full `JobSpec` JSON via MCP. The executor only validates constraints and runs solvers.

## Who talks on Discord?

**OpenClaw's Discord channel** (`DISCORD_BOT_TOKEN` in `~/.openclaw/.env`). Not a second bot from this repo.

## Who sends email?

**OpenClaw Gmail integration** after the executor finishes and triggers `/hooks/agent`.

## Solvers

- OpenFOAM — CFD
- CalculiX — FEA  
- Gmsh, Build123d — mesh/CAD (constrained)
