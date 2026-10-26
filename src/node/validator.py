"""
Validator node combining blockchain, consensus, and networking.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional, Tuple

from src.blockchain.chain import Blockchain
from src.blockchain.crypto import generate_keypair
from src.blockchain.mempool import Mempool
from src.consensus.pbft import PBFTEngine, PrePrepareMessage, PrepareMessage, CommitMessage
from src.network.peer import PeerNetwork

logger = logging.getLogger(__name__)


class ValidatorNode:
    """
    A validator node combining blockchain, consensus, and networking.
    """

    def __init__(
        self,
        validator_id: int,
        validators: Dict[int, Tuple[str, int]],  # id -> (host, port)
        db_path: str,
        bind_host: str = "0.0.0.0",
        bind_port: Optional[int] = None,
    ):
        """
        Initialize validator node.

        Args:
            validator_id: Index of this validator (0, 1, 2, ...)
            validators: Dict mapping validator ID to (host, port)
            db_path: Path for blockchain database
            bind_host: Address to bind server to
            bind_port: Port to bind server to (default: 8001 + validator_id)
        """
        self.validator_id = validator_id
        self.validators = validators
        self.db_path = db_path
        self.bind_host = bind_host
        self.bind_port = bind_port or (8000 + validator_id)

        # Generate keypair for this validator
        self.private_key, self.public_key = generate_keypair()
        logger.info(f"Validator {validator_id} public key: {self.public_key.hex()[:16]}...")

        # Blockchain
        self.blockchain = Blockchain(db_path)
        logger.info(f"Blockchain initialized. Height: {self.blockchain.get_height()}")

        # Consensus engine
        validator_list = [
            (vid, validators[vid][2] if len(validators[vid]) > 2 else self.public_key)
            for vid in sorted(validators.keys())
        ]

        self.consensus = PBFTEngine(
            validator_id=validator_id,
            validators=validator_list,
            private_key=self.private_key,
        )

        self.consensus.on_block_finalized = self._on_block_finalized

        # Networking
        self.network = PeerNetwork(
            validator_id=validator_id,
            validators=validators,
            host=bind_host,
            port=self.bind_port,
        )

        self.network.on_message = self._on_network_message

        # Block proposal task
        self.block_proposal_task: Optional[asyncio.Task] = None
        self.running = False

    async def start(self):
        """Start the validator node."""
        logger.info(f"Starting validator {self.validator_id}")

        # Start networking
        await self.network.start()

        # Start block proposal loop
        self.running = True
        self.block_proposal_task = asyncio.create_task(self._block_proposal_loop())

        logger.info(f"Validator {self.validator_id} started on {self.bind_host}:{self.bind_port}")

    async def shutdown(self):
        """Shutdown the validator."""
        logger.info(f"Shutting down validator {self.validator_id}")

        self.running = False

        if self.block_proposal_task:
            self.block_proposal_task.cancel()

        await self.network.shutdown()
        self.blockchain.close()

    async def _block_proposal_loop(self):
        """
        Continuously propose blocks when leader.
        """
        while self.running:
            try:
                # If leader and idle, propose a new block
                if self.consensus.is_leader() and self.consensus.phase.value == "idle":
                    pending = self.blockchain.get_pending_transactions(max_count=100)

                    if pending or self.consensus.sequence == 0:
                        # Create a new block
                        tip = self.blockchain.get_latest_block()

                        from src.blockchain.block import Block
                        block = Block(
                            height=self.consensus.sequence,
                            timestamp=int(time.time() * 1000),
                            parent_hash=tip.hash() if tip else b"\x00" * 32,
                            proposer=self.public_key,
                            transactions=pending,
                        )

                        logger.info(f"Leader proposing block {block.height} with {len(pending)} transactions")

                        # Start consensus round
                        self.consensus.start_consensus_round(block)

                        # Broadcast pre-prepare message
                        await self._broadcast_pre_prepare()

                # Check for consensus timeout
                if self.consensus.check_timeout():
                    logger.info(f"Consensus timeout, changing view to {self.consensus.view}")
                    # Would broadcast view-change message here (Stage 3+)

                await asyncio.sleep(0.1)  # Poll frequency

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in block proposal loop: {e}")
                await asyncio.sleep(1)

    async def _broadcast_pre_prepare(self):
        """Broadcast pre-prepare message to all peers."""
        if not self.consensus.pre_prepare_msg:
            return

        msg = self.consensus.pre_prepare_msg
        message = {
            "type": "pre_prepare",
            "view": msg.view,
            "sequence": msg.sequence,
            "block_hash": msg.block_hash.hex(),
            "sender": msg.sender,
            "block": {
                "height": msg.block.height,
                "timestamp": msg.block.timestamp,
                "parent_hash": msg.block.parent_hash.hex(),
                "proposer": msg.block.proposer.hex(),
                "transactions": len(msg.block.transactions),
                "merkle_root": msg.block.merkle_root.hex(),
                "state_root": msg.block.state_root.hex(),
            },
            "signature": msg.signature.hex(),
        }

        await self.network.broadcast_message(message)

    async def _on_network_message(self, message: dict):
        """Handle incoming message from network."""
        msg_type = message.get("type")

        try:
            if msg_type == "pre_prepare":
                await self._handle_pre_prepare(message)
            elif msg_type == "prepare":
                await self._handle_prepare(message)
            elif msg_type == "commit":
                await self._handle_commit(message)
        except Exception as e:
            logger.error(f"Error handling {msg_type} message: {e}")

    async def _handle_pre_prepare(self, message: dict):
        """Handle pre-prepare message."""
        # Reconstruct the message
        block_data = message.get("block", {})

        from src.blockchain.block import Block
        block = Block(
            height=block_data.get("height", 0),
            timestamp=block_data.get("timestamp", 0),
            parent_hash=bytes.fromhex(block_data.get("parent_hash", "00" * 32)),
            proposer=bytes.fromhex(block_data.get("proposer", "00" * 32)),
            transactions=[],  # Would reconstruct full transactions here
            merkle_root=bytes.fromhex(block_data.get("merkle_root", "00" * 32)),
            state_root=bytes.fromhex(block_data.get("state_root", "00" * 32)),
        )

        msg = PrePrepareMessage(
            view=message.get("view", 0),
            sequence=message.get("sequence", 0),
            block_hash=bytes.fromhex(message.get("block_hash", "00" * 32)),
            sender=message.get("sender", 0),
            sender_pubkey=self.validators[message.get("sender", 0)][2]
            if len(self.validators.get(message.get("sender", 0), ("", 0))) > 2
            else b"\x00" * 32,
            block=block,
            signature=bytes.fromhex(message.get("signature", "")),
        )

        self.consensus.on_pre_prepare(msg)

        # Broadcast prepare message
        await self._broadcast_prepare()

    async def _broadcast_prepare(self):
        """Broadcast prepare message."""
        # Get prepare vote from consensus
        if self.validator_id in self.consensus.prepare_votes:
            msg = self.consensus.prepare_votes[self.validator_id]
        else:
            return  # No prepare vote yet

        message = {
            "type": "prepare",
            "view": msg.view,
            "sequence": msg.sequence,
            "block_hash": msg.block_hash.hex(),
            "sender": msg.sender,
            "signature": msg.signature.hex(),
        }

        await self.network.broadcast_message(message)

    async def _handle_prepare(self, message: dict):
        """Handle prepare message."""
        msg = PrepareMessage(
            view=message.get("view", 0),
            sequence=message.get("sequence", 0),
            block_hash=bytes.fromhex(message.get("block_hash", "00" * 32)),
            sender=message.get("sender", 0),
            sender_pubkey=self.validators[message.get("sender", 0)][2]
            if len(self.validators.get(message.get("sender", 0), ("", 0))) > 2
            else b"\x00" * 32,
            signature=bytes.fromhex(message.get("signature", "")),
        )

        self.consensus.on_prepare(msg)

    async def _broadcast_commit(self):
        """Broadcast commit message."""
        # Get commit vote from consensus
        if self.validator_id in self.consensus.commit_votes:
            msg = self.consensus.commit_votes[self.validator_id]
        else:
            return  # No commit vote yet

        message = {
            "type": "commit",
            "view": msg.view,
            "sequence": msg.sequence,
            "block_hash": msg.block_hash.hex(),
            "sender": msg.sender,
            "signature": msg.signature.hex(),
        }

        await self.network.broadcast_message(message)

    async def _handle_commit(self, message: dict):
        """Handle commit message."""
        msg = CommitMessage(
            view=message.get("view", 0),
            sequence=message.get("sequence", 0),
            block_hash=bytes.fromhex(message.get("block_hash", "00" * 32)),
            sender=message.get("sender", 0),
            sender_pubkey=self.validators[message.get("sender", 0)][2]
            if len(self.validators.get(message.get("sender", 0), ("", 0))) > 2
            else b"\x00" * 32,
            signature=bytes.fromhex(message.get("signature", "")),
        )

        self.consensus.on_commit(msg)

    def _on_block_finalized(self, block):
        """Called when a block is finalized by consensus."""
        logger.info(f"Block {block.height} finalized, appending to chain")

        # Remove transactions from mempool
        self.blockchain.remove_transactions_from_mempool(block)

        # Append to blockchain
        success = self.blockchain.append_block(block)

        if success:
            logger.info(f"Block {block.height} appended to chain. New height: {self.blockchain.get_height()}")
        else:
            logger.error(f"Failed to append block {block.height} to chain")

    def get_status(self) -> dict:
        """Get node status."""
        return {
            "validator_id": self.validator_id,
            "public_key": self.public_key.hex()[:16] + "...",
            "chain_height": self.blockchain.get_height(),
            "mempool_size": self.blockchain.mempool.size(),
            "consensus": self.consensus.get_status(),
        }
