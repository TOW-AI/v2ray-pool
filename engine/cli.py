"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from engine import __version__
from engine.core.config import ConfigurationError, load_settings
from engine.core.pipeline import PipelineError, run_pipeline
from engine.core.history import verify_history_archives
from engine.core.state import StateStore
from engine.distribution.quality import validate_data_tree


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v2ray-pool",
        description="Build and validate a V2Ray Pool Intelligence Engine data snapshot.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run the full pipeline and build a data snapshot.")
    run.add_argument("--settings", default="config/settings.yml")
    run.add_argument("--sources", default="config/sources.yml")
    run.add_argument("--data-root", default="data")
    run.add_argument("--output", default="build/data")
    run.add_argument("--offline", action="store_true", help="Do not fetch sources or make TCP tests.")
    run.add_argument("--scheduled", action="store_true", help="Count this run in scheduled uptime data.")
    run.add_argument("--limit", type=int, default=None, help="Limit the number of configs for this run.")

    validate = sub.add_parser("validate-settings", help="Validate YAML settings and policy values.")
    validate.add_argument("--settings", default="config/settings.yml")

    check = sub.add_parser("validate-output", help="Run data output checks.")
    check.add_argument("--settings", default="config/settings.yml")
    check.add_argument("--data-root", default="data")

    audit = sub.add_parser("audit-state", help="Check the current State files.")
    audit.add_argument("--data-root", default="data")

    return parser


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.command == "validate-settings":
            settings = load_settings(args.settings)
            _print_json(
                {
                    "status": "valid",
                    "version": settings["app"]["version"],
                    "source_count": len(settings["collector"].get("sources", [])),
                    "fixed_candidate": settings["intelligence"]["fixed_candidate"],
                    "fixed_verified": settings["intelligence"]["fixed_verified"],
                }
            )
            return 0
        if args.command == "run":
            report = run_pipeline(
                args.settings,
                args.sources,
                args.data_root,
                args.output,
                offline=args.offline,
                scheduled=args.scheduled,
                limit=args.limit,
            )
            _print_json(report)
            return 0 if report.get("quality", {}).get("quality_gate") == "passed" else 2
        if args.command == "validate-output":
            settings = load_settings(args.settings)
            state = StateStore(args.data_root).load()
            report = validate_data_tree(Path(args.data_root), settings, state["configs"])
            _print_json(report)
            return 0
        if args.command == "audit-state":
            state = StateStore(args.data_root).load()
            _print_json(
                {
                    "status": "valid",
                    "configs": len(state["configs"]),
                    "ip_observations": len(state["observations"]),
                    "classification_transitions": len(state["transitions"]),
                    "metrics_records": len(state["metrics"]),
                    "history_archives": verify_history_archives(Path(args.data_root) / "history"),
                }
            )
            return 0
    except (ConfigurationError, PipelineError, ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
