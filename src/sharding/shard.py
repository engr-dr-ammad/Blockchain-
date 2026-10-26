"""
Sharding engine for IoT-ShardChain.

Distributes sensors and transactions across multiple shards using
consistent hashing. Each shard maintains its own sub-ledger.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from src.blockchain.crypto import hash_hex

logger = logging.getLogger(__name__)


class ShardRole(str, Enum):
    """Role of a node in shard consensus."""
    LEADER = "leader"
    VALIDATOR = "validator"
    OBSERVER = "observer"


@dataclass
class ShardConfig:
    """Configuration for a shard."""
    shard_id: int
    num_shards: int
    validators_per_shard: int
    min_shard_size: int = 1  # Minimum sensors per shard


class ConsistentHashRing:
    """
    Consistent hash ring for distributing items across shards.

    Uses MD5-style hashing to map items to shards with minimal
    redistribution when shards are added/removed.
    """

    VIRTUAL_NODES = 160  # Nodes per shard for better distribution

    def __init__(self, num_shards: int):
        """
        Initialize consistent hash ring.

        Args:
            num_shards: Number of shards in the ring
        """
        self.num_shards = num_shards
        self.ring: Dict[str, int] = {}  # hash -> shard_id
        self.shard_hashes: Dict[int, List[str]] = {i: [] for i in range(num_shards)}

        self._build_ring()

    def _build_ring(self) -> None:
        """Build the consistent hash ring."""
        self.ring.clear()
        for shard_id in range(self.num_shards):
            shard_hashes = self.shard_hashes[shard_id]
            shard_hashes.clear()

            for i in range(self.VIRTUAL_NODES):
                # Create virtual node hash
                virtual_key = f"shard-{shard_id}-node-{i}"
                node_hash = hash_hex(virtual_key.encode())
                self.ring[node_hash] = shard_id
                shard_hashes.append(node_hash)

    def get_shard(self, key: str) -> int:
        """
        Get shard assignment for a key.

        Args:
            key: Item to hash (sensor_id, transaction_id, etc)

        Returns:
            Shard ID (0 to num_shards-1)
        """
        if not self.ring:
            return 0

        key_hash = hash_hex(key.encode())

        # Find the closest hash in the ring that is >= key_hash
        sorted_hashes = sorted(self.ring.keys())

        for ring_hash in sorted_hashes:
            if ring_hash >= key_hash:
                return self.ring[ring_hash]

        # Wrap around to first shard
        return self.ring[sorted_hashes[0]]

    def get_replication_shards(self, key: str, replication_factor: int = 3) -> List[int]:
        """
        Get multiple shards for replication.

        Args:
            key: Item to hash
            replication_factor: Number of replicas

        Returns:
            List of shard IDs for replication
        """
        primary_shard = self.get_shard(key)
        shards = [primary_shard]

        # Add subsequent shards
        offset = 1
        while len(shards) < min(replication_factor, self.num_shards):
            replica_shard = (primary_shard + offset) % self.num_shards
            if replica_shard not in shards:
                shards.append(replica_shard)
            offset += 1

        return shards


@dataclass
class ShardState:
    """State of a single shard."""
    shard_id: int
    height: int = 0  # Current shard block height
    block_hash: Optional[bytes] = None  # Latest shard block hash
    sensor_count: int = 0  # Number of sensors in this shard
    transaction_count: int = 0  # Number of transactions in this shard
    leaders: List[int] = None  # Validator IDs that have been leaders

    def __post_init__(self):
        if self.leaders is None:
            self.leaders = []


class ShardManager:
    """
    Manages sharding across multiple shards.

    Distributes sensors, transactions, and validator assignments
    across shards using consistent hashing.
    """

    def __init__(self, num_shards: int, num_validators: int,
                 validators_per_shard: int = 3):
        """
        Initialize shard manager.

        Args:
            num_shards: Number of shards (typically 4, 8, 16, 32)
            num_validators: Total number of validators in network
            validators_per_shard: Validators per shard (should be odd for PBFT)
        """
        self.num_shards = num_shards
        self.num_validators = num_validators
        self.validators_per_shard = validators_per_shard

        if validators_per_shard % 2 == 0:
            logger.warning(f"validators_per_shard should be odd for PBFT, got {validators_per_shard}")

        self.hash_ring = ConsistentHashRing(num_shards)
        self.shard_states: Dict[int, ShardState] = {
            i: ShardState(shard_id=i) for i in range(num_shards)
        }

        # Sensor to shard mapping
        self.sensor_shards: Dict[str, int] = {}

        # Shard to validators mapping
        self.shard_validators: Dict[int, List[int]] = self._assign_validators()

        logger.info(
            f"Shard manager initialized: {num_shards} shards, "
            f"{num_validators} validators, {validators_per_shard} per shard"
        )

    def _assign_validators(self) -> Dict[int, List[int]]:
        """
        Assign validators to shards.

        Uses round-robin distribution to assign validators evenly.

        Returns:
            Mapping of shard_id -> list of validator IDs
        """
        assignments = {i: [] for i in range(self.num_shards)}

        # Round-robin assignment
        for validator_id in range(self.num_validators):
            shard_id = validator_id % self.num_shards
            assignments[shard_id].append(validator_id)

        # Trim to validators_per_shard if needed
        for shard_id in assignments:
            if len(assignments[shard_id]) > self.validators_per_shard:
                assignments[shard_id] = assignments[shard_id][:self.validators_per_shard]

        return assignments

    def get_sensor_shard(self, sensor_id: str) -> int:
        """
        Get shard assignment for a sensor.

        Args:
            sensor_id: Sensor identifier

        Returns:
            Shard ID (0 to num_shards-1)
        """
        if sensor_id not in self.sensor_shards:
            shard_id = self.hash_ring.get_shard(sensor_id)
            self.sensor_shards[sensor_id] = shard_id
            self.shard_states[shard_id].sensor_count += 1

            logger.debug(f"Assigned sensor {sensor_id} to shard {shard_id}")

        return self.sensor_shards[sensor_id]

    def get_shard_validators(self, shard_id: int) -> List[int]:
        """
        Get validators assigned to a shard.

        Args:
            shard_id: Shard identifier

        Returns:
            List of validator IDs
        """
        return self.shard_validators.get(shard_id, [])

    def get_shard_leader(self, shard_id: int, view: int) -> Optional[int]:
        """
        Get leader for a shard at a given view.

        Args:
            shard_id: Shard identifier
            view: Current view/round number

        Returns:
            Leader validator ID, or None if shard has no validators
        """
        validators = self.get_shard_validators(shard_id)
        if not validators:
            return None

        leader_index = view % len(validators)
        return validators[leader_index]

    def get_sensor_replicas(self, sensor_id: str, replication_factor: int = 3) -> List[int]:
        """
        Get shard replicas for a sensor (for fault tolerance).

        Args:
            sensor_id: Sensor identifier
            replication_factor: Number of replicas

        Returns:
            List of shard IDs (primary first)
        """
        return self.hash_ring.get_replication_shards(sensor_id, replication_factor)

    def update_shard_height(self, shard_id: int, height: int,
                           block_hash: Optional[bytes] = None) -> None:
        """
        Update shard state after block finalization.

        Args:
            shard_id: Shard identifier
            height: New shard height
            block_hash: Hash of finalized block
        """
        if shard_id < self.num_shards:
            self.shard_states[shard_id].height = height
            if block_hash:
                self.shard_states[shard_id].block_hash = block_hash

    def update_shard_transactions(self, shard_id: int, count: int) -> None:
        """
        Update transaction count for shard.

        Args:
            shard_id: Shard identifier
            count: Number of transactions processed
        """
        if shard_id < self.num_shards:
            self.shard_states[shard_id].transaction_count += count

    def get_shard_state(self, shard_id: int) -> Optional[ShardState]:
        """Get state of a shard."""
        return self.shard_states.get(shard_id)

    def get_all_shard_states(self) -> Dict[int, ShardState]:
        """Get states of all shards."""
        return dict(self.shard_states)

    def get_shard_stats(self) -> dict:
        """Get aggregated statistics across all shards."""
        total_height = sum(s.height for s in self.shard_states.values())
        total_sensors = sum(s.sensor_count for s in self.shard_states.values())
        total_transactions = sum(s.transaction_count for s in self.shard_states.values())

        return {
            "num_shards": self.num_shards,
            "num_validators": self.num_validators,
            "validators_per_shard": self.validators_per_shard,
            "total_height": total_height,
            "average_shard_height": total_height / self.num_shards if self.num_shards > 0 else 0,
            "total_sensors": total_sensors,
            "average_sensors_per_shard": total_sensors / self.num_shards if self.num_shards > 0 else 0,
            "total_transactions": total_transactions,
            "average_transactions_per_shard": total_transactions / self.num_shards if self.num_shards > 0 else 0,
        }

    def get_load_balance_info(self) -> Dict[int, dict]:
        """
        Get load balancing information for each shard.

        Returns:
            Mapping of shard_id -> load info
        """
        info = {}
        for shard_id, state in self.shard_states.items():
            info[shard_id] = {
                "shard_id": shard_id,
                "height": state.height,
                "sensors": state.sensor_count,
                "transactions": state.transaction_count,
                "validators": len(self.shard_validators.get(shard_id, [])),
            }
        return info


class CrossShardCoordinator:
    """
    Coordinates transactions that span multiple shards.

    Handles:
    - Cross-shard transaction validation
    - Two-phase commit coordination
    - Cross-shard message routing
    """

    def __init__(self, shard_manager: ShardManager):
        """
        Initialize cross-shard coordinator.

        Args:
            shard_manager: ShardManager instance
        """
        self.shard_manager = shard_manager
        self.pending_cross_shard: Dict[str, dict] = {}  # tx_id -> tx_state

    def get_shards_for_transaction(self, sensor_ids: List[str]) -> Set[int]:
        """
        Get all shards involved in a transaction.

        Args:
            sensor_ids: List of sensor IDs in transaction

        Returns:
            Set of shard IDs
        """
        shards = set()
        for sensor_id in sensor_ids:
            shard_id = self.shard_manager.get_sensor_shard(sensor_id)
            shards.add(shard_id)
        return shards

    def is_cross_shard(self, sensor_ids: List[str]) -> bool:
        """
        Check if transaction spans multiple shards.

        Args:
            sensor_ids: List of sensor IDs

        Returns:
            True if sensors are in different shards
        """
        shards = self.get_shards_for_transaction(sensor_ids)
        return len(shards) > 1

    def get_coordinator_shard(self, sensor_ids: List[str]) -> int:
        """
        Get the shard that will coordinate cross-shard transaction.

        Uses the shard of the first sensor as coordinator.

        Args:
            sensor_ids: List of sensor IDs

        Returns:
            Coordinator shard ID
        """
        if not sensor_ids:
            return 0
        return self.shard_manager.get_sensor_shard(sensor_ids[0])

    def validate_cross_shard_transaction(self, tx_id: str,
                                        sensor_ids: List[str]) -> Tuple[bool, str]:
        """
        Validate a cross-shard transaction.

        Args:
            tx_id: Transaction ID
            sensor_ids: List of sensor IDs in transaction

        Returns:
            Tuple of (is_valid, reason)
        """
        if not sensor_ids:
            return False, "Transaction has no sensors"

        shards = self.get_shards_for_transaction(sensor_ids)

        if len(shards) == 1:
            return True, "Single-shard transaction"

        if len(shards) > self.shard_manager.num_shards:
            return False, "Transaction involves more shards than exist"

        return True, "Valid cross-shard transaction"
