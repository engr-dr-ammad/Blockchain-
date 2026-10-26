# Implementation Roadmap

**Version**: 1.0
**Status**: Stage 1 Planning

## Implementation Stages Overview

This roadmap details the order, dependencies, and deliverables for each implementation stage.

```
Stage 1 (COMPLETE)
  └─ docs/ARCHITECTURE.md, RESEARCH_MAPPING.md, CONSENSUS.md, THREAT_MODEL.md
  
Stage 2 (IN PROGRESS)
  ├─ Block structure, transactions, hashing
  ├─ Cryptographic signing (Ed25519)
  ├─ Persistent storage (RocksDB)
  ├─ Mempool and transaction pool
  └─ Local Docker testnet (3 nodes)
  
Stage 3
  ├─ PBFT consensus engine
  ├─ Validator set and quorum
  ├─ View change and leader election
  ├─ Peer network (TCP, handshake, sync)
  └─ Multi-node consensus tests
  
Stage 4
  ├─ Sensor identity registry
  ├─ Sensor registration endpoint
  ├─ Signed sensor submission
  ├─ Replay attack prevention
  └─ Sensor simulator
  
Stage 5
  ├─ Sharding engine (assignment, routing)
  ├─ Shard-specific state
  ├─ Cross-shard coordination
  ├─ Shard load balancing
  └─ Sharding benchmarks
  
Stage 6
  ├─ Zero-knowledge proof system
  ├─ Aggregation proof generation
  ├─ Proof verification
  ├─ Privacy-preserving aggregation tests
  └─ Proof performance benchmarks
  
Stage 7
  ├─ REST API (comprehensive)
  ├─ Python SDK
  ├─ Web explorer (React)
  ├─ Proof submission UI
  └─ Developer documentation
  
Stage 8
  ├─ Performance benchmarks (all scenarios)
  ├─ Security testing (adversarial)
  ├─ Testnet deployment guide
  ├─ GitHub Actions CI/CD
  └─ Public testnet launch
```

## Stage 2: Minimal Blockchain Core

**Duration**: ~2-3 weeks
**Goal**: Establish foundational ledger mechanics; support a 3-node local testnet.

### Components to Build

#### 2.1 Block Structure & Serialization (`src/blockchain/block.py`)

**Deliverables**:
- `Block` class: height, parent_hash, timestamp, proposer, transactions, merkle_root, state_root, signatures
- Serialization to CBOR (deterministic)
- Deserialization from CBOR
- Merkle tree construction (transaction root)
- State root calculation (trie or simple hash)
- Block validation (height, parent, timestamps, signatures)

**Tests**:
- ✅ Block creation and serialization
- ✅ Round-trip serialization (Block → CBOR → Block)
- ✅ Hash consistency (same block, same hash)
- ✅ Invalid block rejection (bad height, bad parent)

**Acceptance Criteria**:
- All tests passing
- 100% code coverage
- Documentation of Block schema

#### 2.2 Transactions & Signing (`src/blockchain/transaction.py`)

**Deliverables**:
- `Transaction` class: nonce, sender (public key), operation, data, signature
- Transaction types (enum): `sensor_submit`, `contract_call`, etc.
- Ed25519 signature generation
- Signature verification
- Transaction validation (signature, nonce, field types)
- Serialization to CBOR

**Tests**:
- ✅ Sign transaction with private key
- ✅ Verify signature with public key
- ✅ Reject invalid signature
- ✅ Nonce field stored (not yet enforced)

**Acceptance Criteria**:
- All tests passing
- Ed25519 signatures reproducible
- Malformed transactions rejected

#### 2.3 Cryptography Module (`src/blockchain/crypto.py`)

**Deliverables**:
- Ed25519 key generation (nacl.signing)
- Sign/verify operations
- BLAKE2b hashing (hashlib)
- Public key serialization (hex/bytes)
- Secure random number generation

**Tests**:
- ✅ Key generation creates valid key pair
- ✅ Sign → Verify round-trip
- ✅ Different messages → different signatures
- ✅ Hash consistency

**Dependencies**: `nacl`, `hashlib` (both standard)

#### 2.4 Persistent Storage (`src/blockchain/storage.py`)

**Deliverables**:
- RocksDB database initialization
- Block storage (key: height, value: block CBOR)
- Block retrieval by height
- Index (height → hash) for validation
- State trie or simple state storage
- Database flush and checkpoint

**Tests**:
- ✅ Store block, retrieve block, verify equality
- ✅ Sequential block storage (height 0, 1, 2, ...)
- ✅ Retrieve non-existent block (graceful failure)
- ✅ Database recovery after crash (use journal log)

