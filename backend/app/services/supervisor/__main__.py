"""Entry point: python -m backend.app.services.supervisor"""

import argparse
import asyncio
import logging

from .config import load_config
from .runner import SupervisorRunner


def main() -> None:
    parser = argparse.ArgumentParser(description="agent7 supervisor — rule-based approval agent")
    parser.add_argument("--config", default="supervisor.yaml", help="Path to supervisor YAML config")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    config = load_config(args.config)
    runner = SupervisorRunner(config)
    asyncio.run(runner.start())


if __name__ == "__main__":
    main()
