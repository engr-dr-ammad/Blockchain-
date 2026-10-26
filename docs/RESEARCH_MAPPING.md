# Research-to-Code Mapping

**Document Status**: Stage 1 (Planning Phase)

This document maps concepts and mechanisms from the two research papers to their implementation in IoT-ShardChain.

## Paper 1: Securing IoT Sensors Using Sharding-Based Blockchain Network Technology Integration: A Systematic Review

### Purpose
Systematic review synthesizing blockchain sharding techniques for IoT sensor security.

### Key Concepts Mapping

| Research Concept | Implementation Component | Status | Notes |
|------------------|-------------------------|--------|-------|
| **Sharding Architecture** | `src/sharding/assignment.py`, `src/sharding/shard_state.py` | Stage 5 | Deterministic sensor-to-shard mapping, independent shard execution |
| **Horizontal Scalability** | Sharding module | Stage 5 | Measured by transaction throughput vs. shard count |
| **Sensor Registration** | `src/sensor/sensor_registry.py` | Stage 4 | Cryptographic identity, public key storage, revocation |
| **Data Integrity** | `src/blockchain/crypto.py`, `src/blockchain/transaction.py` | Stage 2 | Ed25519 signatures, BLAKE2b hashing |
| **Decentralized Consensus** | `src/consensus/pbft.py` | Stage 3 | Byzantine fault-tolerant (PBFT) protocol |
| **Immutable Ledger** | `src/blockchain/chain.py`, `src/blockchain/storage.py` | Stage 2 | RocksDB persistent storage, chain validation |
| **Replay Attack Prevention** | `src/blockchain/transaction.py` | Stage 4 | Nonce field and sequence numbers |
| **Cross-Chain Coordination** | `src/sharding/coordinator.py` | Stage 5 | Atomic commits across shards |

### Research Design Questions

**Q1: Which sharding strategy from the review is implemented?**

A: We implement **sensor-based horizontal sharding**:
- Assignment rule: `shard_id = hash(sensor_id) % shard_count`
- Each shard processes transactions from its assigned sensors independently
- Cross-shard transactions require explicit coordinator
- Versioning allows reassignment at block boundaries

This avoids state sharding complexity and is common in sensor networks where each shard is responsible for a fixed sensor set.

**Q2: How do we measure scalability improvements?**

A: Benchmarks in `tests/benchmarks/`:
- Baseline (single shard, all transactions): throughput, latency
- Multi-shard (4 shards): throughput, latency, shard imbalance
- Scaling test (2, 4, 8 shards): measure throughput × shard_count

**Q3: Does the implementation support the review's threat model?**

A: Partial. The review addresses:

| Threat | Addressed By | Stage |
|--------|--------------|-------|
| Sensor spoofing | Cryptographic signatures | 4 |
| Replay attacks | Nonce/sequence fields | 4 |
| Network attacks | BFT consensus quorum | 3 |
| Single points of failure | Distributed validators | 3 |
| Data tampering | Merkle trees, hashing | 2 |

**Critical Gap**: The review discusses data confidentiality. We address this in Stage 6 with encrypted submissions and ZKP.

---

## Paper 2: A Blockchain-based Decentralized Secure Data Aggregation Scheme with ZKP for WSNs

### Purpose
Proposes a privacy-preserving aggregation protocol using zero-knowledge proofs for wireless sensor networks.

### Key Concepts Mapping

| Research Concept | Implementation Component | Status | Notes |
|------------------|-------------------------|--------|-------|
| **Aggregation Function** | `src/zkp/aggregation.py` | Stage 6 | Define: sum, avg, quantiles, custom functions |
| **Zero-Knowledge Proof** | `src/zkp/proof_system.py` | Stage 6 | Prove aggregation without revealing inputs |
| **Privacy Preservation** | `src/api/routes/proofs.py` | Stage 6 | Sensor readings never disclosed, only proofs |
| **Commitment Scheme** | `src/zkp/circuit.py` | Stage 6 | Pedersen commitments or similar |
| **Proof Verification** | `src/api/routes/proofs.py` | Stage 6 | On-chain verification of aggregation correctness |
| **Sensor Participation** | `src/sensor/sensor_registry.py` | Stage 4 | Sensor selection, dropout handling |
| **Resilience** | `src/zkp/aggregation.py` | Stage 6 | Handle missing sensors, faulty data |

### Implementation Assumptions

**A1: Aggregation Function**

The paper proposes privacy-preserving aggregation (likely sum or weighted average). We implement:

