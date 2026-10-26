"""
Transaction structure and validation for IoT-ShardChain.

Transactions are signed operations submitted by clients (sensors or applications).
Each transaction includes a nonce for replay prevention.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import cbor2

from .crypto import hash, sign, verify


class TransactionType(str, Enum):
    """Types of transactions."""
    SENSOR_SUBMIT = "sensor_submit"
    SENSOR_REGISTER = "sensor_register"
    CONTRACT_CALL = "contract_call"


@dataclass
class Transaction:
    """
    A signed transaction ready for inclusion in a block.

    Fields:
        nonce: Monotonic counter per sender (prevents replay attacks)
        sender: Public key of transaction originator (32 bytes)
        operation: Type of transaction (sensor_submit, etc.)
        data: Operation-specific payload (CBOR-encoded)
        signature: Ed25519 signature (64 bytes), set by sign()
    """

    nonce: int
    sender: bytes  # Public key (32 bytes)
    operation: TransactionType
    data: bytes
    signature: bytes = field(default_factory=bytes)

    def __post_init__(self):
        """Validate transaction structure."""
        if not isinstance(self.sender, bytes) or len(self.sender) != 32:
            raise ValueError("sender must be 32-byte public key")
        if not isinstance(self.data, bytes):
            raise ValueError("data must be bytes")
        if self.nonce < 0:
            raise ValueError("nonce must be non-negative")

    def hash(self) -> bytes:
        """Compute transaction hash (for reference, not used in consensus)."""
        return hash(self.to_cbor(include_signature=False))

    def sign(self, private_key: bytes) -> None:
        """
        Sign the transaction with a private key.

        Args:
            private_key: Ed25519 private key (32 bytes)
        """
        message_to_sign = self.to_cbor(include_signature=False)
        self.signature = sign(message_to_sign, private_key)

    def verify(self) -> bool:
        """
        Verify the transaction signature.

        Returns:
            True if signature is valid, False otherwise
        """
        if len(self.signature) != 64:
            return False
        message = self.to_cbor(include_signature=False)
        return verify(message, self.signature, self.sender)

    def is_valid(self) -> bool:
        """
        Check if transaction is well-formed and signed correctly.

        Returns:
            True if valid, False otherwise
        """
        try:
            if len(self.signature) != 64:
                return False
            return self.verify()
        except Exception:
            return False

    def to_cbor(self, include_signature: bool = True) -> bytes:
        """
        Serialize transaction to CBOR format.

        Args:
            include_signature: If True, include signature in output

        Returns:
            CBOR-encoded bytes
        """
        obj = {
            "nonce": self.nonce,
            "sender": self.sender,
            "operation": self.operation.value,
            "data": self.data,
        }
        if include_signature:
            obj["signature"] = self.signature

        return cbor2.dumps(obj)

    @staticmethod
    def from_cbor(cbor_bytes: bytes) -> "Transaction":
        """
        Deserialize transaction from CBOR.

        Args:
            cbor_bytes: CBOR-encoded transaction

        Returns:
            Transaction object

        Raises:
            ValueError: If CBOR is invalid or missing required fields
        """
        obj = cbor2.loads(cbor_bytes)

        try:
            return Transaction(
                nonce=obj["nonce"],
                sender=obj["sender"],
                operation=TransactionType(obj["operation"]),
                data=obj["data"],
                signature=obj.get("signature", b""),
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid transaction CBOR: {e}")


@dataclass
class SensorReading:
    """
    A sensor reading submission (payload of sensor_submit transaction).

    The actual Transaction.data field contains CBOR-encoded SensorReading.

    Fields:
        sensor_id: Identifier of the sensor (e.g., "temp-sensor-01")
        timestamp: Unix milliseconds when reading was taken
        sequence_number: Monotonic counter per sensor (prevents replay within same nonce)
        value: The sensor value (e.g., 23.5 for temperature)
        schema_version: Version of the sensor reading schema
    """

    sensor_id: str
    timestamp: int  # Unix milliseconds
    sequence_number: int
    value: float
    schema_version: int = 1

    def to_cbor(self) -> bytes:
        """Serialize reading to CBOR."""
        obj = {
            "sensor_id": self.sensor_id,
            "timestamp": self.timestamp,
            "sequence": self.sequence_number,
            "value": self.value,
            "schema": self.schema_version,
        }
        return cbor2.dumps(obj)

    @staticmethod
    def from_cbor(cbor_bytes: bytes) -> "SensorReading":
        """Deserialize reading from CBOR."""
        obj = cbor2.loads(cbor_bytes)
        return SensorReading(
            sensor_id=obj["sensor_id"],
            timestamp=obj["timestamp"],
            sequence_number=obj["sequence"],
            value=obj["value"],
            schema_version=obj.get("schema", 1),
        )
