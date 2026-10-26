# Consensus Protocol: Practical Byzantine Fault Tolerance (PBFT)

**Version**: 1.0 (Stage 3 Implementation)
**Status**: Design Specification (Implementation in Stage 3)

## Overview

IoT-ShardChain uses **Practical Byzantine Fault Tolerance (PBFT)**, a permissioned consensus protocol that tolerates up to f Byzantine (arbitrarily faulty) validators in a set of N = 3f + 1 validators.

**Key Properties**:
- **Safety**: All honest validators agree on the same block order
- **Liveness**: New blocks are finalized in O(1) round delays (assuming <f faults)
- **Deterministic Finality**: No confirmation delays; once a block has 2f+1 commits, it is final
- **Byzantine Tolerance**: Tolerates f malicious validators

## Fault Tolerance Table

| Total Validators (N) | Fault Tolerance (f) | Quorum Required | Minimum Honest (2f+1) |
|----------------------|-------------------|-----------------|----------------------|
| 3 | 0 | 3/3 (100%) | 3 |
| 4 | 1 | 3/4 (75%) | 3 |
| 5 | 1 | 4/5 (80%) | 4 |
| 7 | 2 | 5/7 (71%) | 5 |
| 10 | 3 | 7/10 (70%) | 7 |

**For a 3-validator testnet (N=3, f=0)**: All 3 validators must agree. No Byzantine fault tolerance.

**For a 4-validator testnet (N=4, f=1)**: 3 out of 4 must agree. Can tolerate 1 malicious validator.

## PBFT Protocol Phases

### Phase 0: Request (Client -> Leader)

```
Client submits a transaction:
  Transaction {
    nonce: u64
    sender: PublicKey
    operation: TransactionType
    data: Bytes
    signature: Signature
  }
```

The client can submit to any validator. Non-leader validators forward to the leader.

### Phase 1: Pre-Prepare (Leader -> All Validators)

The leader packages transactions into a block and broadcasts:

```
PRE-PREPARE {
  view: u64 (current view number)
  sequence_number: u64 (block height)
  block_hash: Bytes32
  block_data: Block {
    height: u64
    parent_hash: Bytes32
    proposer: PublicKey (leader)
    timestamp: i64
    transactions: [Transaction]
    merkle_root: Bytes32
    state_root: Bytes32
  }
  proposer_signature: Signature
}
```

**Validation**:
- Block height matches current sequence number
- Parent hash matches last finalized block
- All transactions have valid signatures
- Timestamp is reasonable
- Block is not too large

**On failure**: Validator does not proceed to prepare phase.

### Phase 2: Prepare (All -> All)

Each validator that accepted the pre-prepare broadcasts:

```
PREPARE {
  view: u64
  sequence_number: u64
  block_hash: Bytes32
  validator_signature: Signature
}
```

Each validator collects prepares from other validators.

**Condition**: Proceed to commit when received 2f+1 prepares (including own) for the same (view, sequence, block_hash).

### Phase 3: Commit (All -> All)

Once 2f+1 prepares are received, each validator broadcasts:

```
COMMIT {
  view: u64
  sequence_number: u64
  block_hash: Bytes32
  validator_signature: Signature
}
```

Each validator collects commits from other validators.

**Condition**: Block is **FINAL** when 2f+1 commits are received for the same (view, sequence, block_hash).

### State Transitions

```
IDLE
  ├─ (receive valid PRE-PREPARE) ─> PRE-PREPARED
  │
PRE-PREPARED
  ├─ (receive 2f+1 PREPARE) ─> PREPARED
  │
PREPARED
  ├─ (receive 2f+1 COMMIT) ─> COMMITTED
  │
COMMITTED
  ├─ (append block to chain, apply state changes) ─> IDLE
```

## View Change (Leader Election)

When the current leader is faulty or dead, validators trigger a view change.

### Trigger Conditions

A validator triggers view change if:

1. **Timeout**: No new block committed for T seconds (e.g., T = 30s)
2. **Invalid pre-prepare**: Leader sends malformed block
3. **Quorum decides**: 2f+1 validators vote to change view

### View Change Procedure

```
ViewChangeMessage {
  new_view: u64 (view + 1)
  last_stable_checkpoint: {
    sequence_number: u64
    block_hash: Bytes32
  }
  prepares_and_commits: [MessageDigest] (proofs of prepare/commit)
  validator_signature: Signature
}
```

