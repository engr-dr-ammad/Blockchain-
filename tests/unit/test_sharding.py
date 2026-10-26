"""
Unit tests for sharding engine.
"""

import pytest
from src.sharding.shard import (
    ConsistentHashRing,
    ShardManager,
    CrossShardCoordinator,
)


class TestConsistentHashRing:
    """Test consistent hash ring for shard assignment."""

    def test_create_hash_ring(self):
        """Test creating a hash ring."""
        ring = ConsistentHashRing(num_shards=4)
        assert ring.num_shards == 4
        assert len(ring.ring) == 4 * ConsistentHashRing.VIRTUAL_NODES

    def test_get_shard_basic(self):
        """Test basic shard assignment."""
        ring = ConsistentHashRing(num_shards=4)

        # Should assign consistently
        shard1 = ring.get_shard("sensor-1")
        shard2 = ring.get_shard("sensor-1")

        assert shard1 == shard2
        assert 0 <= shard1 < 4

    def test_get_shard_distribution(self):
        """Test that shards are distributed across all shards."""
        ring = ConsistentHashRing(num_shards=4)

        shards_used = set()
        for i in range(100):
            shard = ring.get_shard(f"item-{i}")
            shards_used.add(shard)

        # Should use all 4 shards
        assert len(shards_used) == 4

    def test_shard_consistency(self):
        """Test that shard assignment is consistent."""
        ring = ConsistentHashRing(num_shards=8)

        # Get assignment for 1000 items
        assignments = {}
        for i in range(1000):
            key = f"item-{i}"
            assignments[key] = ring.get_shard(key)

        # Re-check assignments - should be identical
        for key, expected_shard in assignments.items():
            assert ring.get_shard(key) == expected_shard

    def test_get_replication_shards(self):
        """Test getting replica shards."""
        ring = ConsistentHashRing(num_shards=8)

        replicas = ring.get_replication_shards("sensor-1", replication_factor=3)

        assert len(replicas) == 3
        assert replicas[0] == ring.get_shard("sensor-1")  # Primary first
        assert len(set(replicas)) == 3  # All unique

    def test_replication_with_fewer_shards_than_replicas(self):
        """Test replication when replicas > shards."""
        ring = ConsistentHashRing(num_shards=3)

        # Request 5 replicas but only 3 shards exist
        replicas = ring.get_replication_shards("key", replication_factor=5)

        # Should return all 3 shards
        assert len(replicas) == 3

    def test_different_keys_different_assignments(self):
        """Test that different keys get different assignments."""
        ring = ConsistentHashRing(num_shards=4)

        shards = [ring.get_shard(f"key-{i}") for i in range(20)]

        # Most keys should be assigned to different shards
        assert len(set(shards)) > 1


