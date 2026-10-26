"""Unit tests for transactions."""

import pytest

from src.blockchain import crypto
from src.blockchain.transaction import Transaction, TransactionType, SensorReading


class TestTransactionCreation:
    """Test creating and signing transactions."""

    def test_create_transaction(self):
        """Create a basic transaction."""
        priv, pub = crypto.generate_keypair()

        tx = Transaction(
            nonce=0,
            sender=pub,
            operation=TransactionType.SENSOR_SUBMIT,
            data=b"sensor data",
        )

        assert tx.nonce == 0
        assert tx.sender == pub
        assert tx.operation == TransactionType.SENSOR_SUBMIT
        assert tx.data == b"sensor data"

    def test_transaction_invalid_sender_length(self):
        """Transaction should reject invalid sender length."""
        with pytest.raises(ValueError):
            Transaction(
                nonce=0,
                sender=b"\x00" * 31,  # Should be 32
                operation=TransactionType.SENSOR_SUBMIT,
                data=b"data",
            )

    def test_sign_transaction(self):
        """Sign a transaction."""
        priv, pub = crypto.generate_keypair()

        tx = Transaction(
            nonce=0,
            sender=pub,
            operation=TransactionType.SENSOR_SUBMIT,
            data=b"data",
        )

        tx.sign(priv)

        assert len(tx.signature) == 64
        assert tx.verify()

    def test_verify_signed_transaction(self):
        """Verify a signed transaction."""
        priv, pub = crypto.generate_keypair()

        tx = Transaction(
            nonce=0,
            sender=pub,
            operation=TransactionType.SENSOR_SUBMIT,
            data=b"data",
        )

        tx.sign(priv)
        assert tx.verify()

    def test_tampered_transaction_fails_verification(self):
        """Tampered transaction should fail verification."""
        priv, pub = crypto.generate_keypair()

        tx = Transaction(
            nonce=0,
            sender=pub,
            operation=TransactionType.SENSOR_SUBMIT,
            data=b"original data",
        )

        tx.sign(priv)

        # Tamper with data
        tx.data = b"tampered data"

        assert not tx.verify()

    def test_transaction_hash_consistency(self):
        """Transaction hash should be consistent."""
        priv, pub = crypto.generate_keypair()

        tx = Transaction(
            nonce=0,
            sender=pub,
            operation=TransactionType.SENSOR_SUBMIT,
            data=b"data",
        )
        tx.sign(priv)

        hash1 = tx.hash()
        hash2 = tx.hash()

        assert hash1 == hash2


class TestTransactionSerialization:
    """Test CBOR serialization."""

    def test_serialize_and_deserialize(self):
        """Serialize and deserialize a transaction."""
        priv, pub = crypto.generate_keypair()

        tx = Transaction(
            nonce=1,
            sender=pub,
            operation=TransactionType.SENSOR_SUBMIT,
            data=b"test data",
        )
        tx.sign(priv)

        cbor_bytes = tx.to_cbor()
        tx_restored = Transaction.from_cbor(cbor_bytes)

        assert tx_restored.nonce == tx.nonce
        assert tx_restored.sender == tx.sender
        assert tx_restored.operation == tx.operation
        assert tx_restored.data == tx.data
        assert tx_restored.signature == tx.signature

    def test_without_signature_serialization(self):
        """Serialize without signature for hashing."""
        priv, pub = crypto.generate_keypair()

        tx = Transaction(
            nonce=0,
            sender=pub,
            operation=TransactionType.SENSOR_SUBMIT,
            data=b"data",
        )
        tx.sign(priv)

        cbor_with_sig = tx.to_cbor(include_signature=True)
        cbor_without_sig = tx.to_cbor(include_signature=False)

        assert len(cbor_with_sig) > len(cbor_without_sig)


class TestSensorReading:
    """Test sensor reading encoding."""

    def test_create_sensor_reading(self):
        """Create a sensor reading."""
        reading = SensorReading(
            sensor_id="temp-01",
            timestamp=1234567890,
            sequence_number=0,
            value=23.5,
        )

        assert reading.sensor_id == "temp-01"
        assert reading.value == 23.5

    def test_sensor_reading_serialization(self):
        """Serialize and deserialize sensor reading."""
        reading = SensorReading(
            sensor_id="temp-01",
            timestamp=1234567890,
            sequence_number=5,
            value=23.5,
            schema_version=1,
        )

        cbor_bytes = reading.to_cbor()
        restored = SensorReading.from_cbor(cbor_bytes)

        assert restored.sensor_id == reading.sensor_id
        assert restored.value == reading.value
        assert restored.sequence_number == reading.sequence_number
