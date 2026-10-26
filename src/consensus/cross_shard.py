"""
Cross-shard transaction coordination using two-phase commit.

Ensures atomicity of transactions spanning multiple shards.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from enum import Enum
import time

from src.blockchain.crypto import hash as crypto_hash, sign, verify
from src.sharding.shard import CrossShardCoordinator, ShardManager


class TransactionPhase(str, Enum):
    """Phases of cross-shard transaction."""
    PROPOSED = "proposed"
    PREPARE = "prepare"
    PREPARED = "prepared"
    COMMIT = "commit"
    COMMITTED = "committed"
    ABORTED = "aborted"


class ShardVote(str, Enum):
    """Shard vote on transaction preparation."""
    YES = "yes"  # Shard can commit transaction
    NO = "no"    # Shard cannot commit (conflict or invalid)
    ABSTAIN = "abstain"  # No vote


@dataclass
class CrossShardTransaction:
    """Transaction spanning multiple shards."""
    tx_id: str
    coordinator_shard: int
    involved_shards: Set[int]
    sensor_ids: List[str]  # Sensors involved
    timestamp: int
    phase: TransactionPhase = TransactionPhase.PROPOSED
    proposer: bytes = None  # Validator proposing transaction


@dataclass
class PrepareRequest:
    """Request for shard to prepare transaction."""
    tx_id: str
    coordinator_shard: int
    involved_shards: List[int]
    sensor_ids: List[str]
    timestamp: int
    proposer: bytes  # Signer's public key
    signature: bytes  # Signature of request

    def serialize(self) -> bytes:
        """Serialize prepare request."""
        data = (
            self.tx_id.encode() +
            self.coordinator_shard.to_bytes(4, 'big') +
            len(self.involved_shards).to_bytes(2, 'big')
        )
        for shard in self.involved_shards:
            data += shard.to_bytes(4, 'big')
        data += len(self.sensor_ids).to_bytes(2, 'big')
        for sensor_id in self.sensor_ids:
            sensor_bytes = sensor_id.encode()
            data += len(sensor_bytes).to_bytes(2, 'big') + sensor_bytes
        data += self.timestamp.to_bytes(8, 'big')
        data += self.proposer + self.signature
        return data

    @staticmethod
    def deserialize(data: bytes) -> "PrepareRequest":
        """Deserialize prepare request."""
        offset = 0
        tx_id_len = int.from_bytes(data[offset:offset+4], 'big')
        # Assume tx_id is hex string of hash, so 64 chars
        tx_id = data[offset:offset+64].decode()
        offset += 64

        coordinator_shard = int.from_bytes(data[offset:offset+4], 'big')
        offset += 4
        num_shards = int.from_bytes(data[offset:offset+2], 'big')
        offset += 2

        involved_shards = []
        for _ in range(num_shards):
            involved_shards.append(int.from_bytes(data[offset:offset+4], 'big'))
            offset += 4

        num_sensors = int.from_bytes(data[offset:offset+2], 'big')
        offset += 2
        sensor_ids = []
        for _ in range(num_sensors):
            sensor_len = int.from_bytes(data[offset:offset+2], 'big')
            offset += 2
            sensor_ids.append(data[offset:offset+sensor_len].decode())
            offset += sensor_len

        timestamp = int.from_bytes(data[offset:offset+8], 'big')
        offset += 8
        proposer = data[offset:offset+32]
        offset += 32
        signature = data[offset:offset+64]

        return PrepareRequest(tx_id, coordinator_shard, involved_shards, sensor_ids, timestamp, proposer, signature)


@dataclass
class PrepareVote:
    """Shard's vote on transaction preparation."""
    tx_id: str
    shard_id: int
    vote: ShardVote
    reason: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time()))
    signer: bytes = None  # Shard leader's public key
    signature: bytes = None  # Signature

    def serialize(self) -> bytes:
        """Serialize prepare vote."""
        reason_bytes = self.reason.encode()
        data = (
            self.tx_id.encode() +
            self.shard_id.to_bytes(4, 'big') +
            self.vote.value.encode() +
            len(reason_bytes).to_bytes(2, 'big') +
            reason_bytes +
            self.timestamp.to_bytes(8, 'big')
        )
        if self.signer:
            data += self.signer
        if self.signature:
            data += self.signature
        return data

    @staticmethod
    def deserialize(data: bytes) -> "PrepareVote":
        """Deserialize prepare vote."""
        offset = 0
        tx_id = data[offset:offset+64].decode()
        offset += 64
        shard_id = int.from_bytes(data[offset:offset+4], 'big')
        offset += 4
        vote_str = data[offset:offset+3].decode()  # "yes", "no", or "abstain"
        offset += 3
        reason_len = int.from_bytes(data[offset:offset+2], 'big')
        offset += 2
        reason = data[offset:offset+reason_len].decode()
        offset += reason_len
        timestamp = int.from_bytes(data[offset:offset+8], 'big')
        offset += 8

        vote = ShardVote(vote_str) if vote_str in ["yes", "no", "abstain"] else ShardVote.ABSTAIN

        signer = data[offset:offset+32] if len(data) > offset + 32 else None
        offset += 32 if signer else 0
        signature = data[offset:offset+64] if len(data) > offset + 64 else None

        return PrepareVote(tx_id, shard_id, vote, reason, timestamp, signer, signature)


