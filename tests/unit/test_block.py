"""Unit tests for blocks."""

import time

import pytest

from src.blockchain import crypto
from src.blockchain.block import Block, create_genesis_block, merkle_root
from src.blockchain.transaction import Transaction, TransactionType


class TestMerkleRoot:
    """Test Merkle tree construction."""

    def test_merkle_root_empty_list(self):
        """Merkle root of empty list should be zero hash."""
        root = merkle_root([])
        assert root == b"\x00" * 32

    def test_merkle_root_single_transaction(self):
        """Merkle root of single transaction."""
        priv, pub = crypto.generate_keypair()
        tx = Transaction(
            nonce=0,
            sender=pub,
            operation=TransactionType.SENSOR_SUBMIT,
            data=b"data",
        )
        tx.sign(priv)

        root = merkle_root([tx])
        assert len(root) == 32
        assert root != b"\x00" * 32

    def test_merkle_root_consistent(self):
        """Merkle root should be consistent for same transactions."""
        priv, pub = crypto.generate_keypair()
        txs = []
        for i in range(3):
            tx = Transaction(
                nonce=i,
                sender=pub,
                operation=TransactionType.SENSOR_SUBMIT,
                data=f"data {i}".encode(),
            )
            tx.sign(priv)
            txs.append(tx)

        root1 = merkle_root(txs)
        root2 = merkle_root(txs)

        assert root1 == root2


class TestBlockCreation:
    """Test creating blocks."""

    def test_create_block(self):
        """Create a basic block."""
        proposer = crypto.generate_keypair()[1]

        block = Block(
            height=1,
            timestamp=int(time.time() * 1000),
            parent_hash=b"\x00" * 32,
            proposer=proposer,
            transactions=[],
        )

        assert block.height == 1
        assert block.proposer == proposer

    def test_create_genesis_block(self):
        """Create genesis block."""
        proposer = crypto.generate_keypair()[1]
        timestamp = int(time.time() * 1000)

        genesis = create_genesis_block(timestamp, proposer)

        assert genesis.height == 0
        assert genesis.parent_hash == b"\x00" * 32
        assert genesis.transactions == []

    def test_block_with_transactions(self):
        """Create block containing transactions."""
        priv, pub = crypto.generate_keypair()
        proposer = crypto.generate_keypair()[1]

        txs = []
        for i in range(3):
            tx = Transaction(
                nonce=i,
                sender=pub,
                operation=TransactionType.SENSOR_SUBMIT,
                data=f"data {i}".encode(),
            )
            tx.sign(priv)
            txs.append(tx)

        block = Block(
            height=1,
            timestamp=int(time.time() * 1000),
            parent_hash=b"\x00" * 32,
            proposer=proposer,
            transactions=txs,
        )

        assert len(block.transactions) == 3


class TestBlockHashing:
    """Test block hashing."""

    def test_block_hash_consistency(self):
        """Block hash should be consistent."""
        proposer = crypto.generate_keypair()[1]
        block = Block(
            height=1,
            timestamp=int(time.time() * 1000),
            parent_hash=b"\x00" * 32,
            proposer=proposer,
        )

        hash1 = block.hash()
        hash2 = block.hash()

        assert hash1 == hash2
        assert len(hash1) == 32

    def test_different_blocks_have_different_hashes(self):
        """Different blocks should have different hashes."""
        proposer = crypto.generate_keypair()[1]
        timestamp = int(time.time() * 1000)

        block1 = Block(
            height=1,
            timestamp=timestamp,
            parent_hash=b"\x00" * 32,
            proposer=proposer,
        )

        block2 = Block(
            height=2,  # Different height
            timestamp=timestamp,
            parent_hash=b"\x00" * 32,
            proposer=proposer,
        )

        assert block1.hash() != block2.hash()


class TestBlockSignatures:
    """Test block consensus signatures."""

    def test_add_signature_to_block(self):
        """Add a signature to a block."""
        priv, pub = crypto.generate_keypair()
        proposer = crypto.generate_keypair()[1]

        block = Block(
            height=1,
            timestamp=int(time.time() * 1000),
            parent_hash=b"\x00" * 32,
            proposer=proposer,
        )

        block_hash = block.hash()
        signature = crypto.sign(block_hash, priv)

        block.add_signature(pub, signature)

        assert block.verify_signature(pub)

    def test_finalized_block(self):
        """Block is finalized with quorum signatures."""
        proposer = crypto.generate_keypair()[1]
        block = Block(
            height=1,
            timestamp=int(time.time() * 1000),
            parent_hash=b"\x00" * 32,
            proposer=proposer,
        )

        # Add 2 signatures (quorum = 2)
        for _ in range(2):
            priv, pub = crypto.generate_keypair()
            signature = crypto.sign(block.hash(), priv)
            block.add_signature(pub, signature)

        assert block.is_finalized(quorum_size=2)
        assert not block.is_finalized(quorum_size=3)


class TestBlockSerialization:
    """Test block CBOR serialization."""

    def test_block_serialize_deserialize(self):
        """Serialize and deserialize a block."""
        priv, pub = crypto.generate_keypair()
        proposer = crypto.generate_keypair()[1]
        timestamp = int(time.time() * 1000)

        block = Block(
            height=1,
            timestamp=timestamp,
            parent_hash=b"\x00" * 32,
            proposer=proposer,
        )

        # Add a signature
        signature = crypto.sign(block.hash(), priv)
        block.add_signature(pub, signature)

        cbor_bytes = block.to_cbor()
        restored = Block.from_cbor(cbor_bytes)

        assert restored.height == block.height
        assert restored.timestamp == block.timestamp
        assert restored.proposer == block.proposer
        assert restored.hash() == block.hash()
        assert restored.verify_signature(pub)
