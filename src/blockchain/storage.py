"""
Persistent block storage using RocksDB.

Provides ACID guarantees for blockchain state.
"""

import os
from typing import Dict, Optional

import rocksdb

from .block import Block


class BlockStore:
    """
    Persistent storage for blocks using RocksDB.

    Keys:
        "block:{height}" -> Block CBOR
        "height:{hash}" -> height (for O(1) hash lookup)
        "tip" -> latest block height
    """

    def __init__(self, path: str):
        """
        Initialize block store.

        Args:
            path: Directory path for RocksDB database
        """
        self.path = path
        os.makedirs(path, exist_ok=True)

        opts = rocksdb.Options(create_if_missing=True)
        self.db = rocksdb.DB(path, opts)

        # Try to read current height; default to -1 (no blocks)
        tip_bytes = self.db.get(b"tip")
        self.height = int(tip_bytes.decode()) if tip_bytes else -1

    def put_block(self, block: Block) -> None:
        """
        Store a block.

        Updates the "tip" pointer to the latest height.

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
        key = f"block:{block.height}".encode()
        self.db.put(key, block.to_cbor())

        # Update height index (for hash -> height lookup)
        block_hash = block.hash()
        height_key = f"hash:{block_hash.hex()}".encode()
        self.db.put(height_key, str(block.height).encode())

        # Update tip
        self.db.put(b"tip", str(block.height).encode())
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

        key = f"block:{height}".encode()
        cbor_bytes = self.db.get(key)

        if cbor_bytes is None:
            return None

        try:
            return Block.from_cbor(cbor_bytes)
        except Exception:
            return None

    def get_block_by_hash(self, block_hash: bytes) -> Optional[Block]:
        """
        Retrieve a block by hash.

        Args:
            block_hash: Block hash (32 bytes)

        Returns:
            Block if found, None otherwise
        """
        height_key = f"hash:{block_hash.hex()}".encode()
        height_bytes = self.db.get(height_key)

        if height_bytes is None:
            return None

        try:
            height = int(height_bytes.decode())
            return self.get_block(height)
        except Exception:
            return None

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
        if self.db:
            self.db.close()
            self.db = None

    def __del__(self):
        """Cleanup on garbage collection."""
        self.close()


class StateStore:
    """
    Persistent storage for blockchain state (accounts, sensors, etc).

    Simple key-value store; more sophisticated state (Merkle tree) added later.
    """

    def __init__(self, path: str):
        """Initialize state store."""
        self.path = path
        os.makedirs(path, exist_ok=True)

        opts = rocksdb.Options(create_if_missing=True)
        self.db = rocksdb.DB(path, opts)

    def put(self, key: str, value: bytes) -> None:
        """Store a state entry."""
        self.db.put(key.encode(), value)

    def get(self, key: str) -> Optional[bytes]:
        """Retrieve a state entry."""
        return self.db.get(key.encode())

    def delete(self, key: str) -> None:
        """Delete a state entry."""
        self.db.delete(key.encode())

    def get_all(self) -> Dict[str, bytes]:
        """Retrieve all state entries."""
        result = {}
        it = self.db.iteritems()
        for k, v in it:
            result[k.decode()] = v
        return result

    def close(self) -> None:
        """Close the database."""
        if self.db:
            self.db.close()
            self.db = None

    def __del__(self):
        """Cleanup on garbage collection."""
        self.close()