**Acceptance Criteria**:
- All tests passing
- Multi-process concurrent access safe (RocksDB guarantees)

#### 2.5 Blockchain Core (`src/blockchain/chain.py`)

**Deliverables**:
- `Blockchain` class managing block list and state
- Genesis block creation
- Block appending (with validation)
- State transitions (apply/revert)
- Head/tip tracking (latest block)
- Merkle tree of blocks (not just transactions)

**Tests**:
- ✅ Genesis block created correctly
- ✅ Blocks appended in order
- ✅ Block validation on append (invalid blocks rejected)
- ✅ State updated as blocks apply
- ✅ Persistence across restarts

#### 2.6 Mempool (`src/blockchain/mempool.py`)

**Deliverables**:
- Transaction pool (queue of pending transactions)
- Duplicate transaction detection (same nonce from same sender)
- Eviction policy (oldest first, or by fee in Stage 5)
- Batch fetching for block proposal (top N transactions)
- Nonce tracking per sender (to prevent locally-duplicated submissions)

**Tests**:
- ✅ Add transaction
- ✅ Reject duplicate (same sender, same nonce)
- ✅ Evict oldest on size limit
- ✅ Retrieve top N transactions in nonce order

#### 2.7 Docker Configuration

**Deliverables**:
- `docker/Dockerfile` — Multi-stage build for minimal image
- `docker/compose.dev.yml` — 3-node testnet with shared network
- Environment variables for each node (node ID, port, peer list, block time)
- Volume mounts for persistent storage
- Health checks (node status endpoint)

**Example**:
```yaml
version: '3.8'
services:
  node-1:
    build: .
    environment:
      NODE_ID: node-1
      NODE_PORT: 8001
      PEERS: node-2:8002,node-3:8003
      DB_PATH: /data/node-1
    volumes:
      - node-1-data:/data
    ports:
      - "8001:8001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 10s
  # ... node-2, node-3 similar
```

### Minimal API (Stage 2)

**Deliverables**:
- `GET /health` — Node status (is_running, height)
- `GET /blocks/{height}` — Retrieve block by height
- `GET /blocks` — List blocks (paginated)
- `POST /transactions` — Submit transaction
- `GET /transactions/{id}` — Transaction status
- `GET /status` — Chain status (height, block hash, tip)

**No authentication or rate limiting yet** (added in Stage 5-7).

### Tests (`tests/`)

**Unit Tests** (`tests/unit/`):
- Block serialization/deserialization
- Transaction signing/verification
- Storage read/write
- Mempool operations

**Integration Tests** (`tests/integration/`):
- Multi-block chain creation
- Persistent storage recovery
- Mempool → block proposal flow

**Local Testnet Test** (`tests/e2e/test_stage2.py`):
```python
def test_3_node_local_testnet():
    """Start 3 nodes locally, verify they are running."""
    docker_compose_up("docker/compose.dev.yml")
    
    # Query node-1
    status_1 = requests.get("http://localhost:8001/status").json()
    assert status_1["height"] >= 0
    assert status_1["node_id"] == "node-1"
    
    # Query node-2
    status_2 = requests.get("http://localhost:8002/status").json()
    assert status_2["height"] >= 0
    
    # Query node-3
    status_3 = requests.get("http://localhost:8003/status").json()
    assert status_3["height"] >= 0
    
    docker_compose_down("docker/compose.dev.yml")
```

### Acceptance Criteria

- ✅ Block structure fully specified and tested
- ✅ Transactions can be signed and verified
- ✅ Blocks persist in RocksDB
- ✅ 3-node local testnet starts and runs
- ✅ All unit and integration tests passing
- ✅ No consensus yet (leader election comes in Stage 3)

### Known Limitations (Stage 2)

- **No consensus**: Nodes do not communicate; each node processes transactions independently
- **No block proposal**: Who proposes blocks? (Answered in Stage 3 with PBFT)
- **No finality**: Blocks not finalized; could be reversed (finality in Stage 3)
- **Single node only**: Run test on each node independently

---

## Stage 3: Consensus & Peer Network

**Duration**: ~3-4 weeks
**Goal**: Implement PBFT consensus and peer-to-peer communication; demonstrate 3 nodes reaching agreement.

### Components to Build

#### 3.1 Consensus Engine (`src/consensus/pbft.py`)

**Key Classes**:
- `PBFTEngine` — Main consensus state machine
- `ValidatorSet` — Known validators, voting power
- `BlockProposal` — PRE-PREPARE message
- `PrepareVote`, `CommitVote` — Consensus messages

