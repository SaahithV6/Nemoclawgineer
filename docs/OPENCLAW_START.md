# OpenClaw + OpenClaw Engineering — start guide (Brev)

**You:** Discord bot token, OnShape API keys, one Gmail OAuth flow.  
**Brev:** OpenClaw (Nemotron + NVIDIA key from launchable), this executor (CAD, mesh, CFD, FEA).  
**Autonomous:** Agent runs clarification → sculpt → parallel physics → delivery without you touching the CLI.

---

## What runs where

```text
You (Discord DM) ──► OpenClaw on Brev (Nemotron 120B, auto NVIDIA API key from launchable)
                         │
                         ├── MCP: openclaw_engineering_* (sculpt, jobs, artifacts)
                         │
                         └── Executor (this repo): sculpt engine, feasibility, Gmsh cache
                                    ├── OpenFOAM (CFD)  ─┐ parallel on 64 CPU
                                    ├── CalculiX (FEA)  ─┘
                                    └── hook → Gmail + Discord reply
```

---

## Part A — Brev instance (mostly automatic)

1. Launch **OpenClaw on Brev** from NVIDIA; run **`configure.sh`** when prompted (injects **NVIDIA Build API key** into `~/.openclaw/.env`).
2. SSH in and clone this repo:

```bash
git clone <your-repo-url> ~/openclaw-engineering
cd ~/openclaw-engineering
chmod +x setup.sh
./setup.sh
```

3. Start the executor API:

```bash
# If systemctl --user fails (common over plain SSH):
./scripts/start-api.sh
# or
~/.local/share/openclaw-engineering/venv/bin/openclaw-engineering-api

# Optional: enable user systemd across logins on Brev
sudo loginctl enable-linger ubuntu
# then after re-login:
systemctl --user enable --now openclaw-engineering-api
```

FreeCAD AppImage is **optional**; if the download fails, setup continues (Build123d/sculpt is primary).

4. Smoke test:

```bash
openclaw-engineering-doctor
OPENCLAW_ENGINEERING_DRY_RUN=1 openclaw-engineering-doctor --dry-test
```

---

## Part B — What you must do (one-time)

### 1. Discord (required)

