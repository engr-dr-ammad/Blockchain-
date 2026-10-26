# IoT-ShardChain: System Architecture

**Version**: 0.1.0 (Stage 2 - Initial Implementation)
**Status**: Research Platform, Pre-Alpha

## Executive Summary

IoT-ShardChain is a distributed blockchain research platform designed to implement:

1. **Byzantine Fault Tolerant (BFT) consensus** with a permissioned validator set
2. **Sharding** for horizontal scaling of sensor data processing
3. **Zero-knowledge proofs** for privacy-preserving aggregation verification
4. **Cryptographically signed transactions** from IoT sensors

The system runs as multiple independent node processes communicating over TCP/IP, with persistent block storage and a REST API for external applications.

## System Components

### 1. Blockchain Core (`src/blockchain/`)

**Responsibility**: Maintain the immutable ledger, validate transactions, persist state.

**Key Files**:
- `chain.py` — Main blockchain class, manages blocks and state
- `block.py` — Block structure, serialization, hashing
- `transaction.py` — Transaction types, signing, validation
- `crypto.py` — Ed25519 signatures, BLAKE2b hashing
- `storage.py` — Persistent block store (RocksDB)
- `mempool.py` — Transaction queue, duplicate prevention

**Design Decisions**:

| Aspect | Choice | Rationale |
|--------|--------|-----------|
| **Hashing Algorithm** | BLAKE2b | Fast, cryptographically secure, standard |
| **Signature Scheme** | Ed25519 | Quantum-resistant, compact, standard in blockchain |
| **Block Structure** | Height, parent_hash, proposer, timestamp, transactions, merkle_root, state_hash | Standard blockchain structure |
| **Transaction Format** | Sender (public key), operation, data, nonce, signature | Allows replay prevention and verification |
| **Storage** | RocksDB | High performance, ACID properties, embedded |
| **Block Time** | Configurable (default 5s) | Allows testing various finality targets |

### 2. Consensus Engine (`src/consensus/`)

**Responsibility**: Coordinate validators, ensure agreement on block order, implement BFT protocol.

**Protocol**: Practical Byzantine Fault Tolerance (PBFT)

**Key Files**:
- `pbft.py` — PBFT state machine implementation
- `validator.py` — Validator set management, registration
- `view_change.py` — Leader election and view changes on failure
- `message.py` — Pre-prepare, prepare, commit messages

**Design**:

- **Validator Count**: 3-7 nodes (odd number, fault tolerance = ⌊(N-1)/3⌋)
- **Quorum**: ⌈(2N+1)/3⌉ votes required
- **Finality**: Block finalized when 2f+1 commits received
- **View Change**: Triggered on 2f+1 timeout messages

For N=3 validators: tolerance f=0 (no faults), requires unanimous agreement.
For N=4 validators: tolerance f=1 (tolerate 1 failure).
For N=5+ validators: standard BFT tolerance.

### 3. Peer Network (`src/network/`)

**Responsibility**: Node discovery, message routing, peer authentication.

**Key Files**:
- `peer.py` — Outbound peer connection management
- `server.py` — Inbound TCP listener
- `message_handler.py` — Route incoming messages to consensus
- `discovery.py` — Peer discovery (static seed list)

**Design**:

- **Network ID**: Chain-specific identifier prevents cross-network connections
- **Peer Handshake**: Node ID, node name, chain ID, protocol version
- **Message Format**: Varint length prefix + CBOR-encoded message
- **Authentication**: Node public key stored during handshake
- **Timeouts**: 5s connection timeout, 10s message timeout

### 4. Sensor Identity & Submission (`src/sensor/`)

**Responsibility**: Register sensors, validate signed sensor readings, manage credentials.

**Key Files**:
- `sensor_registry.py` — Sensor registration, public key storage
- `sensor_transaction.py` — Signed sensor reading format and validation
- `sensor_simulator.py` — Generate reproducible test datasets

**Design**:

- **Sensor Registration**: Sensor submits (id, public_key, metadata, owner)
- **Sensor Reading**: (sensor_id, timestamp, sequence_num, value, signature, schema_version)
- **Validation**: Verify signature, check sequence number, validate schema
- **Revocation**: Owner can revoke sensor credentials

**Critical Assumption**: Signature verification proves the sensor's private key created the reading, NOT that the reading is truthful. Compromised hardware or stolen keys can produce valid but false readings.