**Key Methods**:
- `start_view()` — Begin new consensus round
- `on_pre_prepare()` — Receive block from leader
- `on_prepare()` — Broadcast prepare vote
- `on_commit()` — Broadcast commit vote
- `finalize_block()` — Block reaches 2f+1 commits

**Tests**:
- ✅ Single leader, all honest validators → block finalized
- ✅ Byzantine leader (sends invalid block) → validators reject
- ✅ Byzantine validator (sends conflicting votes) → honest validators agree
- ✅ Leader failure → view change triggered
- ✅ View change completes → new leader elected

#### 3.2 Peer Network (`src/network/`)

**Components**:
- `PeerServer` — TCP server listening for incoming connections
- `PeerConnection` — Outbound connection to peer
- `MessageHandler` — Route incoming messages to consensus
- `Discovery` — Connect to seed peers from config

**Key Methods**:
- `broadcast()` — Send message to all peers
- `send_to()` — Send message to specific peer
- `handle_message()` — Dispatch message to consensus or validator logic

**Protocol**:
```
Handshake (TCP):
  1. Connect to peer
  2. Send: {node_id, node_name, chain_id, protocol_version}
  3. Receive same from peer
  4. Verify chain_id matches; if not, disconnect
  
Message Format:
  <varint length><CBOR message><signature>
```

**Tests**:
- ✅ Peers discover each other from seed list
- ✅ Handshake succeeds; chain ID mismatch → disconnect
- ✅ Messages sent are received on peer
- ✅ Broadcast message reaches all peers

#### 3.3 Block Proposal & Validation

**Changes to block.py**:
- Block includes proposer (public key)
- Block includes signatures field (map of validator → signature)
- Block is finalized when signatures ≥ 2f+1

**Validation rules**:
- Parent block must be finalized
- Transactions in block are valid
- Block timestamp ≥ parent timestamp
- Block timestamp is not too far in future

#### 3.4 Integration Test: 3-Node Consensus

**Test** (`tests/integration/test_pbft_3node.py`):
```python
def test_3_validators_reach_consensus():
    """Start 3 validators; submit transaction; verify all 3 agree."""
    
    with LocalTestnet(num_validators=3) as testnet:
        # Submit transaction to node 1
        tx = create_transaction(...)
        node1.submit(tx)
        
        # Wait for finality
        time.sleep(15)  # 3 rounds × 5s block time
        
        # Check all 3 nodes have same block
        for height in range(1, 4):
            hash_1 = node1.get_block(height).hash
            hash_2 = node2.get_block(height).hash
            hash_3 = node3.get_block(height).hash
            assert hash_1 == hash_2 == hash_3
```

### Acceptance Criteria

- ✅ PBFT consensus protocol fully implemented
- ✅ 3-node testnet reaches consensus on blocks
- ✅ Byzantine validator detection and isolation
- ✅ View changes work under leader failure
- ✅ All integration tests passing
- ✅ Blocks are finalized (no chain reorganization)

---

## Stage 4: Sensor Identity & Submission

**Duration**: ~2 weeks
**Goal**: Enable IoT devices to register and submit signed sensor readings.

### Components

#### 4.1 Sensor Registry (`src/sensor/sensor_registry.py`)

- Sensor registration transaction (sensor_id, public_key, metadata)
- Storage of active sensors
- Revocation of compromised sensors

#### 4.2 Sensor Submission (`src/sensor/sensor_transaction.py`)

- Signed sensor reading format
- Submission API endpoint
- Validation (signature, timestamp, sequence number)

#### 4.3 Sensor Simulator (`src/sensor/sensor_simulator.py`)

- Generate reproducible sensor data
- Publish to blockchain via API

### Tests

- Sensor registration and retrieval
- Signed sensor reading verification
- Replay attack prevention (sequence numbers)
- Sensor revocation

---

## Stage 5: Sharding

**Duration**: ~4 weeks
**Goal**: Partition sensors across independent shards; route transactions; measure scalability.

### Components

#### 5.1 Sharding Assignment (`src/sharding/assignment.py`)

- Deterministic shard assignment: `shard_id = hash(sensor_id) % num_shards`
- Versioning (assignment can change at block boundaries)

#### 5.2 Shard State (`src/sharding/shard_state.py`)

- Independent transaction log per shard
- Per-shard state root and commitment

#### 5.3 Cross-Shard Coordination (`src/sharding/coordinator.py`)

- Atomic commits across shards
- Timeout and retry logic

### Tests

- Transaction routing to correct shard
- Shard-specific state isolation
- Cross-shard atomicity
- Sharding benchmarks (2, 4, 8 shards)

---

## Stage 6: Zero-Knowledge Proofs

