"""Main entry point for IoT-ShardChain node."""

import asyncio
import os
import logging

from fastapi import FastAPI
from uvicorn import run

from src.blockchain.chain import Blockchain
from src.api.routes import create_app

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Start a blockchain node."""
    # Configuration from environment
    node_id = os.getenv("NODE_ID", "node-1")
    node_port = int(os.getenv("NODE_PORT", 8001))
    db_path = os.getenv("DB_PATH", "/tmp/blockchain")

    logger.info(f"Starting node {node_id} on port {node_port}")
    logger.info(f"Database path: {db_path}")

    # Initialize blockchain
    blockchain = Blockchain(db_path)
    logger.info(f"Blockchain initialized. Height: {blockchain.get_height()}")

    # Create FastAPI app
    app = create_app(blockchain)

    # Run server
    run(
        app,
        host="0.0.0.0",
        port=node_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
