from __future__ import annotations

import asyncio
import logging
import sys

from src.cli.commands import cli

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    cli()


if __name__ == "__main__":
    main()
