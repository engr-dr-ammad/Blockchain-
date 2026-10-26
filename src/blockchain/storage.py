"""
Persistent block storage.

Uses in-memory storage for Stage 2 (RocksDB integration in Stage 3).
Provides ACID guarantees for blockchain state.
"""

import os
from typing import Dict, Optional

from .block import Block


class BlockStore:
    """
    In-memory block storage for Stage 2 (RocksDB in Stage 3).

    Stores blocks by height with O(1) lookup.
    """

    def __init__(self, path: str):
        """
        Initialize block store.

        Args:
            path: Directory path for database (future RocksDB)
        """
        self.path = path
        os.makedirs(path, exist_ok=True)

        # In-memory storage (Stage 2)
        self.blocks: Dict[int, Block] = {}
        self.hash_to_height: Dict[str, int] = {}
        self.height = -1  # No blocks yet

    def put_block(self, block: Block) -> None:
        """
        Store a block.

        Updates the height pointer to the latest height.

        Args:
            block: Block to store

        Raises:
            ValueError: If block height is not tip+1
        """
        if block.height != self.height + 1:
            raise ValueError(
                f"Block height {block.height} does not follow tip {self.height}"
            )

        # Store block by height
        self.blocks[block.height] = block

        # Update height index (for hash -> height lookup)
        block_hash = block.hash().hex()
        self.hash_to_height[block_hash] = block.height

        # Update height
        self.height = block.height

    def get_block(self, height: int) -> Optional[Block]:
        """
        Retrieve a block by height.

        Args:
            height: Block height

        Returns:
            Block if found, None otherwise
        """
        if height < 0 or height > self.height:
            return None

        return self.blocks.get(height)

    def get_block_by_hash(self, block_hash: bytes) -> Optional[Block]:
        """
        Retrieve a block by hash.

        Args:
            block_hash: Block hash (32 bytes)

        Returns:
            Block if found, None otherwise
        """
        hash_hex = block_hash.hex()
        height = self.hash_to_height.get(hash_hex)

        if height is None:
            return None

        return self.get_block(height)

    def get_latest_block(self) -> Optional[Block]:
        """Get the latest (tip) block."""
        if self.height < 0:
            return None
        return self.get_block(self.height)

    def get_block_range(self, start_height: int, end_height: int) -> Dict[int, Block]:
        """
        Retrieve multiple blocks by height range (inclusive).

        Args:
            start_height: Starting height
            end_height: Ending height (inclusive)

        Returns:
            Dictionary mapping height -> Block
        """
        blocks = {}
        for h in range(start_height, end_height + 1):
            block = self.get_block(h)
            if block:
                blocks[h] = block
        return blocks

    def has_block(self, height: int) -> bool:
        """Check if a block exists at given height."""
        return self.get_block(height) is not None

    def get_latest_height(self) -> int:
        """Get the height of the latest block (-1 if no blocks)."""
        return self.height

    def close(self) -> None:
        """Close the database."""
        pass  # No-op for in-memory storage

    def __del__(self):
        """Cleanup on garbage collection."""
        self.close()


class StateStore:
    """
    In-memory state storage for blockchain state (accounts, sensors, etc).

    Simple key-value store; more sophisticated state (Merkle tree) added later.
    """

    def __init__(self, path: str):
        """Initialize state store."""
        self.path = path
        os.makedirs(path, exist_ok=True)

        # In-memory state
        self.state: Dict[str, bytes] = {}

    def put(self, key: str, value: bytes) -> None:
        """Store a state entry."""
        self.state[key] = value

    def get(self, key: str) -> Optional[bytes]:
        """Retrieve a state entry."""
        return self.state.get(key)

    def delete(self, key: str) -> None:
        """Delete a state entry."""
        self.state.pop(key, None)

    def get_all(self) -> Dict[str, bytes]:
        """Retrieve all state entries."""
        return dict(self.state)

    def close(self) -> None:
        """Close the database."""
        pass  # No-op for in-memory storage

    def __del__(self):
        """Cleanup on garbage collection."""
        self.close()
