# Nemoclaw

Engineering orchestrator for **CAD → mesh → FEA/CFD** on NVIDIA Brev, integrated with **OpenClaw** (Nemotron) and **Discord**.

## Features

- **Modes:** optimize, analyze, generate, collab (session-aware)
- **Tools:** FreeCAD (headless), Gmsh, CalculiX, OpenFOAM
- **Credit-aware loops:** max 3 passes, parallel candidates, stop when gain &lt; 2%
- **Interfaces:** Discord bot, OpenClaw MCP tools, REST API, CLI

## Quick start (Brev)

1. Deploy [OpenClaw on Brev](https://github.com/liveaverage/launch-openclaw) and complete `configure.sh` with your NVIDIA API key.
2. Clone this repo on the instance and run:

```bash
chmod +x setup.sh
./setup.sh
```

3. Edit `~/.nemoclaw/.env` — set `DISCORD_BOT_TOKEN` if using Discord.
4. Health check:

```bash
~/.local/share/nemoclaw/venv/bin/nemoclaw-doctor
NEMCLAW_DRY_RUN=1 ~/.local/share/nemoclaw/venv/bin/nemoclaw-doctor --dry-test
```

5. Local demo (no CAE binaries required):

```bash
./scripts/demo_local.sh
```

## Discord

- `/job <description>` — attach STL optional
- `/status <job_id>`
- `/stop <job_id>`
- `/limits`
- `!nemoclaw <description>` with optional attachment

## OpenClaw

`setup.sh` registers the **nemoclaw** MCP server and installs `skills/nemoclaw/SKILL.md`.

Example chat: *"Submit FEA job: minimize mass, stress under 200 MPa, 500 N load"* → use `nemoclaw_submit_job` with JobSpec JSON.

## API

- `GET /health`
- `POST /jobs` (multipart: `user_request`, optional `file`)
- `POST /jobs/json`
- `GET /jobs/{id}`
- `GET /jobs/{id}/artifacts/{name}`

Default: `http://127.0.0.1:8765`

## CLI

```bash
nemoclaw run "Minimize mass, stress < 200 MPa" --stl part.stl --wait
```

## Configuration

- `config/nemoclaw.defaults.yaml` — passes, convergence, mesh, thread counts
- `~/.nemoclaw/.env` — tokens and API host/port

## Hackathon demo flow

1. OpenClaw: submit job via MCP → show job id.
2. Discord: upload `tests/fixtures/sample_bracket.stl` + optimization request.
3. Open `REPORT.md` — pass table and stop reason `converged` or `max_passes`.
4. Download `result.stl`.

## License

See [LICENSE](LICENSE).
