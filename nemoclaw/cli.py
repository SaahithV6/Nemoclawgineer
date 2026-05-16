from __future__ import annotations

import argparse
import time
from pathlib import Path

from nemoclaw.config import get_settings
from nemoclaw.orchestrator import submit_job
from nemoclaw.store import load_state


def main():
    parser = argparse.ArgumentParser(prog="nemoclaw")
    sub = parser.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="Submit a local job")
    run.add_argument("request", help="User request text")
    run.add_argument("--stl", type=Path, default=None)
    run.add_argument("--wait", action="store_true")

    sub.add_parser("doctor", help="Health checks")

    args = parser.parse_args()
    if args.cmd == "doctor":
        from nemoclaw.doctor import main as doc

        doc()
        return
    if args.cmd == "run":
        state = submit_job(args.request, input_stl=args.stl)
        print(f"Job {state.job_id} submitted -> {get_settings().jobs_dir / state.job_id}")
        if args.wait:
            while True:
                st = load_state(state.job_id)
                if st and st.status.value in ("completed", "failed", "cancelled"):
                    print(f"Finished: {st.status} ({st.stop_reason})")
                    break
                time.sleep(2)
        return
    parser.print_help()


if __name__ == "__main__":
    main()
