"""
Unit tests for IoT sensor identity and registry.
"""

import pytest
import time
from src.iot.sensor import (
    SensorRegistry,
    SensorReading,
    SensorType,
    SensorStatus,
)
from src.blockchain.crypto import generate_keypair, sign


class TestSensorRegistration:
    """Test sensor registration."""

    def test_register_sensor(self):
        """Test basic sensor registration."""
        registry = SensorRegistry()
        owner = b"\x00" * 32

        private_key, public_key = registry.register_sensor(
            sensor_id="temp-sensor-1",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        assert len(private_key) == 32
        assert len(public_key) == 32

        # Verify registered
        sensor = registry.get_sensor("temp-sensor-1")
        assert sensor is not None
        assert sensor.sensor_id == "temp-sensor-1"
        assert sensor.sensor_type == SensorType.TEMPERATURE
        assert sensor.public_key == public_key

    def test_register_sensor_with_metadata(self):
        """Test sensor registration with metadata."""
        registry = SensorRegistry()
        owner = b"\x01" * 32
        metadata = {"location": "room-1", "firmware": "v1.2.3"}

        _, _ = registry.register_sensor(
            sensor_id="humid-sensor-1",
            sensor_type=SensorType.HUMIDITY,
            owner_address=owner,
            timestamp=2000,
            metadata=metadata,
        )

        sensor = registry.get_sensor("humid-sensor-1")
        assert sensor.metadata == metadata

    def test_register_duplicate_sensor_fails(self):
        """Test that duplicate sensor registration fails."""
        registry = SensorRegistry()
        owner = b"\x02" * 32

        registry.register_sensor(
            sensor_id="sensor-1",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        # Try to register again
        with pytest.raises(ValueError, match="already registered"):
            registry.register_sensor(
                sensor_id="sensor-1",
                sensor_type=SensorType.HUMIDITY,
                owner_address=owner,
                timestamp=2000,
            )

    def test_register_sensor_with_key(self):
        """Test registering sensor with provided public key."""
        registry = SensorRegistry()
        owner = b"\x03" * 32
        pk, pubk = generate_keypair()

        registry.register_sensor_with_key(
            sensor_id="sensor-external",
            public_key=pubk,
            sensor_type=SensorType.LIGHT,
            owner_address=owner,
            timestamp=3000,
        )

        sensor = registry.get_sensor("sensor-external")
        assert sensor.public_key == pubk

    def test_invalid_owner_address_length(self):
        """Test that invalid owner address is rejected."""
        registry = SensorRegistry()

        with pytest.raises(ValueError, match="32 bytes"):
            registry.register_sensor(
                sensor_id="bad-sensor",
                sensor_type=SensorType.TEMPERATURE,
                owner_address=b"short",
                timestamp=1000,
            )

    def test_invalid_public_key_length(self):
        """Test that invalid public key is rejected."""
        registry = SensorRegistry()
        owner = b"\x04" * 32

        with pytest.raises(ValueError, match="32 bytes"):
            registry.register_sensor_with_key(
                sensor_id="bad-key",
                public_key=b"invalid",
                sensor_type=SensorType.TEMPERATURE,
                owner_address=owner,
                timestamp=1000,
            )


class TestSensorReading:
    """Test sensor readings and signing."""

    def test_create_sensor_reading(self):
        """Test creating a sensor reading."""
        reading = SensorReading(
            sensor_id="sensor-1",
            reading_value=22.5,
            reading_unit="celsius",
            timestamp=1000,
            nonce=1,
        )

        assert reading.sensor_id == "sensor-1"
        assert reading.reading_value == 22.5
        assert reading.nonce == 1

    def test_sign_and_verify_reading(self):
        """Test signing and verifying sensor readings."""
        registry = SensorRegistry()
        owner = b"\x05" * 32

        pk, pubk = registry.register_sensor(
            sensor_id="sign-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        reading = SensorReading(
            sensor_id="sign-test",
            reading_value=20.0,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )

        # Sign reading
        reading.sign(pk)
        assert reading.signature

        # Verify reading
        assert reading.verify(pubk)

    def test_tampered_reading_fails_verification(self):
        """Test that tampered reading fails verification."""
        registry = SensorRegistry()
        owner = b"\x06" * 32

        pk, pubk = registry.register_sensor(
            sensor_id="tamper-test",
            sensor_type=SensorType.HUMIDITY,
            owner_address=owner,
            timestamp=1000,
        )

        reading = SensorReading(
            sensor_id="tamper-test",
            reading_value=65.0,
            reading_unit="percent",
            timestamp=2000,
            nonce=1,
        )

        reading.sign(pk)

        # Tamper with reading
        reading.reading_value = 99.0

        # Verification should fail
        assert not reading.verify(pubk)

    def test_unsigned_reading_fails_verification(self):
        """Test that unsigned reading fails verification."""
        pk, pubk = generate_keypair()

        reading = SensorReading(
            sensor_id="unsigned",
            reading_value=50.0,
            reading_unit="percent",
            timestamp=1000,
            nonce=1,
        )

        # Verify without signature
        assert not reading.verify(pubk)


class TestSensorValidation:
    """Test sensor reading validation."""

    def test_validate_valid_reading(self):
        """Test validation of valid reading."""
        registry = SensorRegistry()
        owner = b"\x07" * 32

        pk, _ = registry.register_sensor(
            sensor_id="valid-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        reading = SensorReading(
            sensor_id="valid-test",
            reading_value=25.0,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )
        reading.sign(pk)

        is_valid, reason = registry.validate_reading(reading)
        assert is_valid
        assert reason == "Valid"

    def test_validate_unregistered_sensor(self):
        """Test validation rejects unregistered sensor."""
        registry = SensorRegistry()

        reading = SensorReading(
            sensor_id="unknown",
            reading_value=10.0,
            reading_unit="celsius",
            timestamp=1000,
            nonce=1,
        )

        is_valid, reason = registry.validate_reading(reading)
        assert not is_valid
        assert "not registered" in reason

    def test_validate_invalid_signature(self):
        """Test validation rejects invalid signature."""
        registry = SensorRegistry()
        owner = b"\x08" * 32

        pk1, _ = registry.register_sensor(
            sensor_id="sig-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        # Sign with different key
        pk2, _ = generate_keypair()

        reading = SensorReading(
            sensor_id="sig-test",
            reading_value=15.0,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )
        reading.sign(pk2)  # Sign with wrong key

        is_valid, reason = registry.validate_reading(reading)
        assert not is_valid
        assert "Invalid signature" in reason

    def test_validate_inactive_sensor(self):
        """Test validation rejects inactive sensor."""
        registry = SensorRegistry()
        owner = b"\x09" * 32

        pk, _ = registry.register_sensor(
            sensor_id="inactive-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        # Deactivate sensor
        registry.update_sensor_status("inactive-test", SensorStatus.INACTIVE)

        reading = SensorReading(
            sensor_id="inactive-test",
            reading_value=20.0,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )
        reading.sign(pk)

        is_valid, reason = registry.validate_reading(reading)
        assert not is_valid
        assert "inactive" in reason

    def test_validate_replay_attack_rejected(self):
        """Test that replay attack is detected and rejected."""
        registry = SensorRegistry()
        owner = b"\x0a" * 32

        pk, _ = registry.register_sensor(
            sensor_id="replay-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        # Create and accept first reading
        reading1 = SensorReading(
            sensor_id="replay-test",
            reading_value=20.0,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )
        reading1.sign(pk)

        is_valid, _ = registry.validate_reading(reading1)
        assert is_valid
        registry.accept_reading(reading1)

        # Try to replay same reading
        reading2 = SensorReading(
            sensor_id="replay-test",
            reading_value=20.0,
            reading_unit="celsius",
            timestamp=2000,
            nonce=1,
        )
        reading2.sign(pk)

        is_valid, reason = registry.validate_reading(reading2)
        assert not is_valid
        assert "Replay attack" in reason

    def test_validate_old_nonce_rejected(self):
        """Test that old nonce is rejected."""
        registry = SensorRegistry()
        owner = b"\x0b" * 32

        pk, _ = registry.register_sensor(
            sensor_id="nonce-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        # Accept reading with nonce 5
        reading1 = SensorReading(
            sensor_id="nonce-test",
            reading_value=20.0,
            reading_unit="celsius",
            timestamp=2000,
            nonce=5,
        )
        reading1.sign(pk)
        registry.accept_reading(reading1)

        # Try reading with lower nonce
        reading2 = SensorReading(
            sensor_id="nonce-test",
            reading_value=25.0,
            reading_unit="celsius",
            timestamp=3000,
            nonce=3,
        )
        reading2.sign(pk)

        is_valid, reason = registry.validate_reading(reading2)
        assert not is_valid
        assert "Replay attack" in reason


class TestSensorStatus:
    """Test sensor status management."""

    def test_update_sensor_status(self):
        """Test updating sensor status."""
        registry = SensorRegistry()
        owner = b"\x0c" * 32

        registry.register_sensor(
            sensor_id="status-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        # Initial status should be REGISTERED
        sensor = registry.get_sensor("status-test")
        assert sensor.status == SensorStatus.REGISTERED

        # Update to INACTIVE
        success = registry.update_sensor_status("status-test", SensorStatus.INACTIVE)
        assert success

        sensor = registry.get_sensor("status-test")
        assert sensor.status == SensorStatus.INACTIVE

    def test_update_nonexistent_sensor_fails(self):
        """Test updating nonexistent sensor fails."""
        registry = SensorRegistry()

        success = registry.update_sensor_status("nonexistent", SensorStatus.REVOKED)
        assert not success


class TestSensorRegistry:
    """Test sensor registry operations."""

    def test_get_public_key(self):
        """Test retrieving sensor public key."""
        registry = SensorRegistry()
        owner = b"\x0d" * 32

        _, pubk = registry.register_sensor(
            sensor_id="pubkey-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        retrieved_key = registry.get_public_key("pubkey-test")
        assert retrieved_key == pubk

    def test_get_sensor_hash(self):
        """Test getting sensor hash."""
        registry = SensorRegistry()
        owner = b"\x0e" * 32

        _, pubk = registry.register_sensor(
            sensor_id="hash-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        sensor_hash = registry.get_sensor_hash("hash-test")
        assert sensor_hash is not None
        assert len(sensor_hash) == 64  # Hex string of 32 bytes

    def test_list_sensors(self):
        """Test listing sensors."""
        registry = SensorRegistry()
        owner = b"\x0f" * 32

        for i in range(3):
            registry.register_sensor(
                sensor_id=f"list-test-{i}",
                sensor_type=SensorType.TEMPERATURE,
                owner_address=owner,
                timestamp=1000 + i,
            )

        sensors = registry.list_sensors()
        assert len(sensors) == 3

    def test_list_sensors_by_status(self):
        """Test listing sensors filtered by status."""
        registry = SensorRegistry()
        owner = b"\x10" * 32

        registry.register_sensor(
            sensor_id="active-1",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=1000,
        )

        _, _ = registry.register_sensor(
            sensor_id="inactive-1",
            sensor_type=SensorType.HUMIDITY,
            owner_address=owner,
            timestamp=2000,
        )
        registry.update_sensor_status("inactive-1", SensorStatus.INACTIVE)

        active_sensors = registry.list_sensors(SensorStatus.REGISTERED)
        assert len(active_sensors) == 1
        assert active_sensors[0].sensor_id == "active-1"

    def test_registry_stats(self):
        """Test registry statistics."""
        registry = SensorRegistry()
        owner = b"\x11" * 32

        # Register 3 sensors
        for i in range(3):
            registry.register_sensor(
                sensor_id=f"stat-test-{i}",
                sensor_type=SensorType.TEMPERATURE,
                owner_address=owner,
                timestamp=1000 + i,
            )

        # Deactivate one
        registry.update_sensor_status("stat-test-1", SensorStatus.INACTIVE)

        stats = registry.get_registry_stats()
        assert stats["total_sensors"] == 3
        assert stats["registered"] == 2
        assert stats["inactive"] == 1
