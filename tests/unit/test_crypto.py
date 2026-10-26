"""Unit tests for cryptographic operations."""

import pytest

from src.blockchain import crypto


class TestKeypairGeneration:
    """Test Ed25519 keypair generation."""

    def test_generate_keypair_returns_32_byte_keys(self):
        """Keypair should return 32-byte private and public keys."""
        private_key, public_key = crypto.generate_keypair()

        assert len(private_key) == 32
        assert len(public_key) == 32
        assert isinstance(private_key, bytes)
        assert isinstance(public_key, bytes)

    def test_different_keypairs_are_different(self):
        """Generating new keypairs should give different keys."""
        priv1, pub1 = crypto.generate_keypair()
        priv2, pub2 = crypto.generate_keypair()

        assert priv1 != priv2
        assert pub1 != pub2

    def test_keypair_class(self):
        """Test KeyPair class."""
        priv, pub = crypto.generate_keypair()
        kp = crypto.KeyPair(priv)

        assert kp.private_key == priv
        assert kp.public_key == pub


class TestSigning:
    """Test message signing and verification."""

    def test_sign_and_verify(self):
        """Sign a message and verify it."""
        private_key, public_key = crypto.generate_keypair()
        message = b"test message"

        signature = crypto.sign(message, private_key)

        assert len(signature) == 64
        assert crypto.verify(message, signature, public_key)

    def test_different_messages_have_different_signatures(self):
        """Different messages should produce different signatures."""
        private_key, _ = crypto.generate_keypair()

        sig1 = crypto.sign(b"message 1", private_key)
        sig2 = crypto.sign(b"message 2", private_key)

        assert sig1 != sig2

    def test_signature_deterministic_for_same_key_and_message(self):
        """Signature should be deterministic (Ed25519 property)."""
        private_key, _ = crypto.generate_keypair()
        message = b"test message"

        sig1 = crypto.sign(message, private_key)
        sig2 = crypto.sign(message, private_key)

        assert sig1 == sig2

    def test_tampered_message_fails_verification(self):
        """Verification should fail if message was tampered."""
        private_key, public_key = crypto.generate_keypair()
        message = b"original message"

        signature = crypto.sign(message, private_key)

        # Tamper with message
        tampered = b"tampered message"

        assert not crypto.verify(tampered, signature, public_key)

    def test_invalid_signature_fails(self):
        """Invalid signature should fail verification."""
        _, public_key = crypto.generate_keypair()
        message = b"test message"
        bad_signature = b"\x00" * 64

        assert not crypto.verify(message, bad_signature, public_key)

    def test_wrong_public_key_fails(self):
        """Verification should fail with wrong public key."""
        priv1, _ = crypto.generate_keypair()
        _, pub2 = crypto.generate_keypair()
        message = b"test message"

        signature = crypto.sign(message, priv1)

        assert not crypto.verify(message, signature, pub2)

    def test_invalid_public_key_length_raises(self):
        """Invalid public key length should raise."""
        message = b"test message"
        bad_pubkey = b"\x00" * 31  # Should be 32 bytes

        with pytest.raises(ValueError):
            crypto.verify(message, b"\x00" * 64, bad_pubkey)

    def test_invalid_signature_length_fails(self):
        """Invalid signature length should fail verification."""
        _, public_key = crypto.generate_keypair()
        message = b"test message"
        bad_signature = b"\x00" * 63  # Should be 64 bytes

        assert not crypto.verify(message, bad_signature, public_key)


class TestHashing:
    """Test BLAKE2b hashing."""

    def test_hash_returns_32_bytes(self):
        """Hash should return 32-byte digest."""
        result = crypto.hash(b"test data")

        assert len(result) == 32
        assert isinstance(result, bytes)

    def test_hash_consistency(self):
        """Hash of same data should always be the same."""
        data = b"test data"

        hash1 = crypto.hash(data)
        hash2 = crypto.hash(data)

        assert hash1 == hash2

    def test_different_data_different_hash(self):
        """Different data should produce different hashes."""
        hash1 = crypto.hash(b"data1")
        hash2 = crypto.hash(b"data2")

        assert hash1 != hash2

    def test_empty_data_has_hash(self):
        """Empty data should still produce a valid hash."""
        result = crypto.hash(b"")

        assert len(result) == 32
        assert result != b"\x00" * 32  # Should not be zero hash

    def test_hash_hex(self):
        """Hash hex should be valid hex string."""
        hex_result = crypto.hash_hex(b"test data")

        assert isinstance(hex_result, str)
        assert len(hex_result) == 64  # 32 bytes = 64 hex chars
        assert all(c in "0123456789abcdef" for c in hex_result)

    def test_large_data_hash(self):
        """Hash should work with large data."""
        large_data = b"x" * (10 * 1024 * 1024)  # 10 MB
        result = crypto.hash(large_data)

        assert len(result) == 32


class TestRandomBytes:
    """Test random number generation."""

    def test_random_bytes_correct_length(self):
        """Random bytes should return requested length."""
        result = crypto.random_bytes(32)

        assert len(result) == 32
        assert isinstance(result, bytes)

    def test_random_bytes_are_different(self):
        """Successive random calls should give different values."""
        bytes1 = crypto.random_bytes(32)
        bytes2 = crypto.random_bytes(32)

        assert bytes1 != bytes2


class TestConstants:
    """Test module constants."""

    def test_constants_have_correct_values(self):
        """Constants should have expected values."""
        assert crypto.PRIVATE_KEY_SIZE == 32
        assert crypto.PUBLIC_KEY_SIZE == 32
        assert crypto.SIGNATURE_SIZE == 64
        assert crypto.HASH_SIZE == 32
