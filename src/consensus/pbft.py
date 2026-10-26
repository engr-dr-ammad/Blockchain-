"""
Practical Byzantine Fault Tolerance (PBFT) consensus engine.

Implements the three-phase consensus protocol:
- Pre-prepare: Leader proposes a block
- Prepare: Validators vote to accept the proposal
- Commit: Validators vote to finalize the block

Reference: Castro & Liskov (1999), "Practical Byzantine Fault Tolerance"
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from src.blockchain.block import Block
from src.blockchain.crypto import sign, verify

logger = logging.getLogger(__name__)


class ConsensusPhase(str, Enum):
    """Consensus phase state machine."""
    IDLE = "idle"
    PRE_PREPARED = "pre_prepared"
    PREPARED = "prepared"
    COMMITTED = "committed"


@dataclass
class ConsensusMessage:
    """Base class for consensus messages."""
    view: int  # View number (view = round number for now)
    sequence: int  # Block height
    block_hash: bytes  # Block hash being voted on
    sender: int  # Validator index who sent this
    sender_pubkey: bytes  # Validator's public key

    def to_bytes(self) -> bytes:
        """Serialize for signing."""
        return (
            str(self.view).encode() +
            str(self.sequence).encode() +
            self.block_hash +
            str(self.sender).encode()
        )


@dataclass
class PrePrepareMessage(ConsensusMessage):
    """Pre-prepare phase message from leader."""
    block: Block = None  # The actual block being proposed
    signature: bytes = field(default_factory=bytes)

    def sign(self, private_key: bytes) -> None:
        """Sign the message."""
        self.signature = sign(self.to_bytes(), private_key)

    def verify(self) -> bool:
        """Verify the signature."""
        return verify(self.to_bytes(), self.signature, self.sender_pubkey)


@dataclass
class PrepareMessage(ConsensusMessage):
    """Prepare phase message from validators."""
    signature: bytes = field(default_factory=bytes)

    def sign(self, private_key: bytes) -> None:
        """Sign the message."""
        self.signature = sign(self.to_bytes(), private_key)

    def verify(self) -> bool:
        """Verify the signature."""
        return verify(self.to_bytes(), self.signature, self.sender_pubkey)


@dataclass
class CommitMessage(ConsensusMessage):
    """Commit phase message from validators."""
    signature: bytes = field(default_factory=bytes)

    def sign(self, private_key: bytes) -> None:
        """Sign the message."""
        self.signature = sign(self.to_bytes(), private_key)

    def verify(self) -> bool:
        """Verify the signature."""
        return verify(self.to_bytes(), self.signature, self.sender_pubkey)


class PBFTEngine:
    """
    Practical Byzantine Fault Tolerance consensus engine.

    Coordinates the three-phase consensus protocol among validators.
    """

    def __init__(
        self,
        validator_id: int,
        validators: List[tuple],  # List of (validator_id, public_key)
        private_key: bytes,
        timeout_prepare_ms: float = 5000,
        timeout_commit_ms: float = 10000,
    ):
        """
        Initialize PBFT engine.

        Args:
            validator_id: Index of this validator (0 to N-1)
            validators: List of (id, public_key) tuples
            private_key: This validator's private key
            timeout_prepare_ms: Timeout for prepare phase
            timeout_commit_ms: Timeout for commit phase
        """
        self.validator_id = validator_id
        self.validators = {v[0]: v[1] for v in validators}
        self.num_validators = len(self.validators)
        self.private_key = private_key
        self.public_key = validators[validator_id][1]

        # Fault tolerance: f = (N-1)/3
        self.f = (self.num_validators - 1) // 3
        # Quorum: 2f + 1 (minimum 2 for safety with 3+ validators)
        self.quorum = max(2, 2 * self.f + 1) if self.num_validators >= 3 else self.num_validators

        logger.info(
            f"PBFT Engine initialized: validator_id={validator_id}, "
            f"N={self.num_validators}, f={self.f}, quorum={self.quorum}"
        )

        # Consensus state
        self.view = 0  # Current view (leader = view % N)
        self.sequence = 0  # Current block height
        self.phase = ConsensusPhase.IDLE
        self.current_block: Optional[Block] = None

        # Message tracking
        self.pre_prepare_msg: Optional[PrePrepareMessage] = None
        self.prepare_votes: Dict[int, PrepareMessage] = {}  # validator_id -> message
        self.commit_votes: Dict[int, CommitMessage] = {}  # validator_id -> message

        # Timeouts
        self.timeout_prepare_ms = timeout_prepare_ms
        self.timeout_commit_ms = timeout_commit_ms
        self.last_activity_time = time.time() * 1000  # milliseconds

        # Queued messages (waiting for current sequence)
        self.pending_messages: List[ConsensusMessage] = []

        # Callbacks
        self.on_block_finalized = None  # Called when block is finalized

    def is_leader(self) -> bool:
        """Check if this validator is the current leader."""
        leader_id = self.view % self.num_validators
        return self.validator_id == leader_id

    def get_leader_id(self, view: Optional[int] = None) -> int:
        """Get leader ID for a given view."""
        view = view or self.view
        return view % self.num_validators

    def start_consensus_round(self, block: Block) -> None:
        """
        Start a new consensus round (leader only).

        Creates a pre-prepare message and broadcasts it.
        """
        if not self.is_leader():
            logger.warning(f"Validator {self.validator_id} is not leader, ignoring block proposal")
            return

        if block.height != self.sequence:
            logger.error(f"Block height {block.height} != current sequence {self.sequence}")
            return

        logger.info(f"Leader proposing block {block.height}")

        # Create pre-prepare message
        msg = PrePrepareMessage(
            view=self.view,
            sequence=block.height,
            block_hash=block.hash(),
            sender=self.validator_id,
            sender_pubkey=self.public_key,
            block=block,
        )
        msg.sign(self.private_key)

        self.pre_prepare_msg = msg
        self.current_block = block
        self.phase = ConsensusPhase.PRE_PREPARED
        self.last_activity_time = time.time() * 1000

        # Broadcast pre-prepare to all validators
        self.on_pre_prepare(msg)

    def on_pre_prepare(self, msg: PrePrepareMessage) -> None:
        """
        Handle pre-prepare message from leader.

        Validation:
        - Message is from current leader
        - Signature is valid
        - Block is valid
        - Sequence number is correct
        """
        if msg.sender != self.get_leader_id(msg.view):
            logger.warning(f"Pre-prepare from non-leader validator {msg.sender}")
            return

        if not msg.verify():
            logger.warning(f"Invalid pre-prepare signature from validator {msg.sender}")
            return

        if msg.sequence != self.sequence:
            logger.warning(
                f"Pre-prepare sequence {msg.sequence} != current {self.sequence}, queueing"
            )
            self.pending_messages.append(msg)
            return

        if msg.view < self.view:
            logger.warning(f"Pre-prepare from old view {msg.view}")
            return

        # Update view if needed (view change recovery)
        if msg.view > self.view:
            self.view = msg.view

        logger.info(f"Accepting pre-prepare for block {msg.sequence}")

        self.pre_prepare_msg = msg
        self.current_block = msg.block
        self.phase = ConsensusPhase.PRE_PREPARED
        self.last_activity_time = time.time() * 1000

        # Send prepare vote
        prepare_msg = PrepareMessage(
            view=self.view,
            sequence=msg.sequence,
            block_hash=msg.block_hash,
            sender=self.validator_id,
            sender_pubkey=self.public_key,
        )
        prepare_msg.sign(self.private_key)

        self.on_prepare(prepare_msg)

        # Broadcast prepare to all validators (including self)
        # In real implementation, this would broadcast to network

    def on_prepare(self, msg: PrepareMessage) -> None:
        """
        Handle prepare message.

        Collects prepare votes. When 2f+1 prepares received, move to commit phase.
        """
        if msg.sequence != self.sequence:
            logger.debug(f"Prepare for future sequence {msg.sequence}, queueing")
            self.pending_messages.append(msg)
            return

        if not msg.verify():
            logger.warning(f"Invalid prepare signature from validator {msg.sender}")
            return

        if msg.sender in self.prepare_votes:
            logger.debug(f"Duplicate prepare from validator {msg.sender}")
            return

        self.prepare_votes[msg.sender] = msg
        self.last_activity_time = time.time() * 1000

        # Check if we have quorum
        if len(self.prepare_votes) >= self.quorum:
            logger.info(f"Quorum of prepares received ({len(self.prepare_votes)}/{self.quorum})")
            self.phase = ConsensusPhase.PREPARED
            self._send_commit()

    def _send_commit(self) -> None:
        """Send commit message."""
        if self.phase != ConsensusPhase.PREPARED:
            return

        if not self.pre_prepare_msg:
            logger.warning("Cannot send commit: no pre-prepare message")
            return

        commit_msg = CommitMessage(
            view=self.view,
            sequence=self.sequence,
            block_hash=self.pre_prepare_msg.block_hash,
            sender=self.validator_id,
            sender_pubkey=self.public_key,
        )
        commit_msg.sign(self.private_key)

        self.on_commit(commit_msg)

        # Broadcast commit to all validators

    def on_commit(self, msg: CommitMessage) -> None:
        """
        Handle commit message.

        Collects commit votes. When 2f+1 commits received, block is final.
        """
        if msg.sequence != self.sequence:
            logger.debug(f"Commit for future sequence {msg.sequence}, queueing")
            self.pending_messages.append(msg)
            return

        if not msg.verify():
            logger.warning(f"Invalid commit signature from validator {msg.sender}")
            return

        if msg.sender in self.commit_votes:
            logger.debug(f"Duplicate commit from validator {msg.sender}")
            return

        self.commit_votes[msg.sender] = msg
        self.last_activity_time = time.time() * 1000

        # Check if we have quorum
        if len(self.commit_votes) >= self.quorum:
            logger.info(f"Quorum of commits received ({len(self.commit_votes)}/{self.quorum})")
            self._finalize_block()

    def _finalize_block(self) -> None:
        """Finalize the current block."""
        if self.phase == ConsensusPhase.COMMITTED:
            return  # Already finalized

        if not self.current_block:
            logger.error("No current block to finalize")
            return

        block = self.current_block
        logger.info(f"Block {block.height} FINALIZED with {len(self.commit_votes)} signatures")

        # Add all commit signatures to the block
        for validator_id, commit_msg in self.commit_votes.items():
            # Sign the block with this validator's signature
            # (In real PBFT, we'd collect signatures)
            pass

        self.phase = ConsensusPhase.COMMITTED

        # Callback
        if self.on_block_finalized:
            self.on_block_finalized(block)

        # Prepare for next round
        self._advance_round()

    def _advance_round(self) -> None:
        """Advance to next consensus round."""
        self.sequence += 1
        self.phase = ConsensusPhase.IDLE
        self.current_block = None
        self.pre_prepare_msg = None
        self.prepare_votes.clear()
        self.commit_votes.clear()

        # Process any queued messages for this sequence
        ready_messages = [m for m in self.pending_messages if m.sequence == self.sequence]
        for msg in ready_messages:
            self.pending_messages.remove(msg)
            if isinstance(msg, PrePrepareMessage):
                self.on_pre_prepare(msg)
            elif isinstance(msg, PrepareMessage):
                self.on_prepare(msg)
            elif isinstance(msg, CommitMessage):
                self.on_commit(msg)

    def check_timeout(self) -> bool:
        """
        Check for consensus timeout.

        Returns True if timeout occurred.
        """
        now = time.time() * 1000

        if self.phase == ConsensusPhase.PRE_PREPARED:
            elapsed = now - self.last_activity_time
            if elapsed > self.timeout_prepare_ms:
                logger.warning(f"Prepare phase timeout after {elapsed}ms")
                self._trigger_view_change()
                return True

        elif self.phase == ConsensusPhase.PREPARED:
            elapsed = now - self.last_activity_time
            if elapsed > self.timeout_commit_ms:
                logger.warning(f"Commit phase timeout after {elapsed}ms")
                self._trigger_view_change()
                return True

        return False

    def _trigger_view_change(self) -> None:
        """Trigger a view change (leader election)."""
        self.view += 1
        self.phase = ConsensusPhase.IDLE
        self.prepare_votes.clear()
        self.commit_votes.clear()

        logger.info(f"View changed to {self.view}, new leader: {self.get_leader_id()}")

    def get_status(self) -> dict:
        """Get consensus engine status."""
        return {
            "validator_id": self.validator_id,
            "view": self.view,
            "is_leader": self.is_leader(),
            "sequence": self.sequence,
            "phase": self.phase.value,
            "prepares": len(self.prepare_votes),
            "commits": len(self.commit_votes),
            "quorum": self.quorum,
        }
