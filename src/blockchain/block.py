"""
Block structure for IoT-ShardChain blockchain.

Blocks contain transactions, state commitments, and consensus signatures.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import cbor2

from .crypto import hash, verify
from .transaction import Transaction


def merkle_root(transactions: List[Transaction]) -> bytes:
    """
    Compute the Merkle root of a list of transactions.

    For an empty list, returns the zero hash.

    Args:
        transactions: List of transactions

    Returns:
        32-byte hash
    """
    if not transactions:
        return b"\x00" * 32

    # Hash each transaction
    hashes = [tx.hash() for tx in transactions]

    # Build Merkle tree bottom-up
    while len(hashes) > 1:
        if len(hashes) % 2 != 0:
            hashes.append(hashes[-1])  # Duplicate last hash if odd

        new_hashes = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i + 1]
            new_hashes.append(hash(combined))
        hashes = new_hashes

    return hashes[0]


@dataclass
class Block:
    """
    A block in the IoT-ShardChain blockchain.

    Fields:
        height: Block number (genesis = 0)
        timestamp: Unix milliseconds when block was proposed
        parent_hash: Hash of parent block (0 for genesis)
        proposer: Public key of validator who proposed block
        transactions: List of transactions included in block
        merkle_root: Root of transaction Merkle tree
        state_root: Hash of blockchain state after applying block
        signatures: Map of validator public key -> BFT signature (added by consensus)
    """

    height: int
    timestamp: int  # Unix milliseconds
    parent_hash: bytes  # 32 bytes
    proposer: bytes  # 32-byte public key
    transactions: List[Transaction] = field(default_factory=list)
    merkle_root: bytes = field(default_factory=lambda: b"\x00" * 32)
    state_root: bytes = field(default_factory=lambda: b"\x00" * 32)
    signatures: Dict[bytes, bytes] = field(default_factory=dict)  # pubkey -> signature

    def __post_init__(self):
        """Validate block structure and recompute merkle_root if needed."""
        if len(self.parent_hash) != 32:
            raise ValueError("parent_hash must be 32 bytes")
        if len(self.proposer) != 32:
            raise ValueError("proposer must be 32-byte public key")
        if len(self.state_root) != 32:
            raise ValueError("state_root must be 32 bytes")

        # Recompute merkle root if not provided
        if self.merkle_root == b"\x00" * 32:
            self.merkle_root = merkle_root(self.transactions)

    def hash(self) -> bytes:
        """
        Compute the block hash (without signatures).

        The hash is deterministic given the block data.
        Signatures are not included in the hash because they're added by consensus.
        """
        obj = {
            "height": self.height,
            "timestamp": self.timestamp,
            "parent_hash": self.parent_hash,
            "proposer": self.proposer,
            "transactions": [tx.to_cbor(include_signature=True) for tx in self.transactions],
            "merkle_root": self.merkle_root,
            "state_root": self.state_root,
        }
        return hash(cbor2.dumps(obj))

    def add_signature(self, validator_pubkey: bytes, signature: bytes) -> None:
        """
        Add a BFT consensus signature to the block.

        Args:
            validator_pubkey: Validator's public key (32 bytes)
            signature: Ed25519 signature (64 bytes)
        """
        if len(validator_pubkey) != 32:
            raise ValueError("validator_pubkey must be 32 bytes")
        if len(signature) != 64:
            raise ValueError("signature must be 64 bytes")

        self.signatures[validator_pubkey] = signature

    def verify_signature(self, validator_pubkey: bytes) -> bool:
        """
        Verify a signature on this block.

        Args:
            validator_pubkey: Validator's public key

        Returns:
            True if signature is valid
        """
        if validator_pubkey not in self.signatures:
            return False

        signature = self.signatures[validator_pubkey]
        block_hash = self.hash()
        return verify(block_hash, signature, validator_pubkey)

    def is_finalized(self, quorum_size: int) -> bool:
        """
        Check if block has enough signatures to be final.

        For PBFT with N validators, finalized requires 2f+1 signatures where f < N/3.

        Args:
            quorum_size: Minimum number of signatures required (2f+1)

        Returns:
            True if block has >= quorum_size valid signatures
        """
        valid_count = 0
        for pubkey in self.signatures:
            if self.verify_signature(pubkey):
                valid_count += 1

        return valid_count >= quorum_size

    def to_cbor(self) -> bytes:
        """Serialize block to CBOR format."""
        obj = {
            "height": self.height,
            "timestamp": self.timestamp,
            "parent_hash": self.parent_hash,
            "proposer": self.proposer,
            "transactions": [tx.to_cbor(include_signature=True) for tx in self.transactions],
            "merkle_root": self.merkle_root,
            "state_root": self.state_root,
            "signatures": {
                k.hex(): v.hex() for k, v in self.signatures.items()
            },
        }
        return cbor2.dumps(obj)

    @staticmethod
    def from_cbor(cbor_bytes: bytes) -> "Block":
        """Deserialize block from CBOR format."""
        obj = cbor2.loads(cbor_bytes)

        transactions = [
            Transaction.from_cbor(cbor2.dumps(tx_obj))
            if isinstance(tx_obj, dict)
            else Transaction.from_cbor(tx_obj)
            for tx_obj in obj.get("transactions", [])
        ]

        signatures = {}
        for k_hex, v_hex in obj.get("signatures", {}).items():
            signatures[bytes.fromhex(k_hex)] = bytes.fromhex(v_hex)

        block = Block(
            height=obj["height"],
            timestamp=obj["timestamp"],
            parent_hash=obj["parent_hash"],
            proposer=obj["proposer"],
            transactions=transactions,
            merkle_root=obj["merkle_root"],
            state_root=obj["state_root"],
            signatures=signatures,
        )
        return block


def create_genesis_block(
    timestamp: int,
    proposer: bytes,
    state_root: bytes = b"\x00" * 32,
) -> Block:
    """
    Create the genesis (first) block.

    Args:
        timestamp: Unix milliseconds
        proposer: Public key of proposer
        state_root: Initial state root (default zero)

    Returns:
        Genesis block with height=0 and parent_hash=0
    """
    return Block(
        height=0,
        timestamp=timestamp,
        parent_hash=b"\x00" * 32,
        proposer=proposer,
        transactions=[],
        merkle_root=b"\x00" * 32,
        state_root=state_root,
    )
