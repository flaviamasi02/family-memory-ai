"""Explicit, non-destructive developer diagnostics for managed metadata stores.

Examples (with ``src`` on ``PYTHONPATH``)::

    python -m storage.diagnostics root
    python -m storage.diagnostics list
    python -m storage.diagnostics register /temporary/test/photos --name Test
    python -m storage.diagnostics open <LibraryID>
    python -m storage.diagnostics backup <LibraryID> /safe/path/library.db
    python -m storage.diagnostics validate <LibraryID> /safe/path/library.db
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from core.application_services import build_application_services


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect DATA-001 managed storage without changing photo folders")
    parser.add_argument("--app-data-root", help="Override application data root (recommended for tests)")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("root", help="show the application data root")
    commands.add_parser("list", help="list explicitly registered libraries")
    register = commands.add_parser("register", help="explicitly register a chosen source root")
    register.add_argument("source_root"); register.add_argument("--name")
    open_command = commands.add_parser("open", help="open a registered library and show health")
    open_command.add_argument("library_id")
    backup = commands.add_parser("backup", help="create a validated online backup")
    backup.add_argument("library_id"); backup.add_argument("destination")
    validate = commands.add_parser("validate", help="validate an existing backup")
    validate.add_argument("library_id"); validate.add_argument("backup_path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    services = build_application_services(args.app_data_root)
    try:
        if not args.command:
            print(json.dumps(services.diagnostics(), indent=2)); return 0
        if args.command == "root":
            payload = {"application_data_root": str(services.paths.root)}
        elif args.command == "list":
            payload = {"libraries": [asdict(r) for r in services.library_registry.list_libraries()]}
        elif args.command == "register":
            payload = {"library": asdict(services.library_registry.register(args.source_root, args.name))}
        else:
            services.metadata_store.open_library(args.library_id)
            if args.command == "open":
                payload = services.metadata_store.health_check()
            elif args.command == "backup":
                payload = asdict(services.metadata_store.backup(args.destination))
            else:
                payload = asdict(services.metadata_store.validate_backup(args.backup_path))
        print(json.dumps(payload, indent=2)); return 0
    finally:
        services.close()


if __name__ == "__main__":
    raise SystemExit(main())