class TestShardManager:
    """Test shard manager."""

    def test_create_shard_manager(self):
        """Test creating a shard manager."""
        manager = ShardManager(
            num_shards=4,
            num_validators=12,
            validators_per_shard=3,
        )

        assert manager.num_shards == 4
        assert manager.num_validators == 12
        assert manager.validators_per_shard == 3

    def test_get_sensor_shard(self):
        """Test getting sensor shard assignment."""
        manager = ShardManager(num_shards=4, num_validators=12)

        shard = manager.get_sensor_shard("sensor-1")
        assert 0 <= shard < 4

        # Should be consistent
        shard2 = manager.get_sensor_shard("sensor-1")
        assert shard == shard2

    def test_sensor_shard_tracking(self):
        """Test that sensor-to-shard mapping is tracked."""
        manager = ShardManager(num_shards=4, num_validators=12)

        shard = manager.get_sensor_shard("sensor-1")

        # Should be in internal map
        assert "sensor-1" in manager.sensor_shards
        assert manager.sensor_shards["sensor-1"] == shard

    def test_shard_count_tracking(self):
        """Test that shard tracks sensor count."""
        manager = ShardManager(num_shards=4, num_validators=12)

        # Add sensors
        shards_used = {}
        for i in range(20):
            sensor_id = f"sensor-{i}"
            shard = manager.get_sensor_shard(sensor_id)
            shards_used[shard] = shards_used.get(shard, 0) + 1

        # Check counts
        for shard_id, expected_count in shards_used.items():
            state = manager.get_shard_state(shard_id)
            assert state.sensor_count == expected_count

    def test_validator_assignment(self):
        """Test that validators are assigned to shards."""
        manager = ShardManager(
            num_shards=4,
            num_validators=12,
            validators_per_shard=3,
        )

        # Each shard should have 3 validators
        for shard_id in range(4):
            validators = manager.get_shard_validators(shard_id)
            assert len(validators) == 3

    def test_validator_distribution(self):
        """Test even distribution of validators."""
        manager = ShardManager(
            num_shards=4,
            num_validators=16,
            validators_per_shard=4,
        )

        # Total validator count
        total_validators = sum(
            len(manager.get_shard_validators(i))
            for i in range(4)
        )

        assert total_validators == 16

    def test_get_shard_leader(self):
        """Test getting shard leader for a view."""
        manager = ShardManager(num_shards=4, num_validators=12)

        validators = manager.get_shard_validators(0)

        # View 0: first validator is leader
        leader0 = manager.get_shard_leader(0, view=0)
        assert leader0 == validators[0]

        # View 1: second validator is leader
        leader1 = manager.get_shard_leader(0, view=1)
        assert leader1 == validators[1]

    def test_leader_rotation(self):
        """Test that leaders rotate across validators."""
        manager = ShardManager(
            num_shards=4,
            num_validators=12,
            validators_per_shard=3,
        )

        validators = manager.get_shard_validators(0)
        leaders = []

        for view in range(6):
            leader = manager.get_shard_leader(0, view=view)
            leaders.append(leader)

        # Should cycle through validators
        assert leaders[:3] == validators
        assert leaders[3:6] == validators

    def test_get_sensor_replicas(self):
        """Test getting replica shards for a sensor."""
        manager = ShardManager(num_shards=8, num_validators=24)

        replicas = manager.get_sensor_replicas("sensor-1", replication_factor=3)

        assert len(replicas) == 3
        assert replicas[0] == manager.get_sensor_shard("sensor-1")

    def test_update_shard_height(self):
        """Test updating shard height."""
        manager = ShardManager(num_shards=4, num_validators=12)

        manager.update_shard_height(0, height=10, block_hash=b"hash0")

        state = manager.get_shard_state(0)
        assert state.height == 10
        assert state.block_hash == b"hash0"

    def test_update_shard_transactions(self):
        """Test updating transaction count."""
        manager = ShardManager(num_shards=4, num_validators=12)

        manager.update_shard_transactions(0, count=5)
        manager.update_shard_transactions(0, count=3)

        state = manager.get_shard_state(0)
        assert state.transaction_count == 8

    def test_get_shard_stats(self):
        """Test getting aggregated shard statistics."""
        manager = ShardManager(num_shards=4, num_validators=12)

        # Add some data
        for i in range(10):
            manager.get_sensor_shard(f"sensor-{i}")

        manager.update_shard_height(0, 5)
        manager.update_shard_height(1, 5)
        manager.update_shard_transactions(0, 10)
        manager.update_shard_transactions(1, 8)

        stats = manager.get_shard_stats()

        assert stats["num_shards"] == 4
        assert stats["total_sensors"] == 10
        assert stats["total_transactions"] == 18
        assert stats["total_height"] == 10

    def test_get_load_balance_info(self):
        """Test getting load balance information."""
        manager = ShardManager(num_shards=4, num_validators=12)

        for i in range(12):
            manager.get_sensor_shard(f"sensor-{i}")

        balance = manager.get_load_balance_info()

        assert len(balance) == 4
        assert sum(b["sensors"] for b in balance.values()) == 12

        for shard_info in balance.values():
            assert "shard_id" in shard_info
            assert "height" in shard_info
            assert "sensors" in shard_info