| Step | Action |
|------|--------|
| 1 | [Discord Developer Portal](https://discord.com/developers/applications) → New Application |
| 2 | **Bot** → enable **Message Content Intent** → copy **token** |
| 3 | OAuth2 URL Generator → `bot` + `applications.commands` → invite to your server |
| 4 | Enable **Developer Mode** in Discord → copy your **User ID** |
| 5 | Allow **DMs** from server members |

```bash
# On Brev
echo 'DISCORD_BOT_TOKEN=your_token_here' >> ~/.openclaw/.env
cd ~/openclaw-engineering
openclaw config patch --file config/openclaw.discord.patch.json5
openclaw gateway restart
```

DM the bot once; **approve pairing** when OpenClaw asks.

### 2. Gmail (plug and chug)

On Brev:

```bash
openclaw webhooks gmail setup --account you@gmail.com
openclaw webhooks gmail run
```

Follow OAuth in the browser/CLI. No Gmail password in this repo.

Optional default recipient:

```bash
echo 'OPENCLAW_ENGINEERING_NOTIFY_EMAIL=you@gmail.com' >> ~/.openclaw-engineering/.env
```

### 3. Job-complete hook (autonomous delivery)

```bash
echo "OPENCLAW_HOOK_TOKEN=$(openssl rand -hex 24)" >> ~/.openclaw/.env
openclaw config patch --file config/openclaw.hooks.patch.json5
openclaw gateway restart
```

When a job finishes, the executor POSTs to OpenClaw; the agent emails **REPORT.md** + STL and replies in Discord.

### 4. OnShape (optional — pull body / push result)

1. https://dev-portal.onshape.com/ → **Create API key** (access + secret).
2. Open your document; URL contains `documents/DOC/w/WS/e/ELEMENT`.
3. Add to `~/.openclaw-engineering/.env`:

```bash
ONSHAPE_ACCESS_KEY=...
ONSHAPE_SECRET_KEY=...
ONSHAPE_DOCUMENT_ID=...
ONSHAPE_WORKSPACE_ID=...
ONSHAPE_ELEMENT_ID=...
```

Executor exports body STL before solve and uploads `result.stl` after.

---

## Part C — Autonomous agent (OpenClaw)

### Install skill + MCP (done by `setup.sh`)

- Skill: `~/.openclaw/skills/openclaw-engineering/SKILL.md`
- MCP: `openclaw-engineering-mcp` in `~/.openclaw/openclaw.json`

### Agent system prompt snippet

Paste [`config/openclaw-engineering-agent.md`](../config/openclaw-engineering-agent.md) into your OpenClaw agent instructions.

### Autonomous behavior (default)

1. User DMs a request (attach **vehicle STL** for mount-fit wings).
2. Agent calls `openclaw_engineering_list_sculpt_methods` → asks **structured** questions (or executor returns `needs_clarification`).
3. Agent submits `openclaw_engineering_submit_job` with full `geometry_spec` + `deliverable_scope`.
4. Executor:
   - **Feasibility** — clamp span/chord to body mount envelope; high downforce → tune camber/AoA, not absurd size.
   - **Sculpt** — dynamic method (wing / hull / nozzle / SDF / bracket).
   - **Optimize** — parallel candidate OpenFOAM runs (8-wide on 64 CPU).
   - **Post** — speed sweep + **parallel CFD & FEA** + wing stress.
   - **Deliver** — hook → Gmail + Discord.

You do not run job commands manually unless debugging.

---

## Part D — Example Discord messages

**Wing only (mount-aware):**  
> Design a rear wing for my 914. Target 200 lb downforce at 40 mph. **Only the wing file** — attach body STL.

**Hull:**  
> New displacement hull 2.4 m waterline, optimize for low wave drag. Method hull_loft.

**Nozzle:**  
> Rocket nozzle contour for constant-pressure style exit, throat 25 mm, exit 80 mm.

**Bracket:**  
> L bracket 120×80 mm, 10 mm thick, gusseted, max stress 200 MPa, 500 N load.

---

## Part E — Reality / feasibility (built in)

The executor **always**:

1. Reads **body STL** bounds and computes a **mount envelope**.
2. **Clamps** wing span/chord so the part fits the car.
3. For extreme downforce targets, prefers **aero parameter tuning** over scaling planform until it cannot mount.
4. **Rejects** addon meshes that violate the envelope after sculpt.

Documented in `REPORT.md` under **Mount / feasibility**.

---

## Part F — Optional PicoGK (LEAP71 lattice / voxel CAD)

```bash
./scripts/install_picogk.sh
# OPENCLAW_ENGINEERING_PICOGK_ENABLED=1 in ~/.openclaw-engineering/.env
```

Use `sculpt_method: picogk_field` in JobSpec. Details: [PICOGK.md](PICOGK.md).

## Part G — Parallelism on Brev (512 GB / 64 CPU)

| Feature | Config |
|---------|--------|
| Optimization candidates | `parallel_candidates: 8` in `config/openclaw-engineering.defaults.yaml` |
| CFD + FEA together | `run_parallel_physics: true` on JobSpec (default) |
| Mesh reuse | `~/.local/state/openclaw-engineering/mesh_cache/` |
| OpenFOAM / CalculiX threads | `openfoam_procs`, `ccx_threads` in defaults |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Nemotron 403 | Re-run Brev `configure.sh`; check `~/.openclaw/.env` |
| Discord silent | Pairing, Message Content Intent, token in `~/.openclaw/.env` |
| Geometry “does not fit vehicle” | Body STL missing or wrong units (mm); attach correct car model |
| No email | `openclaw webhooks gmail run`; check hook token |
| MCP tools missing | `openclaw gateway restart`; verify `setup.sh` MCP block |

---

## Docs index

| Doc | Contents |
|-----|----------|
| [SETUP.md](SETUP.md) | Detailed install |
| [ORCHESTRATION_FLOW.md](ORCHESTRATION_FLOW.md) | End-to-end flow |
| [SCULPT_ENGINE.md](SCULPT_ENGINE.md) | Dynamic sculpt methods |
| [STANDARDS.md](STANDARDS.md) | JobSpec JSON |
