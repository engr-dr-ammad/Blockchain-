"""
Sensor identity and management for IoT-ShardChain.

Provides sensor registration, public key derivation, and signed readings.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum

from src.blockchain.crypto import generate_keypair, sign, verify, hash_hex

logger = logging.getLogger(__name__)


class SensorType(str, Enum):
    """Types of IoT sensors."""
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    PRESSURE = "pressure"
    LIGHT = "light"
    MOTION = "motion"
    DOOR_LOCK = "door_lock"
    WATER_METER = "water_meter"
    POWER_METER = "power_meter"
    CUSTOM = "custom"


class SensorStatus(str, Enum):
    """Sensor registration status."""
    REGISTERED = "registered"
    INACTIVE = "inactive"
    COMPROMISED = "compromised"
    REVOKED = "revoked"


@dataclass
class SensorMetadata:
    """Metadata for a registered sensor."""
    sensor_id: str  # Unique sensor identifier
    sensor_type: SensorType
    public_key: bytes  # Ed25519 public key for signing
    owner_address: bytes  # Address of sensor owner (32 bytes)
    registration_timestamp: int  # Milliseconds since epoch
    status: SensorStatus = SensorStatus.REGISTERED
    metadata: Dict[str, str] = field(default_factory=dict)  # Custom metadata

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "sensor_id": self.sensor_id,
            "sensor_type": self.sensor_type.value,
            "public_key": self.public_key.hex(),
            "owner_address": self.owner_address.hex(),
            "registration_timestamp": self.registration_timestamp,
            "status": self.status.value,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SensorMetadata":
        """Create from dictionary."""
        return cls(
            sensor_id=data["sensor_id"],
            sensor_type=SensorType(data["sensor_type"]),
            public_key=bytes.fromhex(data["public_key"]),
            owner_address=bytes.fromhex(data["owner_address"]),
            registration_timestamp=data["registration_timestamp"],
            status=SensorStatus(data.get("status", "registered")),
            metadata=data.get("metadata", {}),
        )


@dataclass
class SensorReading:
    """A signed reading from a sensor."""
    sensor_id: str
    reading_value: float  # Numeric sensor value
    reading_unit: str  # Unit of measurement (e.g., "celsius", "percent")
    timestamp: int  # Milliseconds since epoch
    nonce: int  # Sequence number for replay prevention
    signature: bytes = field(default_factory=bytes)

    def to_bytes(self) -> bytes:
        """Serialize for signing."""
        return (
            self.sensor_id.encode() +
            str(self.reading_value).encode() +
            self.reading_unit.encode() +
            str(self.timestamp).encode() +
            str(self.nonce).encode()
        )

    def sign(self, private_key: bytes) -> None:
        """Sign the reading with sensor's private key."""
        self.signature = sign(self.to_bytes(), private_key)

    def verify(self, public_key: bytes) -> bool:
        """Verify reading signature with sensor's public key."""
        if not self.signature:
            return False
        return verify(self.to_bytes(), self.signature, public_key)