### 5. Sharding Engine (`src/sharding/`)

**Responsibility**: Assign sensors/transactions to shards, route transactions, coordinate cross-shard commits.

**Key Files**:
- `assignment.py` — Deterministic shard assignment rules
- `shard_state.py` — Per-shard state and transaction history
- `coordinator.py` — Cross-shard transaction coordination
- `router.py` — Route transactions to shards

**Design**:

- **Shard Count**: Configurable (default 4)
- **Assignment**: Deterministic hash(sensor_id) % shard_count
- **Shard Versioning**: Assignment rules versioned with block height
- **State Per Shard**: Independent transaction log, balances, state root
- **Cross-Shard**: Atomic commitment requires all shard leaders, explicit timeout handling

### 6. Zero-Knowledge Proofs (`src/zkp/`)

**Responsibility**: Generate and verify privacy-preserving aggregation proofs.

**Key Files**:
- `aggregation.py` — Aggregation function specification
- `proof_system.py` — Proof generation and verification
- `circuit.py` — Zero-knowledge circuit definition

**Design**:

- **Library**: [TBD - to be selected in Stage 6]
- **Public Inputs**: Aggregated values, sensor commitments
- **Private Witness**: Individual sensor readings
- **Statement**: "These readings aggregate to this value and pass validation"
- **Verification**: Independent proof verification on chain

### 7. REST API (`src/api/`)

**Responsibility**: HTTP interface for external clients, block explorer backend.

**Key Files**:
- `api.py` — FastAPI application
- `routes/` — Endpoint implementations
  - `chain.py` — Status, blocks, transactions
  - `sensors.py` — Registration, submission
  - `shards.py` — Shard assignment, status
  - `proofs.py` — Proof verification
  - `benchmarks.py` — Benchmark results

**Endpoints** (comprehensive list in docs/API.md):
- `GET /api/v1/status` — Node and chain status
- `GET /api/v1/blocks` — List blocks
- `POST /api/v1/transactions` — Submit transaction
- `POST /api/v1/sensors/register` — Register sensor
- `POST /api/v1/sensors/submit` — Submit signed reading
- `GET /api/v1/shards/assignments` — Shard assignments

### 8. Web Explorer (`src/explorer/`)

**Responsibility**: Interactive UI for exploring blockchain, sensors, proofs.

Built with React + TypeScript.

**Key Sections**:
- Network overview (node count, block height, TPS)
- Block explorer (blocks, transactions, state changes)
- Transaction explorer (status, inclusion proofs)
- Sensor registry (registered sensors, transaction history)
- Shard visualization (load distribution, assignment changes)
- Proof interface (submit reading, generate proof, verify)

## Data Structures

### Block

```
Block {
  height: u64
  timestamp: i64 (Unix milliseconds)
  proposer: PublicKey (validator who proposed)
  parent_hash: Bytes32
  state_root: Bytes32 (Merkle root of blockchain state)
  transactions: [Transaction]
  merkle_root: Bytes32 (Merkle root of tx list)
  signatures: {validator_pubkey: Signature} (BFT commits)
}
```

### Transaction

```
Transaction {
  nonce: u64 (prevent replays)
  sender: PublicKey (originator)
  operation: TransactionType (sensor_submit, contract_call, etc.)
  data: Bytes (operation-specific payload)
  signature: Signature (Ed25519)
}
```

### Sensor Reading

```
SensorReading {
  sensor_id: String
  timestamp: i64
  sequence_num: u64
  value: f64
  schema_version: u32
  signature: Signature (sensor's Ed25519)
}
```

## Deployment Topology

### Local Development (Docker Compose)

```
docker-compose up
  ├─ node-1:8001 (validator)
  ├─ node-2:8002 (validator)
  └─ node-3:8003 (validator)
```

Each node:
- Runs in separate container
- Has independent RocksDB storage
- Listens on separate ports
- Configured via environment variables

### Production/Testnet Deployment

```
cloud-provider (EC2, GCP, etc.)
  ├─ validator-1 (Ubuntu, Docker)
  ├─ validator-2 (Ubuntu, Docker)
  ├─ validator-3 (Ubuntu, Docker)
  ├─ seed-node (optional, for peer discovery)
  └─ api-node (public REST API)
```

## Configuration

Stored in `config/` directory:

