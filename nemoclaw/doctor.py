from __future__ import annotations

import shutil
import sys

import httpx

from nemoclaw.config import REPO_ROOT, get_settings, load_defaults
from nemoclaw.tools.util import which


def check_bin(name: str, optional: bool = False) -> bool:
    ok = which(name) is not None
    tag = "OK" if ok else ("SKIP" if optional else "MISSING")
    print(f"  [{tag}] {name}")
    return ok or optional


def main():
    print("Nemoclaw doctor")
    print("===============")
    s = get_settings()
    print(f"Data dir: {s.data_dir}")
    print(f"API: {s.api_base}")
    print(f"Dry run: {s.nemoclaw_dry_run}")
    print(f"Repo: {REPO_ROOT}")
    print("\nBinaries:")
    check_bin("gmsh", optional=True)
    check_bin("ccx", optional=True)
    check_bin("freecadcmd", optional=True)
    check_bin("simpleFoam", optional=True)
    print("\nDefaults:")
    print(f"  {load_defaults()}")
    print("\nOpenClaw gateway:")
    try:
        r = httpx.get(s.openclaw_gateway_url.rstrip("/") + "/health", timeout=5.0)
        print(f"  [{r.status_code}] {s.openclaw_gateway_url}")
    except Exception as exc:
        print(f"  [WARN] {exc}")
    print("\nNemoclaw API:")
    try:
        r = httpx.get(f"{s.api_base}/health", timeout=5.0)
        print(f"  [{r.status_code}] {r.json()}")
    except Exception as exc:
        print(f"  [WARN] API not running: {exc}")
    if "--dry-test" in sys.argv:
        import os

        os.environ["NEMCLAW_DRY_RUN"] = "1"
        from nemoclaw.config import get_settings as gs

        gs.cache_clear()
        from nemoclaw.orchestrator import submit_job

        stl = REPO_ROOT / "tests" / "fixtures" / "sample_bracket.stl"
        state = submit_job(
            "minimize mass, stress < 200 MPa, 500 N",
            input_stl=stl if stl.exists() else None,
        )
        import time

        for _ in range(30):
            from nemoclaw.store import load_state

            st = load_state(state.job_id)
            if st and st.status.value in ("completed", "failed", "cancelled"):
                print(f"Dry test job {state.job_id}: {st.status} {st.stop_reason}")
                break
            time.sleep(1)
    print("\nDone.")


if __name__ == "__main__":
    main()
