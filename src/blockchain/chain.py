"""
Main blockchain class for IoT-ShardChain.

Manages the immutable ledger, transaction processing, and state.
"""

import time
from typing import List, Optional, Tuple

from .block import Block, create_genesis_block
from .crypto import hash
from .mempool import Mempool
from .storage import BlockStore, StateStore
from .transaction import Transaction


class Blockchain:
    """
    Main blockchain class managing blocks, transactions, and state.

    Maintains:
    - Ordered block list (persisted in RocksDB)
    - Pending transaction pool (mempool)
    - Blockchain state (accounts, sensors, etc.)
    """

    def __init__(self, db_path: str, genesis_timestamp: Optional[int] = None):
        """
        Initialize blockchain.

        Args:
            db_path: Path to RocksDB databases
            genesis_timestamp: Timestamp for genesis block (default: now)
        """
        self.block_store = BlockStore(f"{db_path}/blocks")
        self.state_store = StateStore(f"{db_path}/state")
        self.mempool = Mempool()

        # Create genesis block if this is a fresh chain
        if self.block_store.get_latest_height() < 0:
            genesis_ts = genesis_timestamp or int(time.time() * 1000)
            genesis = create_genesis_block(
                timestamp=genesis_ts,
                proposer=b"\x00" * 32,  # Placeholder
            )
            self.block_store.put_block(genesis)

    def get_block(self, height: int) -> Optional[Block]:
        """Get a block by height."""
        return self.block_store.get_block(height)

    def get_latest_block(self) -> Optional[Block]:
        """Get the latest (tip) block."""
        return self.block_store.get_latest_block()

    def get_height(self) -> int:
        """Get the current chain height (latest block height)."""
        return self.block_store.get_latest_height()

    def append_block(self, block: Block) -> bool:
        """
        Append a new block to the chain.

        Validates that:
        - Block height is exactly tip + 1
        - Parent hash matches current tip
        - All transactions are valid

        Args:
            block: Block to append

        Returns:
            True if block was appended, False if validation failed
        """
        tip = self.get_latest_block()

        # Validate height
        if tip is None:
            # Should not happen (genesis always exists)
            return False

        if block.height != tip.height + 1:
            return False

        # Validate parent hash
        if block.parent_hash != tip.hash():
            return False

        # Validate all transactions are valid
        for tx in block.transactions:
            if not tx.is_valid():
                return False

        try:
            self.block_store.put_block(block)
            return True
        except Exception:
            return False

    def submit_transaction(self, tx: Transaction) -> bool:
        """
        Submit a transaction to the mempool.

        Args:
            tx: Transaction to submit

        Returns:
            True if accepted, False if duplicate or invalid
        """
        try:
            self.mempool.add(tx)
            return True
        except ValueError:
            return False

    def get_pending_transactions(self, max_count: int = 1000) -> List[Transaction]:
        """
        Get pending transactions from mempool.

        Args:
            max_count: Maximum number to return

        Returns:
            List of pending transactions
        """
        return self.mempool.get_top(max_count)

    def remove_transactions_from_mempool(self, block: Block) -> None:
        """
        Remove transactions included in a block from the mempool.

        Args:
            block: Block whose transactions were included
        """
        for tx in block.transactions:
            self.mempool.remove(tx)

    def get_state(self, key: str) -> Optional[bytes]:
        """
        Retrieve a value from blockchain state.

        Args:
            key: State key

        Returns:
            State value if found, None otherwise
        """
        return self.state_store.get(key)

    def set_state(self, key: str, value: bytes) -> None:
        """
        Set a value in blockchain state.

        Args:
            key: State key
            value: State value
        """
        self.state_store.put(key, value)

    def get_all_state(self) -> dict:
        """Get all blockchain state."""
        return self.state_store.get_all()

    def verify_chain(self) -> Tuple[bool, str]:
        """
        Verify blockchain integrity.

        Checks:
        - All blocks present from height 0 to tip
        - Parent hashes are correct
        - All block hashes are valid

        Returns:
            Tuple of (is_valid, error_message)
        """
        tip_height = self.get_height()

        for height in range(0, tip_height + 1):
            block = self.get_block(height)

            if block is None:
                return False, f"Missing block at height {height}"

            if block.height != height:
                return False, f"Block height mismatch at {height}"

            if height > 0:
                parent = self.get_block(height - 1)
                if parent is None:
                    return False, f"Missing parent block at height {height - 1}"

                if block.parent_hash != parent.hash():
                    return False, f"Invalid parent hash at height {height}"

        return True, "Chain is valid"

    def close(self) -> None:
        """Close database connections."""
        self.block_store.close()
        self.state_store.close()


def create_test_blockchain(db_path: str) -> Blockchain:
    """
    Create a fresh blockchain for testing.

    Args:
        db_path: Path for test database

    Returns:
        New Blockchain instance
    """
    return Blockchain(db_path)
