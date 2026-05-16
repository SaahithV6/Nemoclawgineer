# Nemoclaw build prompt

You are implementing **nemoclaw** in repo `Nemoclawgineer` for Ubuntu 24.04 on NVIDIA Brev (64 CPU, 512 GB RAM) alongside OpenClaw + `nvidia/nemotron-3-super-120b-a12b`.

## Constraints

- Open source CAE only: FreeCAD (headless), Gmsh, CalculiX (`ccx`), OpenFOAM.
- Do NOT implement OnShape upload; stub only.
- Discord is the primary external UI; OpenClaw via MCP + skill.
- User handles `launch-openclaw` / `configure.sh`; you implement `setup.sh` merging MCP config into `~/.openclaw/openclaw.json`.
- **Credit budget:** default `max_passes=3`, `parallel_candidates=4`, stop when relative objective gain < 2% for 2 consecutive passes.
- Parametric optimization only (no topology opt / LEAP71) for hackathon.

## Architecture

1. `nemoclaw-api` (FastAPI) owns jobs under `~/.local/state/nemoclaw/jobs/<id>/`.
2. `nemoclaw/discord_bot.py` calls API.
3. `nemoclaw/mcp_server.py` exposes MCP tools to OpenClaw.
4. `orchestrator.py` calls OpenClaw `POST /v1/chat/completions` once to produce validated `JobSpec` JSON, then runs flows without LLM.
5. `runner.py` executes YAML flows in `flows/templates/`.
6. `optimizer.py` wraps flows in pass loop with convergence checks.
7. `report.py` writes `REPORT.md` + exports final STL.

## JobSpec schema (Pydantic)

- `mode`: optimize | analyze | generate | collab
- `discipline`: fea | cfd
- `objectives`, `constraints`, `loads`, `fluid`, `design_params`
- `input_stl`, `mesh_size`, `max_passes`, `flow_template`

## MCP tools

- `nemoclaw_submit_job(spec_json)` → job_id
- `nemoclaw_job_status(job_id)`
- `nemoclaw_fetch_artifact(job_id, name)`

## Deliverables per job

- `result.stl`, `REPORT.md`, `metrics.json`, `flow.snapshot.json`

Implement in order: setup.sh + doctor → models + job store → runner + FEA template → optimizer → API → MCP → Discord → CFD template → README demo commands.
