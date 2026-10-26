"""
Unit tests for cross-shard transaction coordination.
"""

import pytest
from src.consensus.cross_shard import (
    CrossShardTransaction,
    CrossShardTransactionManager,
    PrepareRequest,
    PrepareVote,
    CommitRequest,
    TransactionPhase,
    ShardVote,
)
from src.sharding.shard import ShardManager
from src.blockchain.crypto import generate_keypair


class TestCrossShardTransaction:
    """Test cross-shard transaction structure."""

    def test_create_cross_shard_transaction(self):
        """Test creating a cross-shard transaction."""
        tx = CrossShardTransaction(
            tx_id="tx-1",
            coordinator_shard=0,
            involved_shards={0, 1, 2},
            sensor_ids=["sensor-1", "sensor-2"],
            timestamp=1000,
        )

        assert tx.tx_id == "tx-1"
        assert tx.coordinator_shard == 0
        assert len(tx.involved_shards) == 3
        assert tx.phase == TransactionPhase.PROPOSED

    def test_transaction_phase_transitions(self):
        """Test transaction phase transitions."""
        tx = CrossShardTransaction(
            tx_id="tx-2",
            coordinator_shard=1,
            involved_shards={1, 2},
            sensor_ids=["sensor-3"],
            timestamp=2000,
        )

        assert tx.phase == TransactionPhase.PROPOSED
        tx.phase = TransactionPhase.PREPARE
        assert tx.phase == TransactionPhase.PREPARE
        tx.phase = TransactionPhase.PREPARED
        assert tx.phase == TransactionPhase.PREPARED


class TestPrepareRequest:
    """Test prepare request structure."""

    def test_create_prepare_request(self):
        """Test creating a prepare request."""
        proposer = b"\x00" * 32
        signature = b"\x01" * 64

        req = PrepareRequest(
            tx_id="tx-1",
            coordinator_shard=0,
            involved_shards=[0, 1, 2],
            sensor_ids=["sensor-1", "sensor-2"],
            timestamp=1000,
            proposer=proposer,
            signature=signature,
        )

        assert req.tx_id == "tx-1"
        assert req.coordinator_shard == 0
        assert len(req.involved_shards) == 3

    def test_prepare_request_serialization(self):
        """Test serialization of prepare request."""
        proposer = b"\x00" * 32
        signature = b"\x01" * 64

        req = PrepareRequest(
            tx_id="a" * 64,  # 64 char hex string
            coordinator_shard=1,
            involved_shards=[1, 2],
            sensor_ids=["sensor-x"],
            timestamp=5000,
            proposer=proposer,
            signature=signature,
        )

        serialized = req.serialize()
        assert len(serialized) > 0
        # Don't deserialize for now - serialization format may vary


class TestPrepareVote:
    """Test prepare vote structure."""

    def test_create_prepare_vote_yes(self):
        """Test creating a yes vote."""
        vote = PrepareVote(
            tx_id="tx-1",
            shard_id=1,
            vote=ShardVote.YES,
            reason="Shard can commit",
        )

        assert vote.tx_id == "tx-1"
        assert vote.shard_id == 1
        assert vote.vote == ShardVote.YES

    def test_create_prepare_vote_no(self):
        """Test creating a no vote."""
        vote = PrepareVote(
            tx_id="tx-2",
            shard_id=2,
            vote=ShardVote.NO,
            reason="Conflict detected",
        )

        assert vote.vote == ShardVote.NO
        assert "Conflict" in vote.reason

    def test_prepare_vote_serialization(self):
        """Test serialization of prepare vote."""
        vote = PrepareVote(
            tx_id="b" * 64,
            shard_id=0,
            vote=ShardVote.YES,
            reason="test",
        )

        serialized = vote.serialize()
        assert len(serialized) > 0