class SensorRegistry:
    """
    Registry of IoT sensors with cryptographic identities.

    Manages sensor registration, public key storage, and validation.
    """

    def __init__(self):
        """Initialize sensor registry."""
        self.sensors: Dict[str, SensorMetadata] = {}
        self.public_keys: Dict[str, bytes] = {}  # sensor_id -> public_key
        self.sensor_nonces: Dict[str, int] = {}  # sensor_id -> highest nonce seen

        logger.info("Sensor registry initialized")

    def register_sensor(
        self,
        sensor_id: str,
        sensor_type: SensorType,
        owner_address: bytes,
        timestamp: int,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Tuple[bytes, bytes]:
        """
        Register a new sensor with generated keypair.

        Args:
            sensor_id: Unique sensor identifier
            sensor_type: Type of sensor
            owner_address: Address of sensor owner (32 bytes)
            timestamp: Registration timestamp in milliseconds
            metadata: Optional custom metadata

        Returns:
            Tuple of (private_key, public_key)

        Raises:
            ValueError: If sensor already registered or invalid parameters
        """
        if sensor_id in self.sensors:
            raise ValueError(f"Sensor {sensor_id} already registered")

        if len(owner_address) != 32:
            raise ValueError(f"Owner address must be 32 bytes, got {len(owner_address)}")

        # Generate keypair for sensor
        private_key, public_key = generate_keypair()

        # Create metadata
        sensor_meta = SensorMetadata(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            public_key=public_key,
            owner_address=owner_address,
            registration_timestamp=timestamp,
            metadata=metadata or {},
        )

        # Store in registry
        self.sensors[sensor_id] = sensor_meta
        self.public_keys[sensor_id] = public_key
        self.sensor_nonces[sensor_id] = 0  # Start nonce at 0

        logger.info(f"Registered sensor {sensor_id} of type {sensor_type.value}")

        return private_key, public_key

    def register_sensor_with_key(
        self,
        sensor_id: str,
        public_key: bytes,
        sensor_type: SensorType,
        owner_address: bytes,
        timestamp: int,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Register a sensor with a provided public key.

        Useful for importing existing sensor identities.

        Args:
            sensor_id: Unique sensor identifier
            public_key: Sensor's public key (32 bytes)
            sensor_type: Type of sensor
            owner_address: Address of sensor owner (32 bytes)
            timestamp: Registration timestamp in milliseconds
            metadata: Optional custom metadata

        Raises:
            ValueError: If sensor already registered or invalid key
        """
        if sensor_id in self.sensors:
            raise ValueError(f"Sensor {sensor_id} already registered")

        if len(public_key) != 32:
            raise ValueError(f"Public key must be 32 bytes, got {len(public_key)}")

        if len(owner_address) != 32:
            raise ValueError(f"Owner address must be 32 bytes, got {len(owner_address)}")

        sensor_meta = SensorMetadata(
            sensor_id=sensor_id,
            sensor_type=sensor_type,
            public_key=public_key,
            owner_address=owner_address,
            registration_timestamp=timestamp,
            metadata=metadata or {},
        )

        self.sensors[sensor_id] = sensor_meta
        self.public_keys[sensor_id] = public_key
        self.sensor_nonces[sensor_id] = 0

        logger.info(f"Registered sensor {sensor_id} with provided key")

    def get_sensor(self, sensor_id: str) -> Optional[SensorMetadata]:
        """Get sensor metadata by ID."""
        return self.sensors.get(sensor_id)

    def get_public_key(self, sensor_id: str) -> Optional[bytes]:
        """Get sensor's public key."""
        return self.public_keys.get(sensor_id)

    def update_sensor_status(self, sensor_id: str, status: SensorStatus) -> bool:
        """
        Update sensor registration status.

        Useful for deactivating compromised sensors.

        Args:
            sensor_id: Sensor to update
            status: New status

        Returns:
            True if successful, False if sensor not found
        """
        if sensor_id not in self.sensors:
            return False

        self.sensors[sensor_id].status = status
        logger.info(f"Updated sensor {sensor_id} status to {status.value}")
        return True

    def validate_reading(self, reading: SensorReading) -> Tuple[bool, str]:
        """
        Validate a sensor reading.

        Checks:
        - Sensor is registered
        - Sensor is active
        - Signature is valid
        - Nonce is not replayed

        Args:
            reading: Reading to validate

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check sensor exists
        sensor = self.get_sensor(reading.sensor_id)
        if not sensor:
            return False, f"Sensor {reading.sensor_id} not registered"

        # Check sensor is active
        if sensor.status != SensorStatus.REGISTERED:
            return False, f"Sensor {reading.sensor_id} is {sensor.status.value}"

        # Check signature
        if not reading.verify(sensor.public_key):
            return False, f"Invalid signature for sensor {reading.sensor_id}"

        # Check nonce (replay prevention)
        last_nonce = self.sensor_nonces.get(reading.sensor_id, -1)
        if reading.nonce <= last_nonce:
            return False, f"Replay attack: nonce {reading.nonce} <= {last_nonce}"

        return True, "Valid"

    def accept_reading(self, reading: SensorReading) -> bool:
        """
        Accept a validated reading and update nonce tracking.

        Should only be called after validate_reading() returns True.

        Args:
            reading: Reading to accept

        Returns:
            True if accepted
        """
        if reading.sensor_id not in self.sensors:
            return False

        current_nonce = self.sensor_nonces.get(reading.sensor_id, -1)
        if reading.nonce <= current_nonce:
            return False

        self.sensor_nonces[reading.sensor_id] = reading.nonce
        logger.debug(f"Accepted reading from {reading.sensor_id} with nonce {reading.nonce}")
        return True

    def get_sensor_hash(self, sensor_id: str) -> Optional[str]:
        """Get unique hash identifier for sensor."""
        sensor = self.get_sensor(sensor_id)
        if not sensor:
            return None

        # Hash of public key as unique sensor hash
        return hash_hex(sensor.public_key)

    def list_sensors(self, status: Optional[SensorStatus] = None) -> list:
        """
        List all registered sensors.

        Args:
            status: Filter by status (None for all)

        Returns:
            List of sensor metadata
        """
        sensors = list(self.sensors.values())
        if status:
            sensors = [s for s in sensors if s.status == status]
        return sensors

    def get_registry_stats(self) -> dict:
        """Get registry statistics."""
        total = len(self.sensors)
        registered = sum(1 for s in self.sensors.values() if s.status == SensorStatus.REGISTERED)
        inactive = sum(1 for s in self.sensors.values() if s.status == SensorStatus.INACTIVE)
        revoked = sum(1 for s in self.sensors.values() if s.status == SensorStatus.REVOKED)

        return {
            "total_sensors": total,
            "registered": registered,
            "inactive": inactive,
            "revoked": revoked,
            "compromised": total - registered - inactive - revoked,
        }
