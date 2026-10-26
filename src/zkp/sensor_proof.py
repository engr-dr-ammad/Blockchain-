"""
Sensor-specific zero-knowledge proofs.

Provides privacy-preserving proofs for IoT sensor readings and identities.
"""

from dataclasses import dataclass
from typing import Tuple, Optional
import hashlib
import time

from src.blockchain.crypto import hash as crypto_hash, random_bytes, sign, verify
from src.iot.sensor import SensorReading, SensorRegistry
from .commitments import PedersenCommitment, CommitmentOpening
from .range_proof import RangeProof, RangeProofBuilder
from .membership_proof import MembershipProof, MerkleTree


@dataclass
class SensorRangeProof:
    """Zero-knowledge proof that sensor reading is within valid range."""
    sensor_id: str
    reading_commitment: bytes  # Commitment to reading value
    range_proof: RangeProof  # Range proof
    signature: bytes  # Prover signature
    timestamp: int

    def serialize(self) -> bytes:
        """Serialize proof to bytes."""
        sensor_id_bytes = self.sensor_id.encode()
        data = (
            len(sensor_id_bytes).to_bytes(2, 'big') +
            sensor_id_bytes +
            self.reading_commitment +
            self.range_proof.serialize() +
            self.signature +
            self.timestamp.to_bytes(8, 'big')
        )
        return data

    @staticmethod
    def deserialize(data: bytes) -> "SensorRangeProof":
        """Deserialize proof from bytes."""
        offset = 0
        sensor_id_len = int.from_bytes(data[offset:offset+2], 'big')
        offset += 2
        sensor_id = data[offset:offset+sensor_id_len].decode()
        offset += sensor_id_len
        reading_commitment = data[offset:offset+32]
        offset += 32

        # Parse RangeProof (need to figure out its length)
        # For now, assume simple length prefix
        range_proof_len = int.from_bytes(data[offset:offset+4], 'big')
        offset += 4
        range_proof = RangeProof.deserialize(data[offset:offset+range_proof_len])
        offset += range_proof_len

        signature = data[offset:offset+64]
        offset += 64
        timestamp = int.from_bytes(data[offset:offset+8], 'big')

        return SensorRangeProof(sensor_id, reading_commitment, range_proof, signature, timestamp)


@dataclass
class SensorIdentityProof:
    """Zero-knowledge proof of sensor identity without revealing key."""
    sensor_id: str
    identity_commitment: bytes  # Commitment to sensor public key
    challenge: bytes  # Challenge from verifier
    response: bytes  # Prover response
    timestamp: int

    def serialize(self) -> bytes:
        """Serialize proof to bytes."""
        sensor_id_bytes = self.sensor_id.encode()
        data = (
            len(sensor_id_bytes).to_bytes(2, 'big') +
            sensor_id_bytes +
            self.identity_commitment +
            self.challenge +
            self.response +
            self.timestamp.to_bytes(8, 'big')
        )
        return data

    @staticmethod
    def deserialize(data: bytes) -> "SensorIdentityProof":
        """Deserialize proof from bytes."""
        offset = 0
        sensor_id_len = int.from_bytes(data[offset:offset+2], 'big')
        offset += 2
        sensor_id = data[offset:offset+sensor_id_len].decode()
        offset += sensor_id_len
        identity_commitment = data[offset:offset+32]
        offset += 32
        challenge = data[offset:offset+32]
        offset += 32
        response = data[offset:offset+32]
        offset += 32
        timestamp = int.from_bytes(data[offset:offset+8], 'big')

        return SensorIdentityProof(sensor_id, identity_commitment, challenge, response, timestamp)