@dataclass
class CommitRequest:
    """Request to commit a prepared transaction."""
    tx_id: str
    coordinator_shard: int
    involved_shards: List[int]
    timestamp: int
    proposer: bytes
    signature: bytes

    def serialize(self) -> bytes:
        """Serialize commit request."""
        data = (
            self.tx_id.encode() +
            self.coordinator_shard.to_bytes(4, 'big') +
            len(self.involved_shards).to_bytes(2, 'big')
        )
        for shard in self.involved_shards:
            data += shard.to_bytes(4, 'big')
        data += self.timestamp.to_bytes(8, 'big')
        data += self.proposer + self.signature
        return data


class CrossShardTransactionManager:
    """Manages cross-shard transactions in a shard."""

    def __init__(self, shard_id: int, shard_manager: ShardManager):
        """
        Initialize transaction manager.

        Args:
            shard_id: This shard's ID
            shard_manager: ShardManager for shard information
        """
        self.shard_id = shard_id
        self.shard_manager = shard_manager
        self.cross_shard_coordinator = CrossShardCoordinator(shard_manager)

        # Transaction state tracking
        self.pending_transactions: Dict[str, CrossShardTransaction] = {}
        self.prepare_votes: Dict[str, Dict[int, PrepareVote]] = {}  # tx_id -> shard_id -> vote
        self.committed_transactions: Set[str] = set()
        self.aborted_transactions: Set[str] = set()

    def propose_cross_shard_transaction(
        self,
        tx_id: str,
        sensor_ids: List[str],
        proposer: bytes,
    ) -> Tuple[bool, str]:
        """
        Propose a cross-shard transaction.

        Args:
            tx_id: Transaction ID
            sensor_ids: Sensors involved in transaction
            proposer: Validator proposing transaction (public key)

        Returns:
            Tuple of (success, reason)
        """
        # Validate transaction
        is_valid, reason = self.cross_shard_coordinator.validate_cross_shard_transaction(
            tx_id, sensor_ids
        )
        if not is_valid:
            return False, reason

        # Get involved shards
        involved_shards = self.cross_shard_coordinator.get_shards_for_transaction(sensor_ids)
        coordinator_shard = self.cross_shard_coordinator.get_coordinator_shard(sensor_ids)

        # Create transaction
        tx = CrossShardTransaction(
            tx_id=tx_id,
            coordinator_shard=coordinator_shard,
            involved_shards=involved_shards,
            sensor_ids=sensor_ids,
            timestamp=int(time.time()),
            proposer=proposer,
        )

        self.pending_transactions[tx_id] = tx
        return True, "Transaction proposed"

    def handle_prepare_request(
        self,
        prepare_req: PrepareRequest,
    ) -> PrepareVote:
        """
        Handle prepare request from coordinator shard.

        Args:
            prepare_req: Prepare request from coordinator

        Returns:
            PrepareVote indicating yes/no/abstain
        """
        tx_id = prepare_req.tx_id

        # Check if already processed
        if tx_id in self.committed_transactions:
            return PrepareVote(
                tx_id=tx_id,
                shard_id=self.shard_id,
                vote=ShardVote.NO,
                reason="Transaction already committed",
                signer=None,
                signature=None,
            )

        if tx_id in self.aborted_transactions:
            return PrepareVote(
                tx_id=tx_id,
                shard_id=self.shard_id,
                vote=ShardVote.NO,
                reason="Transaction already aborted",
                signer=None,
                signature=None,
            )

        # Validate sensors in this shard
        shard_sensors = [s for s in prepare_req.sensor_ids
                        if self.shard_manager.get_sensor_shard(s) == self.shard_id]

        if not shard_sensors:
            return PrepareVote(
                tx_id=tx_id,
                shard_id=self.shard_id,
                vote=ShardVote.YES,  # No sensors in this shard, can commit
                reason="No sensors in this shard",
                signer=None,
                signature=None,
            )

        # Check if can prepare (validate sensors)
        for sensor_id in shard_sensors:
            sensor = self.shard_manager.shard_states[self.shard_id]
            if sensor is None:
                return PrepareVote(
                    tx_id=tx_id,
                    shard_id=self.shard_id,
                    vote=ShardVote.NO,
                    reason=f"Sensor {sensor_id} not found",
                    signer=None,
                    signature=None,
                )

        # Can prepare
        return PrepareVote(
            tx_id=tx_id,
            shard_id=self.shard_id,
            vote=ShardVote.YES,
            reason="Shard can commit",
            timestamp=int(time.time()),
            signer=None,
            signature=None,
        )

    def record_prepare_vote(self, vote: PrepareVote) -> None:
        """
        Record a prepare vote from this or another shard.

        Args:
            vote: PrepareVote to record
        """
        tx_id = vote.tx_id
        if tx_id not in self.prepare_votes:
            self.prepare_votes[tx_id] = {}

        self.prepare_votes[tx_id][vote.shard_id] = vote

    def get_prepare_votes(self, tx_id: str) -> Dict[int, PrepareVote]:
        """
        Get all prepare votes for a transaction.

        Args:
            tx_id: Transaction ID

        Returns:
            Dictionary of shard_id -> PrepareVote
        """
        return self.prepare_votes.get(tx_id, {})

    def check_prepare_quorum(self, tx_id: str) -> Tuple[bool, int, int]:
        """
        Check if prepare phase has reached quorum.

        Args:
            tx_id: Transaction ID

        Returns:
            Tuple of (has_quorum, yes_votes, total_votes)
        """
        if tx_id not in self.pending_transactions:
            return False, 0, 0

        tx = self.pending_transactions[tx_id]
        votes = self.prepare_votes.get(tx_id, {})

        # Count votes
        yes_votes = sum(1 for v in votes.values() if v.vote == ShardVote.YES)
        total_votes = len(votes)

        # Quorum: majority of involved shards must vote yes
        required = (len(tx.involved_shards) // 2) + 1

        has_quorum = yes_votes >= required

        return has_quorum, yes_votes, total_votes

    def commit_transaction(self, tx_id: str) -> bool:
        """
        Commit a prepared transaction.

        Args:
            tx_id: Transaction ID to commit

        Returns:
            True if committed, False otherwise
        """
        if tx_id not in self.pending_transactions:
            return False

        tx = self.pending_transactions[tx_id]
        tx.phase = TransactionPhase.COMMITTED

        self.committed_transactions.add(tx_id)

        return True

    def abort_transaction(self, tx_id: str) -> bool:
        """
        Abort a transaction.

        Args:
            tx_id: Transaction ID to abort

        Returns:
            True if aborted, False otherwise
        """
        if tx_id not in self.pending_transactions:
            return False

        tx = self.pending_transactions[tx_id]

        # Cannot abort already committed or aborted transactions
        if tx.phase == TransactionPhase.COMMITTED or tx.phase == TransactionPhase.ABORTED:
            return False

        tx.phase = TransactionPhase.ABORTED

        self.aborted_transactions.add(tx_id)

        return True

    def get_transaction_status(self, tx_id: str) -> Optional[TransactionPhase]:
        """
        Get status of a transaction.

        Args:
            tx_id: Transaction ID

        Returns:
            TransactionPhase or None if not found
        """
        if tx_id in self.pending_transactions:
            return self.pending_transactions[tx_id].phase
        if tx_id in self.committed_transactions:
            return TransactionPhase.COMMITTED
        if tx_id in self.aborted_transactions:
            return TransactionPhase.ABORTED
        return None
