"""
Mempool (transaction pool) for IoT-ShardChain.

Maintains pending transactions and prevents duplicates.
"""

from typing import Dict, List, Optional

from .transaction import Transaction


class Mempool:
    """
    Transaction mempool with duplicate prevention.

    Prevents transactions with duplicate (sender, nonce) pairs.
    Evicts oldest transactions when max_size is reached.
    """

    def __init__(self, max_size: int = 10000):
        """
        Initialize mempool.

        Args:
            max_size: Maximum number of transactions to hold
        """
        self.max_size = max_size
        self.transactions: List[Transaction] = []  # Ordered by insertion
        self.nonce_index: Dict[bytes, int] = {}  # sender -> latest nonce seen

    def add(self, tx: Transaction) -> None:
        """
        Add a transaction to the mempool.

        Args:
            tx: Transaction to add

        Raises:
            ValueError: If transaction is invalid or duplicate
        """
        if not tx.is_valid():
            raise ValueError("Invalid transaction signature")

        # Check for duplicate (same sender, same nonce)
        if tx.sender in self.nonce_index and self.nonce_index[tx.sender] >= tx.nonce:
            raise ValueError(
                f"Duplicate nonce {tx.nonce} for sender {tx.sender.hex()}"
            )

        # Add transaction
        self.transactions.append(tx)
        self.nonce_index[tx.sender] = tx.nonce

        # Evict oldest if at capacity
        if len(self.transactions) > self.max_size:
            evicted = self.transactions.pop(0)
            # Note: nonce_index is not updated; we keep highest nonce per sender

    def get_top(self, n: int) -> List[Transaction]:
        """
        Get the top n transactions (oldest first).

        Args:
            n: Number of transactions to retrieve

        Returns:
            List of up to n transactions
        """
        return self.transactions[:n]

    def remove(self, tx: Transaction) -> None:
        """
        Remove a transaction from the mempool (after block inclusion).

        Args:
            tx: Transaction to remove
        """
        try:
            self.transactions.remove(tx)
        except ValueError:
            pass  # Transaction not in mempool

    def remove_by_nonce(self, sender: bytes, nonce: int) -> None:
        """
        Remove transactions up to a given nonce (after block confirmation).

        Args:
            sender: Sender public key
            nonce: Highest nonce to remove (removes all nonce <= this)
        """
        self.transactions = [
            tx for tx in self.transactions
            if not (tx.sender == sender and tx.nonce <= nonce)
        ]

    def clear(self) -> None:
        """Clear all transactions from mempool."""
        self.transactions.clear()
        self.nonce_index.clear()

    def size(self) -> int:
        """Return number of transactions in mempool."""
        return len(self.transactions)

    def __contains__(self, tx: Transaction) -> bool:
        """Check if transaction is in mempool."""
        return tx in self.transactions

    def __len__(self) -> int:
        """Return size of mempool."""
        return len(self.transactions)

    def __repr__(self) -> str:
        return f"Mempool(size={len(self.transactions)}, max_size={self.max_size})"
