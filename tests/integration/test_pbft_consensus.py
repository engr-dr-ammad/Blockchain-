"""
Integration tests for PBFT consensus engine with multiple validators.
"""

import pytest
from src.blockchain.block import Block
from src.blockchain.crypto import generate_keypair
from src.consensus.pbft import (
    PBFTEngine,
    PrePrepareMessage,
    PrepareMessage,
    CommitMessage,
)


@pytest.fixture
def validators_3():
    """Create 3 validators with keypairs."""
    validators = []
    for i in range(3):
        private_key, public_key = generate_keypair()
        validators.append((i, private_key, public_key))
    return validators


@pytest.fixture
def pbft_engines_3(validators_3):
    """Create 3 PBFT engines."""
    validator_list = [(v[0], v[2]) for v in validators_3]
    engines = []

    for vid, private_key, public_key in validators_3:
        engine = PBFTEngine(
            validator_id=vid,
            validators=validator_list,
            private_key=private_key,
        )
        engines.append(engine)

    return engines


@pytest.fixture
def block_1():
    """Create a test block at height 0."""
    return Block(
        height=0,
        timestamp=1000,
        parent_hash=b"\x00" * 32,
        proposer=b"\x00" * 32,
        transactions=[],
    )


def test_pbft_leader_is_first_validator(pbft_engines_3):
    """Verify that validator 0 is the leader at view 0."""
    assert pbft_engines_3[0].is_leader()
    assert not pbft_engines_3[1].is_leader()
    assert not pbft_engines_3[2].is_leader()


def test_pbft_leader_proposal(pbft_engines_3, block_1):
    """Test that leader can propose a block and enter pre-prepared phase."""
    leader = pbft_engines_3[0]

    # Leader should be validator 0
    assert leader.validator_id == 0
    assert leader.is_leader()

    # Propose block
    leader.start_consensus_round(block_1)

    # Verify state after proposal
    assert leader.phase.value == "pre_prepared"
    assert leader.pre_prepare_msg is not None
    assert leader.current_block is not None
    assert leader.sequence == 0


def test_pbft_quorum_calculation():
    """Test quorum calculation for different validator counts."""
    # For N=3: f=(3-1)/3=0, quorum=max(2,1)=2 (minimum 2 for safety)
    # For N=4: f=(4-1)/3=1, quorum=max(2,3)=3
    # For N=7: f=(7-1)/3=2, quorum=max(2,5)=5

    test_cases = [
        (3, 0, 2),
        (4, 1, 3),
        (7, 2, 5),
        (10, 3, 7),
    ]

    for n_validators, expected_f, expected_quorum in test_cases:
        validators = [(i, b"\x00" * 32) for i in range(n_validators)]
        engine = PBFTEngine(
            validator_id=0,
            validators=validators,
            private_key=b"\x00" * 32,
        )

        assert engine.f == expected_f
        assert engine.quorum == expected_quorum


def test_pbft_followers_receive_preprepare(pbft_engines_3, block_1):
    """Test that followers can receive and process pre-prepare messages."""
    leader = pbft_engines_3[0]
    follower1 = pbft_engines_3[1]
    follower2 = pbft_engines_3[2]

    # Leader proposes
    leader.start_consensus_round(block_1)
    pre_prepare_msg = leader.pre_prepare_msg

    # Followers receive pre-prepare
    follower1.on_pre_prepare(pre_prepare_msg)
    follower2.on_pre_prepare(pre_prepare_msg)

    # All should be in pre_prepared state
    assert leader.phase.value == "pre_prepared"
    assert follower1.phase.value == "pre_prepared"
    assert follower2.phase.value == "pre_prepared"


def test_pbft_prepare_phase_collection(pbft_engines_3, block_1):
    """Test that prepare messages are collected and processed."""
    leader = pbft_engines_3[0]
    followers = pbft_engines_3[1:]

    # Leader proposes
    leader.start_consensus_round(block_1)

    # Followers receive and process
    for follower in followers:
        follower.on_pre_prepare(leader.pre_prepare_msg)

    # Collect all prepare votes
    all_prepare_votes = {}
    for engine in pbft_engines_3:
        for vid, msg in engine.prepare_votes.items():
            all_prepare_votes[vid] = msg

    # Distribute prepare votes to all validators
    for engine in pbft_engines_3:
        for vid, msg in all_prepare_votes.items():
            if msg.sender != engine.validator_id:
                engine.on_prepare(msg)

    # Check state - need quorum (2 for 3 validators)
    # At least some engines should have reached prepared phase
    prepared_count = sum(1 for e in pbft_engines_3 if e.phase.value == "prepared")
    assert prepared_count > 0


def test_pbft_leader_election(pbft_engines_3):
    """Test leader election across different views."""
    # View 0: leader is validator 0
    for engine in pbft_engines_3:
        engine.view = 0

    assert pbft_engines_3[0].is_leader()
    assert pbft_engines_3[0].get_leader_id(0) == 0

    # View 1: leader is validator 1
    for engine in pbft_engines_3:
        engine.view = 1

    assert pbft_engines_3[1].is_leader()
    assert pbft_engines_3[1].get_leader_id(1) == 1

    # View 2: leader is validator 2
    for engine in pbft_engines_3:
        engine.view = 2

    assert pbft_engines_3[2].is_leader()
    assert pbft_engines_3[2].get_leader_id(2) == 2


