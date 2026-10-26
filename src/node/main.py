"""Main entry point for IoT-ShardChain validator node."""

import asyncio
import json
import os
import logging
import sys

from fastapi import FastAPI
from uvicorn import Config, Server

from src.node.validator import ValidatorNode
from src.api.routes import create_app

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def parse_validators_config():
    """Parse validator configuration from environment."""
    # Environment variables:
    # VALIDATOR_ID: this validator's ID (0, 1, 2, ...)
    # VALIDATORS_JSON: JSON string with {id: [host, port], ...}
    # Example: {"0": ["validator-0", 8001], "1": ["validator-1", 8002]}

    validator_id = int(os.getenv("VALIDATOR_ID", "0"))

    validators_json = os.getenv("VALIDATORS_JSON", "{}")
    try:
        validators_raw = json.loads(validators_json)
        # Convert string keys to integers
        validators = {int(k): tuple(v) for k, v in validators_raw.items()}
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse VALIDATORS_JSON: {e}, using defaults")
        # Default: 3-node local testnet
        validators = {
            0: ("validator-0", 8001),
            1: ("validator-1", 8002),
            2: ("validator-2", 8003),
        }

    return validator_id, validators


async def main():
    """Start a validator node with consensus and API server."""
    # Configuration from environment
    validator_id, validators = parse_validators_config()
    db_path = os.getenv("DB_PATH", f"/tmp/blockchain-{validator_id}")
    bind_host = os.getenv("BIND_HOST", "0.0.0.0")
    bind_port = int(os.getenv("BIND_PORT", 8000 + validator_id))

    logger.info(f"Starting validator {validator_id}")
    logger.info(f"Database path: {db_path}")
    logger.info(f"Listening on {bind_host}:{bind_port}")
    logger.info(f"Validators: {validators}")

    # Create validator node
    validator_node = ValidatorNode(
        validator_id=validator_id,
        validators=validators,
        db_path=db_path,
        bind_host=bind_host,
        bind_port=bind_port,
    )

    # Create FastAPI app with blockchain reference
    app = create_app(validator_node.blockchain)

    # Create Uvicorn server
    config = Config(
        app=app,
        host=bind_host,
        port=8000 + validator_id + 1000,  # API port offset to avoid conflicts
        log_level="info",
    )
    server = Server(config)

    # Start validator node and API server concurrently
    try:
        await validator_node.start()
        logger.info(f"Validator {validator_id} consensus engine started")

        # Run API server in background
        api_task = asyncio.create_task(server.serve())
        logger.info(f"API server listening on {bind_host}:{config.port}")

        # Keep running until interrupted
        await api_task
    except KeyboardInterrupt:
        logger.info("Shutting down validator node...")
        await validator_node.shutdown()
        await server.shutdown()
        logger.info("Validator node stopped")


def main_sync():
    """Synchronous entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted")
        sys.exit(0)


if __name__ == "__main__":
    main_sync()