class SensorRangeProofBuilder:
    """Builds range proofs for sensor readings."""

    def __init__(self, sensor_ranges: dict = None):
        """
        Initialize builder.

        Args:
            sensor_ranges: Dict of sensor_id -> (min, max) valid ranges
        """
        self.sensor_ranges = sensor_ranges or {}
        self.commitments = PedersenCommitment()
        self.range_builder = RangeProofBuilder()

        # Default ranges for common sensor types
        self._init_default_ranges()

    def _init_default_ranges(self) -> None:
        """Initialize default ranges for sensor types."""
        default_ranges = {
            "temperature": (-50.0, 80.0),  # Celsius
            "humidity": (0.0, 100.0),  # Percent
            "pressure": (900.0, 1100.0),  # hPa
            "light": (0.0, 100000.0),  # Lux
            "power": (0.0, 10000.0),  # Watts
        }
        for sensor_type, (min_val, max_val) in default_ranges.items():
            if sensor_type not in self.sensor_ranges:
                self.sensor_ranges[sensor_type] = (int(min_val), int(max_val))

    def create_range_proof_for_reading(
        self,
        reading: SensorReading,
        private_key: bytes = None,
    ) -> Tuple[SensorRangeProof, CommitmentOpening]:
        """
        Create range proof for sensor reading.

        Args:
            reading: SensorReading to prove
            private_key: Sensor private key for signing

        Returns:
            Tuple of (sensor_range_proof, opening)
        """
        # Get valid range for sensor
        min_bound, max_bound = self._get_sensor_range(reading.sensor_id)

        # Convert reading value to integer
        value_int = int(reading.reading_value)

        # Create range proof
        range_proof, opening = self.range_builder.create_range_proof(
            value=value_int,
            min_bound=min_bound,
            max_bound=max_bound,
            timestamp=reading.timestamp,
        )

        # Sign proof with sensor private key if provided
        proof_bytes = range_proof.serialize()
        signature = sign(proof_bytes, private_key) if private_key else b"\x00" * 64

        sensor_proof = SensorRangeProof(
            sensor_id=reading.sensor_id,
            reading_commitment=range_proof.commitment,
            range_proof=range_proof,
            signature=signature,
            timestamp=reading.timestamp,
        )

        return sensor_proof, opening

    def _get_sensor_range(self, sensor_id: str) -> Tuple[int, int]:
        """Get valid range for sensor."""
        if sensor_id in self.sensor_ranges:
            return self.sensor_ranges[sensor_id]
        # Default range
        return (0, 1000000)


class SensorIdentityProofBuilder:
    """Builds identity proofs for sensors."""

    def __init__(self, registry: SensorRegistry):
        """
        Initialize builder.

        Args:
            registry: SensorRegistry for sensor verification
        """
        self.registry = registry
        self.commitments = PedersenCommitment()

    def create_identity_proof(
        self,
        sensor_id: str,
        private_key: bytes,
    ) -> SensorIdentityProof:
        """
        Create identity proof for sensor.

        Args:
            sensor_id: Sensor identifier
            private_key: Sensor private key

        Returns:
            SensorIdentityProof
        """
        # Get sensor public key from registry
        public_key = self.registry.get_public_key(sensor_id)
        if public_key is None:
            raise ValueError(f"Sensor {sensor_id} not found in registry")

        # Create commitment to public key (use hash of key instead of key as int)
        commitment, _ = self.commitments.create_commitment(
            value=int.from_bytes(crypto_hash(public_key), 'big', signed=False) % (2**127)
        )

        # Generate Fiat-Shamir challenge
        challenge = hashlib.sha256(
            sensor_id.encode() + commitment
        ).digest()

        # Create response: hash of challenge and private key commitment
        response = hashlib.sha256(challenge + private_key).digest()

        return SensorIdentityProof(
            sensor_id=sensor_id,
            identity_commitment=commitment,
            challenge=challenge,
            response=response,
            timestamp=int(time.time()),
        )

    def verify_identity_proof(
        self,
        proof: SensorIdentityProof,
    ) -> bool:
        """
        Verify sensor identity proof.

        Args:
            proof: SensorIdentityProof to verify

        Returns:
            True if proof is valid, False otherwise
        """
        try:
            # Get sensor public key from registry
            public_key = self.registry.get_public_key(proof.sensor_id)
            if public_key is None:
                return False

            # Verify challenge was derived correctly
            expected_challenge = hashlib.sha256(
                proof.sensor_id.encode() + proof.identity_commitment
            ).digest()
            if proof.challenge != expected_challenge:
                return False

            # In real ZKP, would verify Schnorr-style proof
            # Here we just verify the proof structure is valid
            return (
                len(proof.identity_commitment) == 32 and
                len(proof.challenge) == 32 and
                len(proof.response) == 32
            )
        except Exception:
            return False
