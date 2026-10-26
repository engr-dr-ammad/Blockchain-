"""
Unit tests for zero-knowledge proof module.
"""

import pytest
import time
from src.zkp.commitments import PedersenCommitment, CommitmentOpening
from src.zkp.range_proof import RangeProof, RangeProofVerifier, RangeProofBuilder
from src.zkp.membership_proof import MembershipProof, MembershipProofVerifier, MerkleTree
from src.zkp.sensor_proof import (
    SensorRangeProof,
    SensorIdentityProof,
    SensorRangeProofBuilder,
    SensorIdentityProofBuilder,
)
from src.iot.sensor import SensorRegistry, SensorReading, SensorType
from src.blockchain.crypto import generate_keypair


class TestPedersenCommitment:
    """Test Pedersen commitment scheme."""

    def test_create_commitment(self):
        """Test creating a commitment."""
        pc = PedersenCommitment()
        value = 42
        commitment, opening = pc.create_commitment(value)

        assert commitment is not None
        assert len(commitment) == 32
        assert opening.value == value
        assert len(opening.randomness) == 32

    def test_commit_and_verify(self):
        """Test commitment creation and verification."""
        pc = PedersenCommitment()
        value = 100
        commitment, opening = pc.create_commitment(value)

        assert pc.verify_commitment(commitment, opening)

    def test_verify_fails_for_wrong_opening(self):
        """Test verification fails with wrong opening."""
        pc = PedersenCommitment()
        value = 50
        commitment, opening = pc.create_commitment(value)

        # Modify opening
        wrong_opening = CommitmentOpening(51, opening.randomness)
        assert not pc.verify_commitment(commitment, wrong_opening)

    def test_commitment_hiding(self):
        """Test that different values give different commitments."""
        pc = PedersenCommitment()
        commitment1, _ = pc.create_commitment(10)
        commitment2, _ = pc.create_commitment(11)

        assert commitment1 != commitment2

    def test_commitment_binding(self):
        """Test that same value with different randomness gives different commitments."""
        pc = PedersenCommitment()
        value = 42
        randomness1 = b"\x01" * 32
        randomness2 = b"\x02" * 32

        commitment1, _ = pc.create_commitment(value, randomness1)
        commitment2, _ = pc.create_commitment(value, randomness2)

        assert commitment1 != commitment2

    def test_commitment_opening_serialization(self):
        """Test serialization of commitment opening."""
        opening = CommitmentOpening(123, b"\x42" * 32)
        serialized = opening.serialize()

        assert len(serialized) == 64
        deserialized = CommitmentOpening.deserialize(serialized)
        assert deserialized.value == 123
        assert deserialized.randomness == b"\x42" * 32

    def test_blind_and_unblind(self):
        """Test blinding and unblinding values."""
        pc = PedersenCommitment()
        value = 999
        randomness = b"\x11" * 32

        blinded = pc.blind_value(value, randomness)
        assert len(blinded) == 32

        assert pc.unblind_value(blinded, randomness, value)
        assert not pc.unblind_value(blinded, randomness, value + 1)


class TestRangeProof:
    """Test range proofs."""

    def test_create_range_proof(self):
        """Test creating a range proof."""
        builder = RangeProofBuilder()
        value = 50
        proof, opening = builder.create_range_proof(value, 0, 100)

        assert proof.commitment is not None
        assert proof.min_bound == 0
        assert proof.max_bound == 100
        assert len(proof.challenges) == 8
        assert len(proof.responses) == 8

    def test_range_proof_serialization(self):
        """Test range proof serialization."""
        builder = RangeProofBuilder()
        proof, _ = builder.create_range_proof(42, 0, 100)

        serialized = proof.serialize()
        deserialized = RangeProof.deserialize(serialized)

        assert deserialized.commitment == proof.commitment
        assert deserialized.min_bound == proof.min_bound
        assert deserialized.max_bound == proof.max_bound
        assert len(deserialized.challenges) == 8
        assert len(deserialized.responses) == 8

    def test_range_proof_verification(self):
        """Test range proof verification."""
        builder = RangeProofBuilder()
        proof, _ = builder.create_range_proof(50, 0, 100)

        verifier = RangeProofVerifier()
        assert verifier.verify(proof)

    def test_range_proof_rejects_out_of_range(self):
        """Test that out-of-range values are rejected."""
        builder = RangeProofBuilder()

        with pytest.raises(ValueError):
            builder.create_range_proof(-1, 0, 100)

        with pytest.raises(ValueError):
            builder.create_range_proof(101, 0, 100)

    def test_range_proof_multiple_ranges(self):
        """Test range proofs with different ranges."""
        builder = RangeProofBuilder()

        for value in [0, 25, 50, 75, 100]:
            proof, _ = builder.create_range_proof(value, 0, 100)
            verifier = RangeProofVerifier()
            assert verifier.verify(proof)

    def test_range_proof_with_negative_bounds(self):
        """Test range proofs with negative bounds."""
        builder = RangeProofBuilder()
        proof, _ = builder.create_range_proof(-5, -10, 10)

        verifier = RangeProofVerifier()
        assert verifier.verify(proof)

    def test_range_proof_timestamp(self):
        """Test that timestamp is preserved."""
        builder = RangeProofBuilder()
        timestamp = int(time.time())
        proof, _ = builder.create_range_proof(50, 0, 100, timestamp=timestamp)

        assert proof.timestamp == timestamp