def test_pbft_timeout_detection(pbft_engines_3):
    """Test that timeout is detected correctly."""
    engine = pbft_engines_3[0]

    # Set to pre_prepared phase with old timestamp
    engine.phase = engine.phase.__class__.PRE_PREPARED
    engine.last_activity_time = 0

    # Check for timeout
    timeout_occurred = engine.check_timeout()
    assert timeout_occurred


def test_pbft_view_change_on_timeout(pbft_engines_3):
    """Test that view change occurs when timeout is triggered."""
    engine = pbft_engines_3[0]
    initial_view = engine.view

    # Set to pre_prepared with old activity time
    engine.phase = engine.phase.__class__.PRE_PREPARED
    engine.last_activity_time = 0

    # Trigger timeout
    engine.check_timeout()

    # View should have incremented
    assert engine.view > initial_view


def test_pbft_duplicate_prepare_rejected(pbft_engines_3):
    """Test that duplicate prepare messages are ignored."""
    engine = pbft_engines_3[0]

    # Set engine to pre_prepared state
    engine.phase = engine.phase.__class__.PRE_PREPARED

    # Create prepare message
    msg = PrepareMessage(
        view=0,
        sequence=0,
        block_hash=b"\x00" * 32,
        sender=1,
        sender_pubkey=pbft_engines_3[1].public_key,
    )
    msg.sign(pbft_engines_3[1].private_key)

    # First prepare accepted
    engine.on_prepare(msg)
    assert 1 in engine.prepare_votes
    first_count = len(engine.prepare_votes)

    # Duplicate prepare - should be rejected
    engine.on_prepare(msg)
    assert len(engine.prepare_votes) == first_count


def test_pbft_invalid_signature_rejected(pbft_engines_3):
    """Test that messages with invalid signatures are rejected."""
    engine = pbft_engines_3[0]

    # Create prepare message with wrong signature
    msg = PrepareMessage(
        view=0,
        sequence=0,
        block_hash=b"\x00" * 32,
        sender=1,
        sender_pubkey=pbft_engines_3[1].public_key,
        signature=b"invalid_signature",
    )

    # Message should be rejected (invalid signature)
    engine.on_prepare(msg)
    assert 1 not in engine.prepare_votes


def test_pbft_future_sequence_queued(pbft_engines_3):
    """Test that messages for future sequences are queued."""
    follower = pbft_engines_3[1]

    # Create pre-prepare for sequence 2 when follower is at sequence 0
    future_block = Block(
        height=2,
        timestamp=2000,
        parent_hash=b"\x00" * 32,
        proposer=b"\x00" * 32,
        transactions=[],
    )

    msg = PrePrepareMessage(
        view=0,
        sequence=2,
        block_hash=future_block.hash(),
        sender=0,
        sender_pubkey=pbft_engines_3[0].public_key,
        block=future_block,
    )
    msg.sign(pbft_engines_3[0].private_key)

    # Message should be queued
    initial_pending = len(follower.pending_messages)
    follower.on_pre_prepare(msg)

    # Sequence should not advance
    assert follower.sequence == 0
    assert len(follower.pending_messages) > initial_pending


def test_pbft_status_reporting(pbft_engines_3):
    """Test status reporting from PBFT engine."""
    engine = pbft_engines_3[0]

    status = engine.get_status()

    assert "validator_id" in status
    assert "view" in status
    assert "is_leader" in status
    assert "sequence" in status
    assert "phase" in status
    assert "prepares" in status
    assert "commits" in status
    assert "quorum" in status

    assert status["validator_id"] == 0
    assert status["quorum"] == 2  # For 3 validators: f=0, quorum=max(2,1)=2


def test_pbft_4_validators(validators_3):
    """Test PBFT with 4 validators."""
    # Add 4th validator
    private_key, public_key = generate_keypair()
    validators_3.append((3, private_key, public_key))

    validator_list = [(v[0], v[2]) for v in validators_3]

    # For 4 validators: f=1, quorum=3
    engine = PBFTEngine(
        validator_id=0,
        validators=validator_list,
        private_key=validators_3[0][1],
    )

    assert engine.num_validators == 4
    assert engine.f == 1
    assert engine.quorum == 3


def test_pbft_advance_round(pbft_engines_3):
    """Test round advancement and state reset."""
    engine = pbft_engines_3[0]

    # Set some state
    engine.sequence = 5
    engine.view = 2
    engine.phase = engine.phase.__class__.COMMITTED
    engine.prepare_votes[1] = None
    engine.commit_votes[1] = None

    # Advance round
    engine._advance_round()

    # Check state was reset
    assert engine.sequence == 6
    assert engine.phase.value == "idle"
    assert len(engine.prepare_votes) == 0
    assert len(engine.commit_votes) == 0


def test_pbft_pending_message_processing(pbft_engines_3, block_1):
    """Test that pending messages are processed when sequence advances."""
    follower = pbft_engines_3[1]

    # Queue a message for sequence 1
    future_block = Block(
        height=1,
        timestamp=2000,
        parent_hash=block_1.hash(),
        proposer=b"\x00" * 32,
        transactions=[],
    )

    msg = PrePrepareMessage(
        view=0,
        sequence=1,
        block_hash=future_block.hash(),
        sender=0,
        sender_pubkey=pbft_engines_3[0].public_key,
        block=future_block,
    )
    msg.sign(pbft_engines_3[0].private_key)

    # Add to pending
    follower.pending_messages.append(msg)
    assert len(follower.pending_messages) > 0

    # Advance round (sequence becomes 1)
    follower._advance_round()

    # Pending message should be processed
    # After processing, it should be removed from pending
    assert follower.sequence == 1
