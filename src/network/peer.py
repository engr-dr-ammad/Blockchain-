"""
Peer-to-peer networking for IoT-ShardChain validators.

Handles TCP communication between nodes and message routing to consensus engine.
"""

import asyncio
import json
import logging
from typing import Callable, Dict, Optional, List, Tuple

from src.consensus.pbft import (
    ConsensusMessage,
    PrePrepareMessage,
    PrepareMessage,
    CommitMessage,
)

logger = logging.getLogger(__name__)


class PeerConnection:
    """Outbound connection to a peer validator."""

    def __init__(self, peer_id: int, peer_host: str, peer_port: int):
        """
        Initialize peer connection.

        Args:
            peer_id: Remote validator's ID
            peer_host: Remote host address
            peer_port: Remote port
        """
        self.peer_id = peer_id
        self.peer_host = peer_host
        self.peer_port = peer_port
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.is_connected = False

    async def connect(self) -> bool:
        """
        Connect to remote peer.

        Returns:
            True if connection successful
        """
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.peer_host, self.peer_port),
                timeout=5.0,
            )
            self.is_connected = True
            logger.info(f"Connected to peer {self.peer_id} at {self.peer_host}:{self.peer_port}")
            return True
        except asyncio.TimeoutError:
            logger.warning(f"Timeout connecting to peer {self.peer_id}")
            return False
        except Exception as e:
            logger.error(f"Error connecting to peer {self.peer_id}: {e}")
            return False

    async def send_message(self, message: dict) -> bool:
        """
        Send a message to the peer.

        Args:
            message: Message dictionary to send

        Returns:
            True if sent successfully
        """
        if not self.is_connected or not self.writer:
            return False

        try:
            msg_json = json.dumps(message)
            msg_bytes = msg_json.encode() + b'\n'
            self.writer.write(msg_bytes)
            await self.writer.drain()
            return True
        except Exception as e:
            logger.error(f"Error sending to peer {self.peer_id}: {e}")
            self.is_connected = False
            return False

    async def close(self):
        """Close the connection."""
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception:
                pass
        self.is_connected = False


class PeerServer:
    """Inbound TCP server for receiving messages from peers."""

    def __init__(
        self,
        validator_id: int,
        host: str,
        port: int,
        message_handler: Callable,
    ):
        """
        Initialize peer server.

        Args:
            validator_id: This validator's ID
            host: Listen address
            port: Listen port
            message_handler: Async callback for incoming messages
        """
        self.validator_id = validator_id
        self.host = host
        self.port = port
        self.message_handler = message_handler
        self.server: Optional[asyncio.Server] = None

    async def start(self) -> bool:
        """
        Start the peer server.

        Returns:
            True if server started successfully
        """
        try:
            self.server = await asyncio.start_server(
                self._handle_client,
                self.host,
                self.port,
            )

            async with self.server:
                logger.info(f"Peer server listening on {self.host}:{self.port}")
                # Keep running (handled externally)
                return True
        except Exception as e:
            logger.error(f"Error starting peer server: {e}")
            return False

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ):
        """Handle incoming client connection."""
        peer_addr = writer.get_extra_info('peername')
        logger.info(f"Peer connected from {peer_addr}")

        try:
            while True:
                # Read message (terminated by newline)
                line = await asyncio.wait_for(
                    reader.readuntil(b'\n'),
                    timeout=30.0,
                )

                if not line:
                    break

                try:
                    msg_json = line.decode().strip()
                    message = json.loads(msg_json)
                    await self.message_handler(message)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from peer: {line}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

        except asyncio.TimeoutError:
            logger.info(f"Peer {peer_addr} timed out")
        except asyncio.IncompleteReadError:
            logger.info(f"Peer {peer_addr} disconnected")
        except Exception as e:
            logger.error(f"Error with peer {peer_addr}: {e}")
        finally:
            writer.close()
            await writer.wait_closed()

    async def shutdown(self):
        """Shutdown the server."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()


class PeerNetwork:
    """
    Peer-to-peer network coordinator.

    Manages outbound connections to peers and broadcasts messages.
    """

    def __init__(
        self,
        validator_id: int,
        validators: Dict[int, Tuple[str, int]],  # id -> (host, port)
        host: str,
        port: int,
    ):
        """
        Initialize peer network.

        Args:
            validator_id: This validator's ID
            validators: Dict mapping validator ID to (host, port)
            host: This validator's bind host
            port: This validator's bind port
        """
        self.validator_id = validator_id
        self.validators = validators
        self.host = host
        self.port = port

        # Peer connections (outbound)
        self.peers: Dict[int, PeerConnection] = {}

        # Message handler
        self.on_message: Optional[Callable] = None

        # Server
        self.server: Optional[PeerServer] = None

    async def start(self) -> bool:
        """
        Start the peer network (server and peer connections).

        Returns:
            True if started successfully
        """
        # Create outbound peer connections
        for peer_id, (peer_host, peer_port) in self.validators.items():
            if peer_id == self.validator_id:
                continue  # Don't connect to self

            peer_conn = PeerConnection(peer_id, peer_host, peer_port)
            self.peers[peer_id] = peer_conn

            # Try to connect (non-blocking, retry in background)
            asyncio.create_task(self._connect_peer(peer_id))

        # Start inbound server
        self.server = PeerServer(
            self.validator_id,
            self.host,
            self.port,
            self._handle_incoming_message,
        )

        # Run server in background
        asyncio.create_task(self.server.start())

        logger.info(f"Peer network started: {self.validator_id}")
        return True

    async def _connect_peer(self, peer_id: int, retries: int = 3):
        """Attempt to connect to a peer with retries."""
        peer = self.peers[peer_id]

        for attempt in range(retries):
            if await peer.connect():
                return

            if attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    async def broadcast_message(self, message: dict):
        """
        Broadcast a message to all peers.

        Args:
            message: Message to broadcast
        """
        tasks = []
        for peer in self.peers.values():
            tasks.append(peer.send_message(message))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log failures
        for peer_id, result in zip(self.peers.keys(), results):
            if isinstance(result, Exception) or not result:
                logger.debug(f"Failed to send to peer {peer_id}")

    async def send_to_peer(self, peer_id: int, message: dict) -> bool:
        """
        Send a message to a specific peer.

        Args:
            peer_id: Target peer ID
            message: Message to send

        Returns:
            True if sent successfully
        """
        if peer_id not in self.peers:
            return False

        return await self.peers[peer_id].send_message(message)

    async def _handle_incoming_message(self, message: dict):
        """Handle incoming message from peer."""
        if self.on_message:
            try:
                await self.on_message(message)
            except Exception as e:
                logger.error(f"Error handling message: {e}")

    async def shutdown(self):
        """Shutdown the network."""
        # Close all peer connections
        for peer in self.peers.values():
            await peer.close()

        # Shutdown server
        if self.server:
            await self.server.shutdown()
