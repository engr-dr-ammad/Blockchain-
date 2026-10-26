"""REST API routes for IoT-ShardChain."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import json

from src.blockchain.chain import Blockchain


class StatusResponse(BaseModel):
    """Node status response."""
    node_id: str
    height: int
    latest_block_hash: str
    mempool_size: int
    status: str = "ok"


def create_app(blockchain: Blockchain) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(title="IoT-ShardChain Node API", version="0.1.0")

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok"}

    @app.get("/api/v1/status", response_model=StatusResponse)
    async def get_status():
        """Get node and chain status."""
        tip = blockchain.get_latest_block()
        latest_hash = tip.hash().hex() if tip else "0000"

        return StatusResponse(
            node_id="node-1",
            height=blockchain.get_height(),
            latest_block_hash=latest_hash,
            mempool_size=blockchain.mempool.size(),
        )

    @app.get("/api/v1/blocks")
    async def list_blocks(limit: int = 10, offset: int = 0):
        """List blocks with pagination."""
        height = blockchain.get_height()
        start = max(0, height - offset - limit + 1)
        end = height - offset

        if start > height:
            return {"blocks": [], "total": height + 1}

        blocks = []
        for h in range(start, end + 1):
            block = blockchain.get_block(h)
            if block:
                blocks.append({
                    "height": block.height,
                    "hash": block.hash().hex(),
                    "timestamp": block.timestamp,
                    "transactions": len(block.transactions),
                })

        return {
            "blocks": blocks,
            "total": height + 1,
            "limit": limit,
            "offset": offset,
        }

    @app.get("/api/v1/blocks/{height}")
    async def get_block(height: int):
        """Get a specific block by height."""
        block = blockchain.get_block(height)
        if not block:
            raise HTTPException(status_code=404, detail="Block not found")

        return {
            "height": block.height,
            "hash": block.hash().hex(),
            "parent_hash": block.parent_hash.hex(),
            "timestamp": block.timestamp,
            "proposer": block.proposer.hex(),
            "transactions": len(block.transactions),
            "merkle_root": block.merkle_root.hex(),
            "state_root": block.state_root.hex(),
        }

    return app
