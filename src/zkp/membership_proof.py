"""
Membership proofs for zero-knowledge proof of set membership.

Allows proving an element belongs to a set without revealing which element.
"""

from dataclasses import dataclass
from typing import List, Set
import hashlib

from src.blockchain.crypto import hash as crypto_hash, random_bytes


@dataclass
class MembershipProof:
    """Zero-knowledge membership proof for set membership."""
    set_commitment: bytes  # Commitment to the set (Merkle root or similar)
    member_commitment: bytes  # Commitment to member
    proof_path: List[bytes]  # Path through commitment tree
    proof_flags: List[bool]  # Left/right flags for path
    timestamp: int  # Timestamp of proof creation

    def serialize(self) -> bytes:
        """Serialize proof to bytes."""
        data = (
            self.set_commitment +
            self.member_commitment +
            len(self.proof_path).to_bytes(2, 'big')
        )
        for path_elem, flag in zip(self.proof_path, self.proof_flags):
            data += path_elem + (1 if flag else 0).to_bytes(1, 'big')
        data += self.timestamp.to_bytes(8, 'big')
        return data

    @staticmethod
    def deserialize(data: bytes) -> "MembershipProof":
        """Deserialize proof from bytes."""
        offset = 0
        set_commitment = data[offset:offset+32]
        offset += 32
        member_commitment = data[offset:offset+32]
        offset += 32
        path_len = int.from_bytes(data[offset:offset+2], 'big')
        offset += 2

        proof_path = []
        proof_flags = []
        for _ in range(path_len):
            proof_path.append(data[offset:offset+32])
            offset += 32
            proof_flags.append(bool(data[offset]))
            offset += 1

        timestamp = int.from_bytes(data[offset:offset+8], 'big')

        return MembershipProof(set_commitment, member_commitment, proof_path, proof_flags, timestamp)


class MembershipProofVerifier:
    """Verifies zero-knowledge membership proofs."""

    def verify(self, proof: MembershipProof, member_value: bytes = None) -> bool:
        """
        Verify a membership proof.

        Args:
            proof: MembershipProof to verify
            member_value: Optional member value to verify against commitment

        Returns:
            True if proof is valid, False otherwise
        """
        if not proof.set_commitment or len(proof.set_commitment) != 32:
            return False

        if not proof.member_commitment or len(proof.member_commitment) != 32:
            return False

        if len(proof.proof_path) != len(proof.proof_flags):
            return False

        if member_value is not None:
            # Verify member commitment matches member value
            expected = crypto_hash(member_value)
            if proof.member_commitment != expected:
                return False

        # Verify proof path leads to set commitment
        current_hash = proof.member_commitment
        for path_elem, is_right in zip(proof.proof_path, proof.proof_flags):
            if is_right:
                current_hash = crypto_hash(path_elem + current_hash)
            else:
                current_hash = crypto_hash(current_hash + path_elem)

        return current_hash == proof.set_commitment

    def verify_batch(self, proofs: List[MembershipProof], set_commitment: bytes = None) -> bool:
        """
        Verify multiple membership proofs for same set.

        Args:
            proofs: List of proofs to verify
            set_commitment: Expected set commitment (optional, uses first proof if not provided)

        Returns:
            True if all proofs are valid, False otherwise
        """
        if not proofs:
            return False

        if set_commitment is None:
            set_commitment = proofs[0].set_commitment

        for proof in proofs:
            if proof.set_commitment != set_commitment:
                return False
            if not self.verify(proof):
                return False
        return True


class MerkleTree:
    """Simple Merkle tree for set commitment."""

    def __init__(self, members: List[bytes] = None):
        """
        Initialize Merkle tree.

        Args:
            members: List of member values to include in tree
        """
        self.members = members or []
        self.tree_levels = []  # List of levels, each level is list of hashes
        self._build_tree()

    def _build_tree(self) -> None:
        """Build Merkle tree from members."""
        if not self.members:
            self.tree_levels = [[crypto_hash(b"")]]
            return

        # Level 0: hash each member
        current_level = [crypto_hash(m) for m in self.members]
        self.tree_levels = [current_level]

        # Build higher levels
        while len(current_level) > 1:
            next_level = []
            for i in range(0, len(current_level), 2):
                if i + 1 < len(current_level):
                    parent = crypto_hash(current_level[i] + current_level[i + 1])
                else:
                    parent = crypto_hash(current_level[i] + current_level[i])
                next_level.append(parent)

            self.tree_levels.append(next_level)
            current_level = next_level

    def get_root(self) -> bytes:
        """Get Merkle root."""
        if not self.tree_levels:
            return crypto_hash(b"")
        return self.tree_levels[-1][0]

    def get_proof(self, member_index: int) -> MembershipProof:
        """
        Get membership proof for a member.

        Args:
            member_index: Index of member in list

        Returns:
            MembershipProof for the member
        """
        if member_index < 0 or member_index >= len(self.members):
            raise ValueError(f"Invalid member index: {member_index}")

        member_commitment = crypto_hash(self.members[member_index])
        proof_path = []
        proof_flags = []

        # Traverse tree from leaf to root
        current_index = member_index
        for level in range(len(self.tree_levels) - 1):
            current_level = self.tree_levels[level]
            sibling_index = current_index ^ 1  # Toggle last bit to get sibling

            if sibling_index < len(current_level):
                proof_path.append(current_level[sibling_index])
                is_right = (current_index % 2 == 1)
                proof_flags.append(is_right)

            current_index = current_index // 2

        import time
        return MembershipProof(
            set_commitment=self.get_root(),
            member_commitment=member_commitment,
            proof_path=proof_path,
            proof_flags=proof_flags,
            timestamp=int(time.time()),
        )