class TestCrossShardCoordinator:
    """Test cross-shard transaction coordination."""

    def test_create_coordinator(self):
        """Test creating cross-shard coordinator."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        assert coordinator.shard_manager == manager

    def test_get_shards_for_single_sensor(self):
        """Test getting shards for single-sensor transaction."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        shards = coordinator.get_shards_for_transaction(["sensor-1"])

        assert len(shards) == 1
        assert shards == {manager.get_sensor_shard("sensor-1")}

    def test_get_shards_for_multiple_sensors(self):
        """Test getting shards for multi-sensor transaction."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        shards = coordinator.get_shards_for_transaction(["sensor-1", "sensor-2", "sensor-3"])

        # Might be 1 shard (if all in same shard) or multiple
        assert len(shards) >= 1

    def test_is_cross_shard_true(self):
        """Test detecting cross-shard transaction."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        # Try many combinations to find one that crosses shards
        found_cross_shard = False
        for i in range(20):
            shards = coordinator.get_shards_for_transaction([f"sensor-{i}", f"sensor-{i+100}"])
            if len(shards) > 1:
                assert coordinator.is_cross_shard([f"sensor-{i}", f"sensor-{i+100}"])
                found_cross_shard = True
                break

        # At least one should be cross-shard with 4 shards
        assert found_cross_shard

    def test_is_cross_shard_false(self):
        """Test detecting single-shard transaction."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        # Same sensor only
        assert not coordinator.is_cross_shard(["sensor-1"])

    def test_get_coordinator_shard(self):
        """Test getting coordinator shard."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        shard = coordinator.get_coordinator_shard(["sensor-1", "sensor-2"])

        # Should be the shard of the first sensor
        assert shard == manager.get_sensor_shard("sensor-1")

    def test_validate_cross_shard_transaction_single_shard(self):
        """Test validating single-shard transaction."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        is_valid, reason = coordinator.validate_cross_shard_transaction(
            "tx-1", ["sensor-1"]
        )

        assert is_valid
        assert "single-shard" in reason.lower()

    def test_validate_cross_shard_transaction_valid(self):
        """Test validating valid cross-shard transaction."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        is_valid, reason = coordinator.validate_cross_shard_transaction(
            "tx-1", ["sensor-1", "sensor-2", "sensor-3"]
        )

        assert is_valid

    def test_validate_empty_sensors(self):
        """Test validating transaction with no sensors."""
        manager = ShardManager(num_shards=4, num_validators=12)
        coordinator = CrossShardCoordinator(manager)

        is_valid, reason = coordinator.validate_cross_shard_transaction("tx-1", [])

        assert not is_valid
        assert "no sensors" in reason.lower()


class TestShardingEdgeCases:
    """Test edge cases in sharding."""

    def test_single_shard(self):
        """Test system with single shard."""
        manager = ShardManager(num_shards=1, num_validators=3)

        # All sensors should go to same shard
        shard1 = manager.get_sensor_shard("sensor-1")
        shard2 = manager.get_sensor_shard("sensor-2")

        assert shard1 == 0
        assert shard2 == 0

    def test_many_shards(self):
        """Test system with many shards."""
        manager = ShardManager(num_shards=64, num_validators=192)

        # Should handle 64 shards
        validators = manager.get_shard_validators(0)
        assert len(validators) <= 3

    def test_more_validators_than_shards(self):
        """Test when validators > shards * validators_per_shard."""
        manager = ShardManager(
            num_shards=4,
            num_validators=20,  # More than 4*3
            validators_per_shard=3,
        )

        # Some validators won't be assigned
        total = sum(len(manager.get_shard_validators(i)) for i in range(4))
        assert total <= 20

    def test_consistency_after_state_updates(self):
        """Test that hash ring is consistent after shard state updates."""
        manager = ShardManager(num_shards=4, num_validators=12)

        # Get initial assignments
        initial = {f"sensor-{i}": manager.get_sensor_shard(f"sensor-{i}")
                   for i in range(10)}

        # Update shard states
        manager.update_shard_height(0, 5)
        manager.update_shard_transactions(1, 10)

        # Verify assignments unchanged
        for sensor_id, expected_shard in initial.items():
            assert manager.get_sensor_shard(sensor_id) == expected_shard
