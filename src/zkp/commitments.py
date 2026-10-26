"""
Commitment schemes for zero-knowledge proofs.

Pedersen commitments provide hiding and binding properties for constructing ZKPs.
"""

from dataclasses import dataclass
from typing import Tuple
import hashlib

from src.blockchain.crypto import hash as crypto_hash, random_bytes


@dataclass
class CommitmentParams:
    """Parameters for Pedersen commitment scheme."""
    modulus: int = 2**256 - 2**224 + 2**192 + 2**96 - 1  # SECP256K1-like prime


class CommitmentOpening:
    """Opening (witness) to a commitment: value and randomness."""

    def __init__(self, value: int, randomness: bytes):
        """
        Initialize commitment opening.

        Args:
            value: Committed value
            randomness: Random blinding factor (32 bytes)
        """
        if len(randomness) != 32:
            raise ValueError("Randomness must be 32 bytes")
        self.value = value
        self.randomness = randomness

    def serialize(self) -> bytes:
        """Serialize opening to bytes."""
        value_bytes = self.value.to_bytes(32, 'big', signed=True)
        return value_bytes + self.randomness

    @staticmethod
    def deserialize(data: bytes) -> "CommitmentOpening":
        """Deserialize opening from bytes."""
        if len(data) != 64:
            raise ValueError("Opening must be 64 bytes")
        value = int.from_bytes(data[:32], 'big', signed=True)
        randomness = data[32:64]
        return CommitmentOpening(value, randomness)


class PedersenCommitment:
    """
    Pedersen commitment scheme for creating commitments to values.

    Uses hash-based generators for practical efficiency.
    """

    def __init__(self):
        """Initialize Pedersen commitment with parameters."""
        self.params = CommitmentParams()

    def _generate_generator(self, seed: bytes) -> int:
        """Generate a generator from seed using hash."""
        h = hashlib.sha256(seed).digest()
        return int.from_bytes(h, 'big') % (2**255)

    def create_commitment(self, value: int, randomness: bytes = None) -> Tuple[bytes, CommitmentOpening]:
        """
        Create a commitment to a value.

        Args:
            value: Value to commit to
            randomness: Random blinding factor (32 bytes, optional)

        Returns:
            Tuple of (commitment_bytes, opening)
        """
        if randomness is None:
            randomness = random_bytes(32)

        if len(randomness) != 32:
            raise ValueError("Randomness must be 32 bytes")

        # Hash-based Pedersen commitment: C = H(value || randomness)
        commitment_input = value.to_bytes(32, 'big', signed=True) + randomness
        commitment_hash = crypto_hash(commitment_input)

        opening = CommitmentOpening(value, randomness)
        return commitment_hash, opening

    def verify_commitment(self, commitment: bytes, opening: CommitmentOpening) -> bool:
        """
        Verify a commitment against its opening.

        Args:
            commitment: Commitment to verify
            opening: Opening (witness) to commitment

        Returns:
            True if commitment is valid, False otherwise
        """
        try:
            commitment_input = (
                opening.value.to_bytes(32, 'big', signed=True) +
                opening.randomness
            )
            expected = crypto_hash(commitment_input)
            return commitment == expected
        except (ValueError, OverflowError):
            return False

    def blind_value(self, value: int, randomness: bytes) -> bytes:
        """
        Blind a value using randomness.

        Args:
            value: Value to blind
            randomness: Blinding factor (32 bytes)

        Returns:
            Blinded value (32 bytes)
        """
        return crypto_hash(
            value.to_bytes(32, 'big', signed=True) + randomness
        )

    def unblind_value(self, blinded: bytes, randomness: bytes, value: int) -> bool:
        """
        Verify that blinded value matches original.

        Args:
            blinded: Blinded value
            randomness: Blinding factor used
            value: Original value to verify

        Returns:
            True if blinded value is correct, False otherwise
        """
        try:
            expected = self.blind_value(value, randomness)
            return blinded == expected
        except (ValueError, OverflowError):
            return False