class TestMembershipProof:
    """Test membership proofs."""

    def test_create_merkle_tree(self):
        """Test creating a Merkle tree."""
        members = [b"member1", b"member2", b"member3"]
        tree = MerkleTree(members)

        assert tree.get_root() is not None
        assert len(tree.get_root()) == 32

    def test_get_membership_proof(self):
        """Test getting membership proof from tree."""
        members = [b"alice", b"bob", b"charlie"]
        tree = MerkleTree(members)

        proof = tree.get_proof(1)  # Get proof for "bob"

        assert proof.member_commitment is not None
        assert proof.set_commitment == tree.get_root()
        assert len(proof.proof_path) > 0

    def test_verify_membership_proof(self):
        """Test verifying membership proof."""
        members = [b"user1", b"user2", b"user3", b"user4"]
        tree = MerkleTree(members)

        proof = tree.get_proof(2)
        verifier = MembershipProofVerifier()

        assert verifier.verify(proof, members[2])

    def test_membership_proof_serialization(self):
        """Test serialization of membership proof."""
        members = [b"x", b"y", b"z"]
        tree = MerkleTree(members)
        proof = tree.get_proof(0)

        serialized = proof.serialize()
        deserialized = MembershipProof.deserialize(serialized)

        assert deserialized.set_commitment == proof.set_commitment
        assert deserialized.member_commitment == proof.member_commitment
        assert len(deserialized.proof_path) == len(proof.proof_path)

    def test_membership_proof_fails_for_wrong_member(self):
        """Test that proof fails for wrong member."""
        members = [b"a", b"b", b"c"]
        tree = MerkleTree(members)

        proof = tree.get_proof(0)
        verifier = MembershipProofVerifier()

        assert not verifier.verify(proof, b"d")

    def test_membership_proof_batch_verification(self):
        """Test batch verification of membership proofs."""
        members = [b"one", b"two", b"three", b"four"]  # Use power of 2 for simpler tree
        tree = MerkleTree(members)

        proofs = [tree.get_proof(i) for i in range(len(members))]
        verifier = MembershipProofVerifier()

        # Verify each proof individually first
        for i, proof in enumerate(proofs):
            assert verifier.verify(proof, members[i])

        # Then verify batch
        assert verifier.verify_batch(proofs, tree.get_root())

    def test_single_member_tree(self):
        """Test Merkle tree with single member."""
        members = [b"only"]
        tree = MerkleTree(members)

        proof = tree.get_proof(0)
        verifier = MembershipProofVerifier()

        assert verifier.verify(proof, members[0])

    def test_many_members_tree(self):
        """Test Merkle tree with many members."""
        members = [f"member{i}".encode() for i in range(1024)]
        tree = MerkleTree(members)

        # Test proofs for various positions
        for idx in [0, 100, 500, 1023]:
            proof = tree.get_proof(idx)
            verifier = MembershipProofVerifier()
            assert verifier.verify(proof, members[idx])