**Procedure**:

1. Validator broadcasts VIEW-CHANGE for (new_view)
2. Leader for new_view (determined by `new_view % N`) collects view-change messages
3. New leader broadcasts NEW-VIEW with 2f+1 view-change messages
4. All validators accept NEW-VIEW and reset to new view

**New leader selection**: 
```python
new_leader_index = new_view % len(validators)
```

### Timeout & Recovery

- **Prepare timeout**: 5 seconds (no progress on current view)
- **Commit timeout**: 10 seconds (successful prepare, waiting for commits)
- **View change timeout**: 30 seconds (if view change stalls)

On repeated timeouts, exponential backoff up to 5 minutes, then alert operator.

## Liveness & Safety Proofs

### Safety: All Honest Validators Agree

**Invariant**: If 2f+1 validators commit block B at height H, no other block can be committed at height H.

**Proof**: Any two sets of 2f+1 validators have at least f+1 validators in common (by pigeonhole). If both sets committed different blocks at the same height, the common f+1 validators would have committed to both, which is impossible (each validator commits to at most one block per height).

### Liveness: Blocks Eventually Finalize

**Assumption**: At most f validators are Byzantine, and the network is eventually synchronous (all messages delivered in bounded time).

**Proof sketch**:
1. If current leader is honest, it will receive sufficient prepares and commits for its block
2. If current leader is Byzantine, 2f+1 honest validators trigger view change
3. New leader is chosen; the process repeats
4. With only one honest leader remaining and <f faults, that leader will finalize blocks

## Configuration

### Validator Set

The **genesis block** specifies the initial validator set:

```json
{
  "genesis": {
    "chain_id": "iot-shardchain-testnet-v1",
    "network_id": "0x1234567890abcdef",
    "timestamp": 1677000000,
    "validators": [
      {
        "index": 0,
        "name": "validator-1",
        "public_key": "0x...",
        "voting_power": 1
      },
      {
        "index": 1,
        "name": "validator-2",
        "public_key": "0x...",
        "voting_power": 1
      },
      {
        "index": 2,
        "name": "validator-3",
        "public_key": "0x...",
        "voting_power": 1
      }
    ]
  }
}
```

### Runtime Parameters

Configured in `config/node.yml`:

```yaml
consensus:
  min_prepare_timeout_ms: 5000    # 5 seconds for prepare phase
  min_commit_timeout_ms: 10000    # 10 seconds for commit phase
  view_change_timeout_ms: 30000   # 30 seconds before escalating view change
  block_time_target_ms: 5000      # Target time between blocks
  max_transactions_per_block: 1000
  max_block_size_bytes: 10485760   # 10 MB
```

## Comparison to Other Consensus Protocols

| Protocol | Finality | Tolerance | Scalability | Notes |
|----------|----------|-----------|-------------|-------|
| **PBFT** | Deterministic (O(1) rounds) | f < N/3 | O(N²) messages | ✅ Chosen for testnet |
| **HotStuff** | Deterministic | f < N/3 | O(N) messages | Better scaling, simpler view change |
| **PoW (Bitcoin)** | Probabilistic (~1 hour) | N/A | Low validator count required | High energy, not suitable |
| **PoS (Ethereum)** | Probabilistic (~15 min) | N/A | Higher finality delay | Not deterministic, not permissioned |
| **Raft** | Deterministic | Crash only, not Byzantine | O(N) messages | No Byzantine tolerance |

**Why PBFT for this project**?
- Research testnet (not production) → deterministic finality valuable for experiments
- Permissioned network (known validators) → PBFT natural fit
- Byzantine fault model → interesting for IoT security research
- Well-understood, reference implementations available

## Message Signing & Verification

All consensus messages are signed with the validator's private key:

```python
# Example: Sign a PREPARE message
message = PRE_PREPARE(view=1, sequence=100, block_hash=0x..., block_data=...)
signature = Ed25519Sign(message_bytes, validator_private_key)

# Verification
assert Ed25519Verify(message_bytes, signature, validator_public_key)
```

**Serialization**: Messages are CBOR-encoded for deterministic hashing.

## Edge Cases & Handling

### Case 1: Duplicate Prepare Messages

**Scenario**: A malicious leader sends multiple different PRE-PREPARE for the same view and sequence.

**Handling**:
- Validator accepts first valid PRE-PREPARE
- Subsequent PRE-PREPARE with same (view, sequence) but different block_hash is rejected
- If validator has already committed prepare for different block_hash, issue VIEW-CHANGE

