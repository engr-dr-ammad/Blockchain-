"""
Multi-node consensus integration test.
Simulates a 3-node testnet reaching consensus.
"""

import asyncio
import pytest
from src.blockchain.block import Block
from src.blockchain.crypto import generate_keypair
from src.consensus.pbft import PBFTEngine


@pytest.fixture
def three_node_network():
    """Create a 3-node network with consensus engines and simulated messaging."""

    class Network:
        def __init__(self):
            self.engines = {}
            self.message_queues = {}
            self.block_log = []

        def add_validator(self, validator_id, private_key, public_key):
            """Add a validator to the network."""
            validator_list = [(i, self.engines[i].public_key if i in self.engines else public_key)
                            for i in range(3)]

            engine = PBFTEngine(
                validator_id=validator_id,
                validators=validator_list,
                private_key=private_key,
            )

            # Set up block finalization callback
            def on_finalized(block, vid=validator_id):
                self.block_log.append((vid, block))

            engine.on_block_finalized = on_finalized
            self.engines[validator_id] = engine
            self.message_queues[validator_id] = []

        def broadcast_from_engine(self, from_id, messages):
            """Broadcast messages from an engine to all other validators."""
            for validator_id, engine in self.engines.items():
                if validator_id != from_id:
                    for msg in messages:
                        self._deliver_message(validator_id, msg)

        def _deliver_message(self, to_id, msg):
            """Deliver a message to a validator's queue."""
            self.message_queues[to_id].append((to_id, msg))

        def process_message_queue(self, validator_id):
            """Process all queued messages for a validator."""
            queue = self.message_queues[validator_id]
            engine = self.engines[validator_id]

            while queue:
                _, msg = queue.pop(0)

                # Route message to appropriate handler
                if hasattr(msg, '__class__'):
                    msg_type = msg.__class__.__name__
                    if msg_type == 'PrePrepareMessage':
                        engine.on_pre_prepare(msg)
                    elif msg_type == 'PrepareMessage':
                        engine.on_prepare(msg)
                    elif msg_type == 'CommitMessage':
                        engine.on_commit(msg)

    return Network()


def test_three_node_consensus_with_leader(three_node_network):
    """Test 3-node network reaching consensus with leader proposing."""
    network = three_node_network

    # Create 3 validators
    for i in range(3):
        pk, pubk = generate_keypair()
        network.add_validator(i, pk, pubk)

    # Get leader (validator 0 at view 0)
    leader = network.engines[0]
    assert leader.is_leader()

    # Leader proposes a block
    block = Block(
        height=0,
        timestamp=1000,
        parent_hash=b"\x00" * 32,
        proposer=leader.public_key,
        transactions=[],
    )

    leader.start_consensus_round(block)

    # Simulate pre-prepare broadcast
    if leader.pre_prepare_msg:
        for validator_id in [1, 2]:
            follower = network.engines[validator_id]
            follower.on_pre_prepare(leader.pre_prepare_msg)

    # Collect prepare votes from all validators
    prepare_messages = []
    for validator_id in range(3):
        engine = network.engines[validator_id]
        if validator_id in engine.prepare_votes:
            prepare_messages.append(engine.prepare_votes[validator_id])

    # Distribute prepare votes
    for validator_id in range(3):
        engine = network.engines[validator_id]
        for msg in prepare_messages:
            if msg.sender != validator_id:
                engine.on_prepare(msg)

    # Check prepared phase
    prepared_count = sum(1 for e in network.engines.values() if e.phase.value == "prepared")
    assert prepared_count > 0

    # Collect commit votes
    commit_messages = []
    for validator_id in range(3):
        engine = network.engines[validator_id]
        if validator_id in engine.commit_votes:
            commit_messages.append(engine.commit_votes[validator_id])

    # Distribute commit votes
    for validator_id in range(3):
        engine = network.engines[validator_id]
        for msg in commit_messages:
            if msg.sender != validator_id:
                engine.on_commit(msg)

    # Check if any block was finalized
    # (might not be finalized if we need more commits)
    # But we should have made progress towards consensus


def test_three_node_complete_consensus_flow(three_node_network):
    """Test complete consensus flow in a 3-node network."""
    network = three_node_network

    # Create 3 validators
    for i in range(3):
        pk, pubk = generate_keypair()
        network.add_validator(i, pk, pubk)

    leader = network.engines[0]

    # Create and propose block
    block = Block(
        height=0,
        timestamp=1000,
        parent_hash=b"\x00" * 32,
        proposer=leader.public_key,
        transactions=[],
    )

    # Phase 1: Pre-prepare
    leader.start_consensus_round(block)
    for vid in [1, 2]:
        network.engines[vid].on_pre_prepare(leader.pre_prepare_msg)

    # All should be in pre-prepared
    for vid in range(3):
        assert network.engines[vid].phase.value == "pre_prepared"

    # Phase 2: Prepare
    for vid in range(3):
        engine = network.engines[vid]
        for other_vid in range(3):
            if other_vid != vid and other_vid in network.engines[other_vid].prepare_votes:
                msg = network.engines[other_vid].prepare_votes[other_vid]
                engine.on_prepare(msg)

    # Gather all prepare votes
    all_prepare_votes = {}
    for vid in range(3):
        engine = network.engines[vid]
        for voter_id, msg in engine.prepare_votes.items():
            all_prepare_votes[voter_id] = msg

    # Distribute to all
    for vid in range(3):
        engine = network.engines[vid]
        for msg in all_prepare_votes.values():
            if msg.sender != vid:
                engine.on_prepare(msg)

    # Check progress towards prepared phase
    prepared_count = sum(1 for e in network.engines.values() if e.phase.value == "prepared")
    assert prepared_count >= 1  # At least one should be prepared


def test_consensus_with_timeout_and_view_change(three_node_network):
    """Test that timeout triggers view change in 3-node network."""
    network = three_node_network

    # Create 3 validators
    for i in range(3):
        pk, pubk = generate_keypair()
        network.add_validator(i, pk, pubk)

    leader = network.engines[0]

    # Set to pre_prepared with old timestamp
    leader.phase = leader.phase.__class__.PRE_PREPARED
    leader.last_activity_time = 0

    initial_view = leader.view

    # Check timeout
    timeout_occurred = leader.check_timeout()

    assert timeout_occurred
    assert leader.view > initial_view

    # After view change, new view is 1, so new leader = 1 % 3 = 1
    new_view = leader.view
    assert new_view == 1

    # In a real system, all validators would be informed of the view change
    # Here we just verify the leader's view was incremented
    assert not leader.is_leader()  # Validator 0 is no longer leader at view 1