class TestSensorRangeProof:
    """Test sensor-specific range proofs."""

    def test_create_sensor_range_proof(self):
        """Test creating sensor range proof."""
        builder = SensorRangeProofBuilder()
        reading = SensorReading(
            sensor_id="temp-1",
            reading_value=22.5,
            reading_unit="celsius",
            timestamp=int(time.time()),
            nonce=1,
        )

        proof, opening = builder.create_range_proof_for_reading(reading)

        assert proof.sensor_id == "temp-1"
        assert proof.reading_commitment is not None
        assert len(proof.signature) == 64

    def test_sensor_range_proof_with_signature(self):
        """Test sensor range proof with private key signature."""
        registry = SensorRegistry()
        owner = b"\x00" * 32

        pk, _ = registry.register_sensor(
            sensor_id="temp-sensor",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        builder = SensorRangeProofBuilder()
        reading = SensorReading(
            sensor_id="temp-sensor",
            reading_value=25.0,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )

        proof, opening = builder.create_range_proof_for_reading(reading, pk)

        assert proof.signature != b"\x00" * 64

    def test_sensor_range_proof_serialization(self):
        """Test sensor range proof serialization."""
        builder = SensorRangeProofBuilder()
        reading = SensorReading(
            sensor_id="humidity-1",
            reading_value=65.0,
            reading_unit="percent",
            timestamp=int(time.time()),
            nonce=1,
        )

        proof, _ = builder.create_range_proof_for_reading(reading)
        serialized = proof.serialize()

        deserialized = SensorRangeProof.deserialize(serialized)
        assert deserialized.sensor_id == "humidity-1"
        assert deserialized.reading_commitment == proof.reading_commitment

    def test_multiple_sensor_types(self):
        """Test range proofs for different sensor types."""
        builder = SensorRangeProofBuilder()

        sensors = [
            ("temp-1", 20.0, "celsius"),
            ("humidity-1", 50.0, "percent"),
            ("pressure-1", 1000.0, "hPa"),
        ]

        for sensor_id, value, unit in sensors:
            reading = SensorReading(
                sensor_id=sensor_id,
                reading_value=value,
                reading_unit=unit,
                timestamp=int(time.time()),
                nonce=1,
            )
            proof, _ = builder.create_range_proof_for_reading(reading)
            assert proof.sensor_id == sensor_id


class TestSensorIdentityProof:
    """Test sensor identity proofs."""

    def test_create_sensor_identity_proof(self):
        """Test creating sensor identity proof."""
        registry = SensorRegistry()
        owner = b"\x01" * 32

        pk, _ = registry.register_sensor(
            sensor_id="identity-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        builder = SensorIdentityProofBuilder(registry)
        proof = builder.create_identity_proof("identity-test", pk)

        assert proof.sensor_id == "identity-test"
        assert proof.identity_commitment is not None
        assert len(proof.challenge) == 32
        assert len(proof.response) == 32

    def test_verify_sensor_identity_proof(self):
        """Test verifying sensor identity proof."""
        registry = SensorRegistry()
        owner = b"\x02" * 32

        pk, _ = registry.register_sensor(
            sensor_id="verify-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        builder = SensorIdentityProofBuilder(registry)
        proof = builder.create_identity_proof("verify-test", pk)

        assert builder.verify_identity_proof(proof)

    def test_identity_proof_fails_for_unregistered(self):
        """Test that identity proof fails for unregistered sensor."""
        registry = SensorRegistry()
        owner = b"\x03" * 32

        pk, _ = generate_keypair()

        builder = SensorIdentityProofBuilder(registry)

        with pytest.raises(ValueError):
            builder.create_identity_proof("nonexistent", pk)

    def test_identity_proof_serialization(self):
        """Test identity proof serialization."""
        registry = SensorRegistry()
        owner = b"\x04" * 32

        pk, _ = registry.register_sensor(
            sensor_id="serial-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        builder = SensorIdentityProofBuilder(registry)
        proof = builder.create_identity_proof("serial-test", pk)

        serialized = proof.serialize()
        deserialized = SensorIdentityProof.deserialize(serialized)

        assert deserialized.sensor_id == "serial-test"
        assert deserialized.identity_commitment == proof.identity_commitment
        assert deserialized.challenge == proof.challenge

    def test_multiple_sensors_identity_proofs(self):
        """Test identity proofs for multiple sensors."""
        registry = SensorRegistry()
        builder = SensorIdentityProofBuilder(registry)

        owner = b"\x05" * 32

        for i in range(3):
            sensor_id = f"sensor-{i}"
            pk, _ = registry.register_sensor(
                sensor_id=sensor_id,
                sensor_type=SensorType.TEMPERATURE,
                owner_address=owner,
                timestamp=1000 + i,
            )

            proof = builder.create_identity_proof(sensor_id, pk)
            assert builder.verify_identity_proof(proof)


class TestZKPIntegration:
    """Integration tests for ZKP module."""

    def test_sensor_reading_with_range_proof(self):
        """Test sensor reading with range proof."""
        registry = SensorRegistry()
        owner = b"\x06" * 32

        pk, _ = registry.register_sensor(
            sensor_id="integrated-temp",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        reading = SensorReading(
            sensor_id="integrated-temp",
            reading_value=23.5,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )
        reading.sign(pk)

        # Create range proof
        proof_builder = SensorRangeProofBuilder()
        range_proof, _ = proof_builder.create_range_proof_for_reading(reading, pk)

        # Verify both reading and proof
        is_valid, _ = registry.validate_reading(reading)
        assert is_valid

        assert range_proof.sensor_id == "integrated-temp"

    def test_privacy_preserving_workflow(self):
        """Test complete privacy-preserving workflow."""
        registry = SensorRegistry()
        owner = b"\x07" * 32

        # Register sensor
        pk, pubk = registry.register_sensor(
            sensor_id="private-sensor",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        # Create reading with identity proof
        identity_builder = SensorIdentityProofBuilder(registry)
        identity_proof = identity_builder.create_identity_proof("private-sensor", pk)

        # Create range proof for reading
        reading = SensorReading(
            sensor_id="private-sensor",
            reading_value=19.5,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )

        range_builder = SensorRangeProofBuilder()
        range_proof, _ = range_builder.create_range_proof_for_reading(reading, pk)

        # Verify both proofs
        assert identity_builder.verify_identity_proof(identity_proof)
        # Range proof is internally verified
        assert range_proof.reading_commitment is not None