**Result**: Honest validators will not accept conflicting prepares from the same leader.

### Case 2: Network Partition

**Scenario**: Network splits into two groups; neither has 2f+1 validators.

**Handling**:
- Both partitions trigger view changes repeatedly (timeouts)
- No partition reaches 2f+1 consensus
- Both wait until partition heals
- Once healed, validators with higher view number become leader
- Resynchronization happens naturally

**Result**: Safety preserved (no block finalized on both sides); liveness lost until partition heals.

### Case 3: Validator Restart

**Scenario**: Validator crashes and restarts after missing messages.

**Handling**:
- Validator loads last finalized block from RocksDB
- Starts with its current view number
- If behind, participates in view change to catch up
- Peer synchronization provides missing blocks

**Result**: Validator rejoins consensus in next view or current view.

### Case 4: Client Timeout

**Scenario**: Client sends transaction; after timeout, doesn't know if committed.

**Handling**:
- Client queries API: `GET /api/v1/transactions/{tx_id}`
- Response: status ∈ {pending, committed, finalized}
- If finalized on ≥2f+1 validators: safe to assume success
- If still pending after multiple timeouts: resubmit with same nonce

**Result**: Idempotent submission; retries don't cause double-processing.

## Monitoring & Diagnostics

### Node Health Endpoint

```bash
curl http://localhost:8001/api/v1/status
```

Response:
```json
{
  "node_id": "node-1",
  "chain_id": "iot-shardchain-testnet-v1",
  "network_id": "0x1234567890abcdef",
  "height": 1234,
  "view": 3,
  "is_leader": false,
  "finalized_block_hash": "0x...",
  "pending_transactions": 45,
  "validator_count": 3,
  "peer_count": 2,
  "last_block_time_ms": 4800,
  "consensus_state": "prepared",
  "uptime_seconds": 3600
}
```

### Consensus Metrics

Tracked and exposed for monitoring:

- `pbft_blocks_finalized` — Total blocks finalized
- `pbft_view_changes_total` — Total view changes triggered
- `pbft_prepare_latency_ms` — Median time prepare phase
- `pbft_commit_latency_ms` — Median time commit phase
- `pbft_leader_uptime_percent` — Current leader availability

### Log Examples

```
[2026-10-26 12:34:56] INFO consensus: View 0, sequence 100, leader: node-1
[2026-10-26 12:34:57] DEBUG consensus: Received PRE-PREPARE from node-1, block_hash=0x...
[2026-10-26 12:34:58] DEBUG consensus: Sent PREPARE, 2/3 prepares collected
[2026-10-26 12:35:00] INFO consensus: COMMITTED block 100, hash=0x...
[2026-10-26 12:35:31] WARN consensus: Prepare timeout on view 0, initiating view change
[2026-10-26 12:35:32] INFO consensus: View changed to view 1, new leader: node-2
```

## Performance Characteristics

### Latency

- **Prepare phase**: 1-2 network round trips (~50ms with local latency)
- **Commit phase**: 1-2 network round trips (~50ms)
- **Total block latency**: ~5 seconds (if block time = 5s)

### Message Complexity

- **Per block**: O(N) PRE-PREPARE, O(N²) PREPARE, O(N²) COMMIT
- **Per view change**: O(N²) VIEW-CHANGE, O(N) NEW-VIEW
- **Scaling**: Not suitable for >50 validators (quadratic messages)

### Improvements (Future)

- **BLS Threshold Signatures**: Aggregate signatures → O(N) messages
- **Pipelining**: Multiple views in progress → higher throughput
- **Leader rotation**: Every L blocks → reduces correlation with leader Byzantine faults

## Testing Plan

See [TESTING_PLAN.md](TESTING_PLAN.md) for detailed test scenarios:

- Single-leader happy path (3-5 validators)
- Byzantine leader (leader sends conflicting blocks)
- Validator failure and view change
- Network partition and recovery
- Message loss and retransmission
- Concurrent transactions and ordering

## References

- **Original PBFT**: Practical Byzantine Fault Tolerance (Castro & Liskov, 1999)
- **Implementation**: See `src/consensus/pbft.py`
- **Tests**: See `tests/integration/test_consensus.py`

---

**Next**: Stage 3 implementation. Consensus protocol coded, tested against multi-node failure scenarios.