**Duration**: ~4-6 weeks
**Goal**: Implement privacy-preserving aggregation proofs.

### Components

#### 6.1 Aggregation (`src/zkp/aggregation.py`)

- Aggregation function specification
- Batch formation logic

#### 6.2 Proof System (`src/zkp/proof_system.py`)

- Proof generation from sensor readings
- Proof verification
- Circuit definition (Circom or similar)

### Tests

- Proof correctness (valid → accepted, invalid → rejected)
- Performance (generation time, verification time)
- Privacy validation (proof doesn't leak sensor data)

---

## Stage 7: API, SDK, & Explorer

**Duration**: ~4 weeks
**Goal**: Developer-friendly interface and diagnostic UI.

### Components

#### 7.1 REST API (`src/api/`)

- Comprehensive endpoints for all blockchain operations
- OpenAPI/Swagger documentation
- Authentication and rate limiting

#### 7.2 Python SDK (`src/sdk/`)

- High-level API client
- Examples and tutorials

#### 7.3 Web Explorer (`src/explorer/`)

- React/TypeScript frontend
- Block explorer, transaction explorer, sensor registry
- Proof submission and verification UI

### Tests

- API endpoint tests
- SDK integration tests
- End-to-end browser tests

---

## Stage 8: Benchmarks, Security, Deployment

**Duration**: ~4 weeks
**Goal**: Comprehensive testing, audit, and production deployment guide.

### Components

#### 8.1 Benchmarks

- Throughput scaling (shard count, transaction rate)
- Latency (p50, p99)
- Proof generation/verification cost
- Memory and storage growth
- Validator failure recovery time

#### 8.2 Security Testing

- Adversarial network conditions (loss, latency, partition)
- Malformed transactions and blocks
- Proof tampering
- Resource exhaustion

#### 8.3 Documentation

- Testnet deployment guide (EC2, GCP)
- Operational runbook
- Troubleshooting guide
- Known issues and limitations

#### 8.4 CI/CD

- GitHub Actions for automated testing
- Container builds
- Security scanning (dependency vulnerabilities, SAST)

### Tests

- Benchmark scenarios (all documented)
- Security tests (adversarial)
- Deployment automation

---

## Timeline & Effort Estimates

| Stage | Duration | FTE | Key Deliverable |
|-------|----------|-----|-----------------|
| 1 | 1 week | 1 | Architecture & research mapping docs |
| 2 | 3 weeks | 2 | Minimal blockchain, Docker testnet |
| 3 | 4 weeks | 2 | PBFT consensus, 3-node agreement |
| 4 | 2 weeks | 1 | Sensor identity and submission |
| 5 | 4 weeks | 2 | Sharding and cross-shard coordination |
| 6 | 5 weeks | 2 | ZKP aggregation and verification |
| 7 | 4 weeks | 2 | REST API, SDK, web explorer |
| 8 | 4 weeks | 2 | Benchmarks, security, deployment |
| **Total** | **~6 months** | **~14 FTE** | **Production-ready research testnet** |

---

## Success Metrics

By end of Stage 8:

1. ✅ Multiple independent nodes running and reaching consensus
2. ✅ Transactions from IoT sensors processed, signed, stored
3. ✅ Sharding demonstrably improves throughput
4. ✅ ZKP aggregation proofs generated and verified
5. ✅ REST API and SDK usable by external developers
6. ✅ Web explorer displays live network data
7. ✅ Comprehensive benchmark suite with reproducible results
8. ✅ Security audit completed; known issues documented
9. ✅ Public testnet deployed; external researchers can join

---

## Risk Mitigation

### Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| PBFT consensus difficult to debug | Medium | High | Extensive logging, visualization tools early |
| ZKP proof system performance poor | Medium | Medium | Proof-of-concept in Stage 6 before full integration |
| Sharding introduces correctness bugs | Medium | High | Formal verification of cross-shard logic |
| Docker Compose insufficient for testing | Low | Medium | Add Kubernetes support in Stage 8 |

### Schedule Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Cryptographic library bugs | Low | High | Use well-reviewed libraries; fuzz testing |
| Network testing complexity | Medium | Medium | Implement network simulator in Stage 5 |
| Proof system selection delays | Medium | Medium | Prototype multiple proof systems in parallel |

---

## Next Steps (Stage 2)

1. Implement blockchain core (block, transaction, crypto)
2. Set up persistent storage (RocksDB)
3. Build Docker Compose environment
4. Create minimal API endpoints
5. Write comprehensive tests
6. Verify 3-node local testnet starts and survives 30 minutes

**Go to**: `Stage 2 Implementation` (next document)