```python
# Pseudocode for aggregation
def aggregate(readings: List[SensorReading]) -> AggregationResult:
    """
    Aggregates sensor readings into a single value.
    
    Public inputs:
      - sensor_ids (list of participating sensors)
      - aggregated_value (e.g., sum)
    
    Private inputs (in proof witness):
      - individual readings
      - sensor signatures
    
    Verifies:
      1. Each reading has valid signature from declared sensor
      2. Each sensor appears exactly once
      3. Readings match declared aggregation function
      4. No double-counting or tampering
    """
```

**A2: Zero-Knowledge Proof Library**

Selection criteria:
- Mature, audited library (preferred over homegrown circuit)
- Support for practical aggregation logic (sum, weighted avg)
- Proof generation time < 10s
- Verification time < 100ms
- Language: Python or Rust with Python bindings

Candidates:
- **Circom + SnarkJS** (zk-SNARKs, popular)
- **LibZKP** (general-purpose ZK library)
- **Halo2** (Rust, good verification time)

**Decision deferred to Stage 6** once proof-system requirements are finalized.

**A3: Privacy Model**

The scheme provides **input privacy** (individual readings remain secret) but not **output privacy** (aggregated value is public). Assumptions:

- Aggregator (blockchain) is honest-but-curious (doesn't leak inputs)
- Sensors trust the aggregation commitment scheme
- Attackers cannot forge zero-knowledge proofs (cryptographic assumption)

What it does NOT protect:
- Sensor correlation attacks (if adversary knows sensor locations)
- Inference attacks (revealing aggregated sum may leak information)
- Compromised sensors (can still submit false readings)

### Research Questions & Implementation Decisions

**Q1: How are aggregation batches formed?**

A: Options considered:

1. **Time-based batches**: Aggregate all readings in a 10-second window
   - Simple, deterministic
   - May exclude late-arriving readings

2. **Count-based batches**: Wait for 50 sensor readings
   - Bounded proof size
   - Variable latency

3. **Leader-proposed batches**: A designated shard leader selects readings
   - Matches PBFT, minimal consensus overhead
   - Leader could exclude sensors (mitigated by reputation)

**Implementation**: Leader-proposed batches in Stage 6.

**Q2: How do we handle sensors that drop out?**

A: Aggregation scheme variants:

1. **Exact aggregation**: All sensors must participate
   - Proof is tight but fails if any sensor offline

2. **Approximate aggregation**: Sum with dropout threshold (e.g., > 80% sensors)
   - Proof includes which sensors participated
   - Must still verify signature from each participant

**Implementation**: Approximate with configurable threshold in Stage 6.

**Q3: Can the aggregation be corrupted by a Byzantine sensor?**

A: Yes. The ZKP proves that the claimed aggregation matches the inputs it saw, but it cannot prevent:

- A compromised sensor with valid private key sending false readings
- A shard leader including corrupt readings in the batch

**Mitigation**:
- Reputation scoring (Stage 7)
- Anomaly detection on aggregated values (Stage 8)
- Sensor credential revocation (Stage 4)

**NOT mitigated**: Hardware tampering or private key theft.

---

## Consensus Algorithm Mapping

### Paper 1 Review of Consensus Options

The first paper likely surveys consensus approaches (PoW, PoS, BFT, etc.). We implement **PBFT** because:

- **Permissioned network**: Known validator set (natural for IoT testnet)
- **Deterministic finality**: No confirmation delays, unlike PoW
- **Byzantine tolerance**: Handles malicious validators
- **Well-understood**: Reference implementations available
- **Research suitability**: Easy to experiment with f, block time, etc.

### Alternative Consensus Mechanisms (Future Stages)

We may add support for alternative consensus in Stage 8:

- **Practical Byzantine Fault Tolerance (PBFT)** — Current (Stage 3)
- **HotStuff** — Simpler view changes, better scalability (Stage 8 option)
- **Raft** — Crash-fault tolerant (not Byzantine)
- **Proof-of-Authority** — Permissioned, low overhead (Stage 8 option)

---

## Experimental Setup & Reproducibility

### Benchmark Scenarios from Papers

**From Paper 1 (Sharding)**:

1. **Scalability with Shard Count**
   - Measure: throughput vs. shard count (2, 4, 8, 16)
   - Expected: near-linear improvement
   - Implementation: `tests/benchmarks/shard_scaling.py`

2. **Network Latency Impact**
   - Measure: finality time with added latency (0, 10, 50, 100ms)
   - Expected: linear with latency
   - Implementation: `tests/benchmarks/network_latency.py`

3. **Validator Failure Recovery**
   - Measure: time to resume consensus after f validators crash
   - Expected: < 10 seconds with view change
   - Implementation: `tests/benchmarks/validator_failure.py`

**From Paper 2 (ZKP)**:

1. **Proof Generation Cost**
   - Measure: time to generate proof for N-sensor aggregation
   - Expected: sublinear or polynomial
   - Implementation: `tests/benchmarks/proof_generation.py`

2. **Proof Verification Cost**
   - Measure: time to verify proof (should be <100ms)
   - Expected: constant or log(N)
   - Implementation: `tests/benchmarks/proof_verification.py`

3. **Privacy-Preserving Aggregation Correctness**
   - Measure: proof verifies when inputs are correct, fails when tampering occurs
   - Expected: 100% pass rate on valid proofs, 0% on invalid
   - Implementation: `tests/integration/zkp_correctness.py`

### Experiment Configuration

Each benchmark records:

```json
{
  "experiment_name": "shard_scaling_experiment",
  "timestamp": "2026-10-26T12:00:00Z",
  "parameters": {
    "shard_count": 4,
    "transaction_rate": 1000,
    "block_time_ms": 5000,
    "network_latency_ms": 0
  },
  "results": {
    "throughput_tx_per_sec": 950,
    "latency_p50_ms": 45,
    "latency_p99_ms": 120,
    "memory_used_mb": 520
  },
  "git_revision": "abc123def456"
}
```

Results stored in `tests/benchmarks/results/` for trending and analysis.

---

## Implementation Order & Research Fidelity

### Stage 2 (Minimal Blockchain)

**Research Claims Addressed**: None yet; foundation only.

**What We Build**: Transaction signing, block structure, persistent storage.

**What Is NOT in Scope**: Sharding, ZKP, consensus beyond leader election.

### Stage 3 (Consensus Integration)

**Research Claim**: "Blockchain enables decentralized consensus."

**What We Implement**: Full PBFT, validator quorum, Byzantine tolerance.

**Tests**: Multi-validator agreement, Byzantine node failure.

### Stage 4-5 (Sensors & Sharding)

**Research Claims**:
- "Sensors can be registered and authenticated" (Paper 1)
- "Sharding enables horizontal scalability" (Paper 1)

**What We Implement**: Sensor cryptography, sharding assignment, shard execution.

**Tests**: Sharding correctness, throughput scaling, cross-shard atomicity.

### Stage 6 (Zero-Knowledge Proofs)

**Research Claim**: "ZKP enables privacy-preserving aggregation" (Paper 2)

**What We Implement**: Proof generation, verification, aggregation proof.

**Tests**: Proof correctness, privacy validation, performance.

### Stage 7-8 (Integration & Benchmarks)

**Research Claim**: Quantified scalability and privacy improvements.

**What We Do**: Run all benchmark scenarios, collect measurements, document results.

---

## Gaps & Clarifications

### Open Questions for Paper Authors

1. **Paper 1 Sharding Strategy**: Which of the surveyed sharding strategies is recommended for IoT?
   - **Current assumption**: Sensor-based horizontal sharding (easy to reason about)

2. **Paper 2 Aggregation Function**: What specific aggregation (sum, weighted avg, percentiles) is the primary use case?
   - **Current assumption**: Sum aggregation with privacy preservation

3. **Paper 2 Proof System**: Any specific zero-knowledge proof scheme preferred?
   - **Current assumption**: zk-SNARK (well-supported, fast verification)

4. **Sensor Fault Tolerance**: How many faulty sensors should the system tolerate?
   - **Current assumption**: Same as validator tolerance (⌊(N-1)/3⌋)

### Implementation Divergences

**These are NOT claims in the papers, but engineering decisions we made**:

1. **PBFT Consensus**: Practical choice for permissioned testnet (not specified in papers)
2. **RocksDB Storage**: Specific embedded database (not specified in papers)
3. **REST API**: External interface for research testbed (not specified in papers)
4. **Web Explorer**: Diagnostic UI (not specified in papers)

All engineering extensions are clearly labeled throughout the code.

---

## References

**Paper 1**:
- *Securing IoT Sensors Using Sharding-Based Blockchain Network Technology Integration: A Systematic Review*
- Author: Ammad Aslam
- [URL/Citation to be added]

**Paper 2**:
- *A Blockchain-based Decentralized Secure Data Aggregation Scheme with ZKP for WSNs*
- Author: Ammad Aslam
- [URL/Citation to be added]

---

## Maintaining This Document

As implementation progresses:

1. Update **Status** column for each mapping (Stage X when complete)
2. Add test results linking to actual test files
3. Document any deviations from papers with justification
4. Keep **Open Questions** current; mark resolved with decision

Last updated: 2026-10-26 (Stage 1)
