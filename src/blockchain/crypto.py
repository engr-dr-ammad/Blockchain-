"""
Cryptographic operations for IoT-ShardChain.

Provides Ed25519 signatures and BLAKE2b hashing using libsodium (PyNaCl) and hashlib.

Reference: https://libsodium.org/
"""

import hashlib
from typing import Tuple

import nacl.signing
import nacl.utils
from nacl.exceptions import BadSignatureError


class KeyPair:
    """An Ed25519 keypair for signing and verification."""

    def __init__(self, private_key_bytes: bytes):
        """
        Initialize keypair from a private key.

        Args:
            private_key_bytes: Raw Ed25519 private key (32 bytes)

        Raises:
            ValueError: If private key is invalid length
        """
        if len(private_key_bytes) != 32:
            raise ValueError("Ed25519 private key must be 32 bytes")

        self._signing_key = nacl.signing.SigningKey(private_key_bytes)

    @property
    def private_key(self) -> bytes:
        """Raw private key bytes (32 bytes)."""
        return bytes(self._signing_key)

    @property
    def public_key(self) -> bytes:
        """Raw public key bytes (32 bytes)."""
        return bytes(self._signing_key.verify_key)

    def sign(self, message: bytes) -> bytes:
        """Sign a message."""
        return bytes(self._signing_key.sign(message).signature)


def generate_keypair() -> Tuple[bytes, bytes]:
    """
    Generate a new Ed25519 keypair.

    Returns:
        Tuple of (private_key, public_key), each 32 bytes
    """
    signing_key = nacl.signing.SigningKey.generate()
    private_bytes = bytes(signing_key)
    public_bytes = bytes(signing_key.verify_key)
    return private_bytes, public_bytes


def sign(message: bytes, private_key: bytes) -> bytes:
    """
    Sign a message with a private key.

    Args:
        message: Data to sign
        private_key: Ed25519 private key (32 bytes)

    Returns:
        Signature (64 bytes)

    Raises:
        ValueError: If private key is invalid
    """
    signing_key = nacl.signing.SigningKey(private_key)
    return bytes(signing_key.sign(message).signature)


def verify(message: bytes, signature: bytes, public_key: bytes) -> bool:
    """
    Verify a signature.

    Args:
        message: Original data
        signature: Ed25519 signature (64 bytes)
        public_key: Ed25519 public key (32 bytes)

    Returns:
        True if signature is valid, False otherwise

    Raises:
        ValueError: If public key is invalid length
    """
    if len(public_key) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")

    if len(signature) != 64:
        return False

    try:
        verify_key = nacl.signing.VerifyKey(public_key)
        verify_key.verify(message, signature)
        return True
    except BadSignatureError:
        return False
    except Exception:
        return False


def hash(data: bytes) -> bytes:
    """
    Compute BLAKE2b-256 hash of data.

    Args:
        data: Data to hash

    Returns:
        Hash digest (32 bytes)
    """
    return hashlib.blake2b(data, digest_size=32).digest()


def hash_hex(data: bytes) -> str:
    """Compute BLAKE2b-256 hash and return as hex string."""
    return hash(data).hex()


def random_bytes(length: int) -> bytes:
    """Generate secure random bytes."""
    return nacl.utils.random(length)


# Constants
PRIVATE_KEY_SIZE = 32
PUBLIC_KEY_SIZE = 32
SIGNATURE_SIZE = 64
HASH_SIZE = 32  # 256-bit hash