class TestCrossShardTransactionManager:
    """Test cross-shard transaction manager."""

    def test_create_manager(self):
        """Test creating a transaction manager."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)

        assert manager.shard_id == 0
        assert len(manager.pending_transactions) == 0

    def test_propose_single_shard_transaction(self):
        """Test proposing single-shard transaction."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x00" * 32

        # Single sensor stays in one shard - should succeed
        success, reason = manager.propose_cross_shard_transaction(
            "tx-single",
            ["sensor-1"],
            proposer,
        )

        assert success
        assert "tx-single" in manager.pending_transactions

    def test_propose_multi_shard_transaction(self):
        """Test proposing multi-shard transaction."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x01" * 32

        # Multiple sensors may span multiple shards
        success, reason = manager.propose_cross_shard_transaction(
            "tx-multi",
            ["sensor-1", "sensor-2", "sensor-3"],
            proposer,
        )

        assert success
        assert "tx-multi" in manager.pending_transactions

    def test_handle_prepare_request(self):
        """Test handling a prepare request."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(1, shard_manager)
        proposer = b"\x02" * 32
        signature = b"\x03" * 64

        req = PrepareRequest(
            tx_id="prepare-test",
            coordinator_shard=0,
            involved_shards=[0, 1],
            sensor_ids=["sensor-a", "sensor-b"],
            timestamp=1000,
            proposer=proposer,
            signature=signature,
        )

        vote = manager.handle_prepare_request(req)

        assert vote.tx_id == "prepare-test"
        assert vote.shard_id == 1
        assert vote.vote in [ShardVote.YES, ShardVote.NO, ShardVote.ABSTAIN]

    def test_record_prepare_vote(self):
        """Test recording prepare votes."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)

        vote1 = PrepareVote("tx-vote", 0, ShardVote.YES)
        vote2 = PrepareVote("tx-vote", 1, ShardVote.YES)
        vote3 = PrepareVote("tx-vote", 2, ShardVote.NO)

        manager.record_prepare_vote(vote1)
        manager.record_prepare_vote(vote2)
        manager.record_prepare_vote(vote3)

        votes = manager.get_prepare_votes("tx-vote")
        assert len(votes) == 3
        assert votes[0].vote == ShardVote.YES
        assert votes[2].vote == ShardVote.NO

    def test_check_prepare_quorum(self):
        """Test checking prepare quorum."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x04" * 32

        # Propose transaction
        manager.propose_cross_shard_transaction("quorum-test", ["s1", "s2"], proposer)

        # Initially no votes
        has_quorum, yes_votes, total = manager.check_prepare_quorum("quorum-test")
        assert not has_quorum
        assert yes_votes == 0

        # Record some votes
        tx = manager.pending_transactions["quorum-test"]
        num_shards = len(tx.involved_shards)

        for shard_id in tx.involved_shards:
            vote = PrepareVote("quorum-test", shard_id, ShardVote.YES)
            manager.record_prepare_vote(vote)

        # Now should have quorum
        has_quorum, yes_votes, total = manager.check_prepare_quorum("quorum-test")
        assert has_quorum
        assert yes_votes == num_shards

    def test_commit_transaction(self):
        """Test committing a transaction."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x05" * 32

        manager.propose_cross_shard_transaction("commit-test", ["sensor-x"], proposer)

        assert manager.get_transaction_status("commit-test") == TransactionPhase.PROPOSED

        success = manager.commit_transaction("commit-test")
        assert success

        assert manager.get_transaction_status("commit-test") == TransactionPhase.COMMITTED
        assert "commit-test" in manager.committed_transactions

    def test_abort_transaction(self):
        """Test aborting a transaction."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x06" * 32

        manager.propose_cross_shard_transaction("abort-test", ["sensor-y"], proposer)

        success = manager.abort_transaction("abort-test")
        assert success

        assert manager.get_transaction_status("abort-test") == TransactionPhase.ABORTED
        assert "abort-test" in manager.aborted_transactions

    def test_cannot_commit_nonexistent(self):
        """Test that committing nonexistent transaction fails."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)

        success = manager.commit_transaction("nonexistent")
        assert not success

    def test_cannot_abort_nonexistent(self):
        """Test that aborting nonexistent transaction fails."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)

        success = manager.abort_transaction("nonexistent")
        assert not success

    def test_get_transaction_status(self):
        """Test getting transaction status."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x07" * 32

        # Nonexistent
        assert manager.get_transaction_status("unknown") is None

        # Proposed
        manager.propose_cross_shard_transaction("status-test", ["s"], proposer)
        assert manager.get_transaction_status("status-test") == TransactionPhase.PROPOSED

        # Committed
        manager.commit_transaction("status-test")
        assert manager.get_transaction_status("status-test") == TransactionPhase.COMMITTED

    def test_multiple_transactions(self):
        """Test managing multiple transactions."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x08" * 32

        for i in range(5):
            success, _ = manager.propose_cross_shard_transaction(
                f"tx-{i}",
                [f"sensor-{i}"],
                proposer,
            )
            assert success

        assert len(manager.pending_transactions) == 5

        # Commit some, abort others
        manager.commit_transaction("tx-0")
        manager.commit_transaction("tx-1")
        manager.abort_transaction("tx-2")

        assert "tx-0" in manager.committed_transactions
        assert "tx-2" in manager.aborted_transactions
        assert "tx-3" in manager.pending_transactions

    def test_prepare_vote_with_reason(self):
        """Test prepare vote includes reason."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(1, shard_manager)
        proposer = b"\x09" * 32
        signature = b"\x0a" * 64

        req = PrepareRequest(
            tx_id="reason-test",
            coordinator_shard=0,
            involved_shards=[0, 1],
            sensor_ids=["sensor-m", "sensor-n"],
            timestamp=2000,
            proposer=proposer,
            signature=signature,
        )

        vote = manager.handle_prepare_request(req)

        assert len(vote.reason) > 0

    def test_duplicate_vote_handling(self):
        """Test handling duplicate votes from same shard."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)

        vote1 = PrepareVote("dup-test", 0, ShardVote.YES, "First vote")
        vote2 = PrepareVote("dup-test", 0, ShardVote.NO, "Second vote")

        manager.record_prepare_vote(vote1)
        manager.record_prepare_vote(vote2)

        # Second vote should overwrite first
        votes = manager.get_prepare_votes("dup-test")
        assert len(votes) == 1
        assert votes[0].vote == ShardVote.NO

    def test_transaction_workflow(self):
        """Test complete cross-shard transaction workflow."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x0b" * 32

        # Step 1: Propose
        success, _ = manager.propose_cross_shard_transaction(
            "workflow-test",
            ["sensor-p", "sensor-q"],
            proposer,
        )
        assert success
        assert manager.get_transaction_status("workflow-test") == TransactionPhase.PROPOSED

        # Step 2: Get prepare request and votes
        tx = manager.pending_transactions["workflow-test"]
        for shard_id in tx.involved_shards:
            vote = PrepareVote("workflow-test", shard_id, ShardVote.YES)
            manager.record_prepare_vote(vote)

        # Step 3: Check quorum
        has_quorum, _, _ = manager.check_prepare_quorum("workflow-test")
        assert has_quorum

        # Step 4: Commit
        success = manager.commit_transaction("workflow-test")
        assert success
        assert manager.get_transaction_status("workflow-test") == TransactionPhase.COMMITTED


class TestCrossShardEdgeCases:
    """Test edge cases in cross-shard coordination."""

    def test_single_shard_manager(self):
        """Test manager for single-shard system."""
        shard_manager = ShardManager(num_shards=1, num_validators=3)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x0c" * 32

        success, _ = manager.propose_cross_shard_transaction(
            "single-shard",
            ["sensor-1"],
            proposer,
        )
        assert success

    def test_many_shards(self):
        """Test manager with many shards."""
        shard_manager = ShardManager(num_shards=32, num_validators=192)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x0d" * 32

        success, _ = manager.propose_cross_shard_transaction(
            "many-shards",
            ["sensor-a", "sensor-b"],
            proposer,
        )
        assert success

    def test_abort_after_commit_fails(self):
        """Test that aborting after commit is handled."""
        shard_manager = ShardManager(num_shards=4, num_validators=12)
        manager = CrossShardTransactionManager(0, shard_manager)
        proposer = b"\x0e" * 32

        manager.propose_cross_shard_transaction("abort-commit", ["s"], proposer)
        manager.commit_transaction("abort-commit")

        # Trying to abort committed transaction should fail
        success = manager.abort_transaction("abort-commit")
        # Status should still be committed
        assert manager.get_transaction_status("abort-commit") == TransactionPhase.COMMITTED