- `genesis.json` — Initial validator set, chain ID, network ID
- `node.yml` — Node-specific settings (port, peer list)
- `.env` — Environment variables (DB path, block time, etc.)

## Security Model

### Threat Assumptions

1. **Network**: Asynchronous network, may partition
2. **Validators**: Up to f out of 2f+1 validators may be Byzantine (arbitrary behavior)
3. **Cryptography**: Ed25519 and BLAKE2b are secure
4. **Sensors**: Private keys may be compromised; readings may be forged
5. **Clients**: API clients assumed honest (no authentication in Stage 2)

### What We Do NOT Guarantee

- **Sensor Truthfulness**: Signatures prove key ownership, not reading accuracy
- **Privacy**: Readings visible to all nodes (encrypted submission in Stage 6)
- **Production Readiness**: Research platform, not audited for production use
- **Quantum Resistance**: Ed25519 vulnerable to quantum computers

### Security Improvements (Staged)

- **Stage 3**: Message authentication codes on peer communication
- **Stage 4**: Sensor API authentication (API keys, OAuth)
- **Stage 5**: Rate limiting and transaction size limits
- **Stage 6**: Encrypted submissions and private aggregation
- **Stage 7**: Audit logging and intrusion detection
- **Stage 8**: Security audit and penetration testing

## Performance Characteristics

### Design Targets (Stage 2-3)

- **Transaction Throughput**: 100-1000 tx/sec (with sharding)
- **Block Time**: 5 seconds (configurable)
- **Finality**: 2-3 blocks (10-15 seconds) for BFT consensus
- **Latency (API)**: <100ms p99
- **Memory per Node**: ~500MB steady-state
- **Storage Growth**: ~1MB/sec (configurable)

### Measured Results

See [TESTING_PLAN.md](TESTING_PLAN.md) for benchmark scenarios and results.

## Known Limitations

1. **Stage 2**: Single leader per round (not fully BFT yet)
2. **Stage 2**: No cross-shard transactions
3. **Stage 2**: No ZKP integration
4. **Stage 3+**: Transaction finality may stall on > f validator failures
5. **All stages**: Peer discovery is static seed list (not DHT)
6. **All stages**: No transaction fee mechanism
7. **All stages**: No smart contract VM

## File Structure

```
Blockchain-/
├── README.md                      # This file
├── CONTRIBUTING.md                # Development guidelines
├── docs/
│   ├── ARCHITECTURE.md           # This document
│   ├── RESEARCH_MAPPING.md        # Research-to-code mapping
│   ├── CONSENSUS.md              # PBFT protocol details
│   ├── THREAT_MODEL.md           # Security analysis
│   ├── ROADMAP.md                # Implementation roadmap
│   ├── TESTING_PLAN.md           # Test scenarios and benchmarks
│   ├── API.md                    # REST API documentation
│   └── DEPLOYMENT.md             # Testnet deployment guide
├── src/
│   ├── blockchain/               # Core ledger and transactions
│   ├── consensus/                # BFT consensus engine
│   ├── network/                  # Peer communication
│   ├── sensor/                   # Sensor identity and readings
│   ├── sharding/                 # Sharding engine
│   ├── zkp/                      # Zero-knowledge proofs
│   ├── api/                      # REST API
│   └── explorer/                 # Web UI
├── tests/
│   ├── unit/                     # Unit tests
│   ├── integration/              # Multi-node tests
│   ├── e2e/                      # End-to-end tests
│   └── benchmarks/               # Performance benchmarks
├── docker/
│   ├── Dockerfile                # Multi-stage container build
│   ├── compose.dev.yml           # 3-node local dev testnet
│   └── compose.testnet.yml       # 5+ node testnet
├── config/
│   ├── genesis.json              # Initial chain state
│   ├── node.yml                  # Node configuration template
│   └── .env.example              # Environment variables
├── .gitignore
├── .github/
│   └── workflows/
│       ├── test.yml              # Run tests on PR
│       └── security.yml          # Security checks
└── requirements.txt              # Python dependencies
```

## Next Steps (Stage 2)

1. ✅ Repository structure established
2. 🔄 Implement blockchain core (blocks, transactions, storage)
3. 🔄 Implement consensus engine (leader election, finality)
4. 🔄 Implement peer network (discovery, sync)
5. 🔄 Docker Compose configuration
6. 🔄 Automated tests
7. 🔄 Documentation

See [ROADMAP.md](ROADMAP.md) for detailed implementation order.
