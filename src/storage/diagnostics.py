"""Small developer-facing DATA-001A diagnostic command.

Run ``python -m storage.diagnostics`` with ``src`` on PYTHONPATH. The command is
read-only: it never registers a source library or opens a library database.
"""

from __future__ import annotations

import json

from core.application_services import build_application_services


def main() -> None:
    services = build_application_services()
    try:
        print(json.dumps(services.diagnostics(), indent=2))
    finally:
        services.close()


if __name__ == "__main__":
    main()
