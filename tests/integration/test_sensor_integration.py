"""
Integration tests for sensor readings with blockchain.
Tests end-to-end sensor identity, readings, and validation.
"""

import pytest
import tempfile
import shutil
from src.blockchain.chain import Blockchain
from src.iot.sensor import SensorType, SensorStatus, SensorReading


@pytest.fixture
def blockchain():
    """Create a temporary blockchain for testing."""
    tmpdir = tempfile.mkdtemp()
    bc = Blockchain(tmpdir, genesis_timestamp=1000)
    yield bc
    bc.close()
    shutil.rmtree(tmpdir)


class TestSensorBlockchainIntegration:
    """Test sensor integration with blockchain."""

    def test_register_sensor_via_blockchain(self, blockchain):
        """Test registering sensor through blockchain."""
        owner = b"\x00" * 32

        registry = blockchain.get_sensor_registry()
        pk, pubk = registry.register_sensor(
            sensor_id="temp-1",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=2000,
        )

        # Verify registered
        sensor = registry.get_sensor("temp-1")
        assert sensor is not None
        assert sensor.sensor_id == "temp-1"

    def test_sensor_reading_validation_through_blockchain(self, blockchain):
        """Test validating sensor readings through blockchain."""
        owner = b"\x01" * 32
        registry = blockchain.get_sensor_registry()

        # Register sensor
        pk, _ = registry.register_sensor(
            sensor_id="humidity-1",
            sensor_type=SensorType.HUMIDITY,
            owner_address=owner,
            timestamp=2000,
        )

        # Create reading
        reading = SensorReading(
            sensor_id="humidity-1",
            reading_value=55.0,
            reading_unit="percent",
            timestamp=3000,
            nonce=1,
        )
        reading.sign(pk)

        # Validate through blockchain
        is_valid, reason = blockchain.validate_sensor_reading(reading)
        assert is_valid
        assert reason == "Valid"

    def test_sensor_reading_acceptance_tracking(self, blockchain):
        """Test that blockchain tracks accepted sensor readings."""
        owner = b"\x02" * 32
        registry = blockchain.get_sensor_registry()

        pk, _ = registry.register_sensor(
            sensor_id="pressure-1",
            sensor_type=SensorType.PRESSURE,
            owner_address=owner,
            timestamp=2000,
        )

        # Create first reading
        reading1 = SensorReading(
            sensor_id="pressure-1",
            reading_value=1013.25,
            reading_unit="hPa",
            timestamp=3000,
            nonce=1,
        )
        reading1.sign(pk)

        # Accept first reading
        is_valid, _ = blockchain.validate_sensor_reading(reading1)
        assert is_valid
        blockchain.accept_sensor_reading(reading1)

        # Try to replay - should be rejected
        reading2 = SensorReading(
            sensor_id="pressure-1",
            reading_value=1013.25,
            reading_unit="hPa",
            timestamp=3000,
            nonce=1,  # Same nonce
        )
        reading2.sign(pk)

        is_valid, reason = blockchain.validate_sensor_reading(reading2)
        assert not is_valid
        assert "Replay attack" in reason

    def test_multiple_sensors_independent_nonces(self, blockchain):
        """Test that different sensors have independent nonce tracking."""
        owner = b"\x03" * 32
        registry = blockchain.get_sensor_registry()

        # Register two sensors
        pk1, _ = registry.register_sensor(
            sensor_id="light-1",
            sensor_type=SensorType.LIGHT,
            owner_address=owner,
            timestamp=2000,
        )

        pk2, _ = registry.register_sensor(
            sensor_id="light-2",
            sensor_type=SensorType.LIGHT,
            owner_address=owner,
            timestamp=2100,
        )

        # Send reading from sensor 1 with nonce 1
        reading1 = SensorReading(
            sensor_id="light-1",
            reading_value=500.0,
            reading_unit="lux",
            timestamp=3000,
            nonce=1,
        )
        reading1.sign(pk1)
        blockchain.accept_sensor_reading(reading1)

        # Send reading from sensor 2 with nonce 1 (should work - different sensor)
        reading2 = SensorReading(
            sensor_id="light-2",
            reading_value=600.0,
            reading_unit="lux",
            timestamp=3100,
            nonce=1,
        )
        reading2.sign(pk2)

        is_valid, _ = blockchain.validate_sensor_reading(reading2)
        assert is_valid  # Should be valid - different sensor

    def test_sensor_status_affects_validation(self, blockchain):
        """Test that sensor status affects reading validation."""
        owner = b"\x04" * 32
        registry = blockchain.get_sensor_registry()

        pk, _ = registry.register_sensor(
            sensor_id="motion-1",
            sensor_type=SensorType.MOTION,
            owner_address=owner,
            timestamp=2000,
        )

        # Create valid reading
        reading = SensorReading(
            sensor_id="motion-1",
            reading_value=1.0,  # Motion detected
            reading_unit="binary",
            timestamp=3000,
            nonce=1,
        )
        reading.sign(pk)

        # Should be valid initially
        is_valid, _ = blockchain.validate_sensor_reading(reading)
        assert is_valid

        # Deactivate sensor
        registry.update_sensor_status("motion-1", SensorStatus.INACTIVE)

        # Should be invalid now
        is_valid, reason = blockchain.validate_sensor_reading(reading)
        assert not is_valid
        assert "inactive" in reason

    def test_sensor_sequence_validation(self, blockchain):
        """Test that sensors can send multiple readings with increasing nonces."""
        owner = b"\x05" * 32
        registry = blockchain.get_sensor_registry()

        pk, _ = registry.register_sensor(
            sensor_id="power-1",
            sensor_type=SensorType.POWER_METER,
            owner_address=owner,
            timestamp=2000,
        )

        # Send sequence of readings
        for nonce in range(1, 5):
            reading = SensorReading(
                sensor_id="power-1",
                reading_value=float(nonce * 100),  # 100, 200, 300, 400
                reading_unit="watts",
                timestamp=3000 + nonce * 100,
                nonce=nonce,
            )
            reading.sign(pk)

            # Each should be valid
            is_valid, reason = blockchain.validate_sensor_reading(reading)
            assert is_valid, f"Reading {nonce} failed: {reason}"

            # Accept it
            blockchain.accept_sensor_reading(reading)

    def test_sensor_registry_statistics(self, blockchain):
        """Test retrieving sensor registry statistics."""
        owner = b"\x06" * 32
        registry = blockchain.get_sensor_registry()

        # Register several sensors
        for i in range(3):
            registry.register_sensor(
                sensor_id=f"sensor-{i}",
                sensor_type=SensorType.TEMPERATURE,
                owner_address=owner,
                timestamp=2000 + i,
            )

        # Deactivate one
        registry.update_sensor_status("sensor-1", SensorStatus.INACTIVE)

        stats = registry.get_registry_stats()
        assert stats["total_sensors"] == 3
        assert stats["registered"] == 2
        assert stats["inactive"] == 1

        # Also check through blockchain
        stats2 = blockchain.get_sensor_registry().get_registry_stats()
        assert stats == stats2

    def test_sensor_reading_with_custom_type(self, blockchain):
        """Test sensor readings with custom sensor type."""
        owner = b"\x07" * 32
        registry = blockchain.get_sensor_registry()

        pk, _ = registry.register_sensor(
            sensor_id="custom-1",
            sensor_type=SensorType.CUSTOM,
            owner_address=owner,
            timestamp=2000,
            metadata={"device_model": "custom-v1", "manufacturer": "test"},
        )

        reading = SensorReading(
            sensor_id="custom-1",
            reading_value=42.5,
            reading_unit="custom_unit",
            timestamp=3000,
            nonce=1,
        )
        reading.sign(pk)

        is_valid, _ = blockchain.validate_sensor_reading(reading)
        assert is_valid

    def test_blockchain_chain_height_with_sensors(self, blockchain):
        """Test that blockchain chain height is maintained with sensor activity."""
        initial_height = blockchain.get_height()

        owner = b"\x08" * 32
        registry = blockchain.get_sensor_registry()

        # Register sensor
        pk, _ = registry.register_sensor(
            sensor_id="height-test",
            sensor_type=SensorType.TEMPERATURE,
            owner_address=owner,
            timestamp=2000,
        )

        # Create reading
        reading = SensorReading(
            sensor_id="height-test",
            reading_value=25.0,
            reading_unit="celsius",
            timestamp=3000,
            nonce=1,
        )
        reading.sign(pk)

        # Validate reading (shouldn't affect chain height)
        blockchain.validate_sensor_reading(reading)

        # Chain height should be unchanged (sensor registry is separate)
        assert blockchain.get_height() == initial_height
