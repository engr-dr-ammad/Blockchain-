# Testing Plan & Benchmark Scenarios

**Version**: 1.0
**Status**: Stage 1 (Planning), Implementation Stages 2-8

## Overview

Comprehensive testing strategy covering unit tests, integration tests, end-to-end tests, and performance benchmarks.

## Test Pyramid

```
        ╱╲
       ╱  ╲  E2E Tests (10%)
      ╱────╲ - Browser automation
     ╱      ╲ - Public testnet
    ╱  ══════╲
   ╱   Integration (30%)
  ╱    ══════  - Multi-node consensus
 ╱     Tests   ╲ - Cross-shard transactions
╱             ╲ - ZKP verification
──────────────────
   Unit Tests (60%)
   - Cryptography
   - Block structure
   - Transaction validation
   - Storage operations
```

## Unit Tests (Stage 2+)

### Cryptography Tests (`tests/unit/test_crypto.py`)

**Ed25519 Signing**:
```python
def test_sign_and_verify():
    private_key, public_key = crypto.generate_keypair()
    message = b"test message"
    signature = crypto.sign(message, private_key)
    assert crypto.verify(message, signature, public_key)

def test_invalid_signature_fails():
    private_key, public_key = crypto.generate_keypair()
    message = b"test message"
    bad_signature = b"0" * 64
    with pytest.raises(crypto.SignatureError):
        crypto.verify(message, bad_signature, public_key)

def test_signature_deterministic():
    private_key, public_key = crypto.generate_keypair()
    message = b"test message"
    sig1 = crypto.sign(message, private_key)
    sig2 = crypto.sign(message, private_key)
    assert sig1 == sig2  # Deterministic for same key and message
```

**BLAKE2b Hashing**:
```python
def test_hash_consistency():
    data = b"test data"
    hash1 = crypto.hash(data)
    hash2 = crypto.hash(data)
    assert hash1 == hash2

def test_different_data_different_hash():
    hash1 = crypto.hash(b"data1")
    hash2 = crypto.hash(b"data2")
    assert hash1 != hash2

def test_hash_size():
    hash_result = crypto.hash(b"test")
    assert len(hash_result) == 32  # 256 bits
```

### Block Structure Tests (`tests/unit/test_block.py`)

**Serialization**:
```python
def test_block_serialization_roundtrip():
    block = Block(
        height=1,
        timestamp=int(time.time() * 1000),
        parent_hash=b"\x00" * 32,
        proposer=public_key,
        transactions=[tx1, tx2],
        merkle_root=compute_merkle_root([tx1, tx2]),
        state_root=b"\x00" * 32,
    )
    cbor_data = block.to_cbor()
    block_restored = Block.from_cbor(cbor_data)
    assert block_restored == block

def test_block_hash_consistency():
    block = Block(...)
    hash1 = block.hash()
    hash2 = block.hash()
    assert hash1 == hash2
```

**Validation**:
```python
def test_block_validation_invalid_height():
    block = Block(height=10, parent_hash=genesis_hash, ...)
    with pytest.raises(ValidationError):
        block.validate(parent_block=genesis_block)  # height should be 1

def test_block_validation_invalid_parent():
    block = Block(height=1, parent_hash=b"\xff" * 32, ...)
    with pytest.raises(ValidationError):
        block.validate(parent_block=genesis_block)

def test_block_validation_future_timestamp():
    future_time = int(time.time() * 1000) + 10 * 60 * 1000  # 10 min future
    block = Block(height=1, timestamp=future_time, ...)
    with pytest.raises(ValidationError):
        block.validate(parent_block=genesis_block)
```

### Transaction Tests (`tests/unit/test_transaction.py`)

**Signing & Verification**:
```python
def test_transaction_sign_and_verify():
    tx = Transaction(
        nonce=0,
        sender=public_key,
        operation="sensor_submit",
        data=b"sensor_data",
    )
    tx.sign(private_key)
    assert tx.verify(public_key)

def test_transaction_tampered_data_fails():
    tx = Transaction(nonce=0, sender=public_key, operation="sensor_submit", data=b"data")
    tx.sign(private_key)
    tx.data = b"tampered_data"
    with pytest.raises(SignatureError):
        tx.verify(public_key)

def test_transaction_replay_prevention():
    # Nonce is stored; receiver checks it's >= last seen nonce from sender
    tx1 = Transaction(nonce=1, sender=public_key, ...)
    tx1.sign(private_key)
    
    tx2 = Transaction(nonce=1, sender=public_key, ...)  # Same nonce
    tx2.sign(private_key)
    
    pool.add(tx1)  # Accepted
    with pytest.raises(ReplayError):
        pool.add(tx2)  # Rejected
```

### Storage Tests (`tests/unit/test_storage.py`)

**RocksDB Operations**:
```python
def test_store_and_retrieve_block():
    storage = RocksDBStorage(path="test_db")
    block = Block(height=1, ...)
    storage.put_block(block)
    
    retrieved = storage.get_block(height=1)
    assert retrieved == block

def test_retrieve_nonexistent_block():
    storage = RocksDBStorage(path="test_db")
    with pytest.raises(NotFoundError):
        storage.get_block(height=999)

def test_concurrent_writes():
    # Multiple threads writing to DB
    storage = RocksDBStorage(path="test_db")
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(storage.put_block, Block(height=i, ...))
            for i in range(100)
        ]
        for future in as_completed(futures):
            future.result()
    
    # All blocks should be stored
    for i in range(100):
        assert storage.get_block(height=i) is not None
```

### Mempool Tests (`tests/unit/test_mempool.py`)

```python
def test_add_transaction():
    mempool = Mempool()
    tx = Transaction(nonce=0, sender=public_key, ...)
    tx.sign(private_key)
    mempool.add(tx)
    assert tx in mempool

def test_reject_duplicate_nonce():
    mempool = Mempool()
    tx1 = Transaction(nonce=0, sender=public_key, ...)
    tx1.sign(private_key)
    
    tx2 = Transaction(nonce=0, sender=public_key, ...)  # Same nonce
    tx2.sign(private_key)
    
    mempool.add(tx1)
    with pytest.raises(DuplicateTransactionError):
        mempool.add(tx2)

def test_evict_oldest():
    mempool = Mempool(max_size=3)
    txs = [
        Transaction(nonce=i, sender=public_key, ...)
        for i in range(5)
    ]
    for tx in txs:
        tx.sign(private_key)
        mempool.add(tx)
    
    # Oldest 2 should be evicted
    assert len(mempool) == 3
    assert txs[0] not in mempool
    assert txs[1] not in mempool
    assert txs[4] in mempool

def test_get_top_transactions():
    mempool = Mempool()
    txs = [
        Transaction(nonce=i, sender=public_key, ...)
        for i in range(5)
    ]
    for tx in txs:
        tx.sign(private_key)
        mempool.add(tx)
    
    top = mempool.get_top(n=3)
    assert len(top) == 3
    assert all(tx in txs for tx in top)
```

---

## Integration Tests (Stage 3+)

### Consensus Tests (`tests/integration/test_pbft.py`)

**Happy Path: 3 Validators, Single Block**:
```python
@pytest.mark.integration
def test_3_validators_agree_on_block():
    """All 3 validators reach consensus on block proposal."""
    with LocalTestnet(num_validators=3) as testnet:
        # Submit transaction to validator 1
        tx = create_sensor_transaction()
        testnet.submit_transaction(tx)
        
        # Wait for consensus (max 15 seconds = 3 rounds)
        testnet.wait_for_finality(timeout=15)
        
        # Verify all 3 validators have the block
        for v in testnet.validators:
            block = v.get_block(height=1)
            assert block is not None
            assert block.transactions == [tx]
            
        # Verify all have same block hash
        hashes = [v.get_block(height=1).hash() for v in testnet.validators]
        assert len(set(hashes)) == 1  # All same
```

**Byzantine Leader**:
```python
@pytest.mark.integration
def test_byzantine_leader_invalid_block_rejected():
    """Leader sends invalid block; honest validators reject it."""
    with LocalTestnet(num_validators=3) as testnet:
        # Make validator 0 Byzantine (will propose invalid block)
        testnet.validators[0].mock_byzantine_leader = True
        
        # Trigger leader to propose (noop; Byzantine leader already prepared)
        testnet.submit_transaction(create_transaction())
        
        # Wait for prepare phase timeout
        time.sleep(7)
        
        # Validators 1 and 2 should trigger view change
        # (Leader didn't get 2 prepares for valid block)
        assert testnet.validators[1].current_view >= 1
        assert testnet.validators[2].current_view >= 1
```

**View Change & Leader Election**:
```python
@pytest.mark.integration
def test_view_change_on_leader_timeout():
    """Leader crash → validators trigger view change → new leader elected."""
    with LocalTestnet(num_validators=4) as testnet:
        initial_view = testnet.validators[0].current_view
        
        # Kill leader (validator 0)
        testnet.validators[0].stop()
        
        # Wait for other validators to timeout and change view
        time.sleep(35)  # Timeout + view change
        
        # New view should be elected
        for v in testnet.validators[1:]:
            assert v.current_view > initial_view
        
        # New leader is next in line
        expected_leader = (initial_view + 1) % 4
        assert testnet.validators[expected_leader].is_leader
```

### Multi-Block Consensus**:
```python
@pytest.mark.integration
def test_consensus_multiple_blocks():
    """Validators finalize multiple blocks in succession."""
    with LocalTestnet(num_validators=3) as testnet:
        # Submit 5 transactions
        for i in range(5):
            tx = create_transaction(nonce=i)
            testnet.submit_transaction(tx)
        
        # Wait for ~25 seconds (5 blocks × 5s block time)
        testnet.wait_for_block_height(height=5, timeout=30)
        
        # Verify all blocks are finalized
        for v in testnet.validators:
            for h in range(1, 6):
                block = v.get_block(h)
                assert block.is_finalized()
```

### Peer Synchronization Tests (`tests/integration/test_sync.py`)

**New Node Joins**:
```python
@pytest.mark.integration
def test_new_node_syncs_chain():
    """New validator joins; syncs blocks from peers."""
    with LocalTestnet(num_validators=3) as testnet:
        # Finalize 5 blocks
        testnet.finalize_blocks(num_blocks=5)
        
        # Add new validator
        new_v = testnet.add_validator()
        
        # Wait for sync
        time.sleep(5)
        
        # New node should have all 5 blocks
        assert new_v.get_block_height() == 5
        for h in range(1, 6):
            original_hash = testnet.validators[0].get_block(h).hash()
            new_hash = new_v.get_block(h).hash()
            assert original_hash == new_hash
```

**Restart & Recovery**:
```python
@pytest.mark.integration
def test_validator_restart_catches_up():
    """Validator restarts; syncs missing blocks."""
    with LocalTestnet(num_validators=3) as testnet:
        # Finalize 10 blocks
        testnet.finalize_blocks(num_blocks=10)
        
        v0 = testnet.validators[0]
        original_height = v0.get_block_height()
        
        # Restart validator 0
        v0.stop()
        v0.start()
        
        # Wait for sync
        time.sleep(5)
        
        # Should catch up
        assert v0.get_block_height() == original_height
```

---

## End-to-End Tests (Stage 7+)

### Browser-Based Exploration (`tests/e2e/test_explorer.py`)

**Block Explorer**:
```python
@pytest.mark.e2e
def test_explorer_displays_blocks(browser):
    """Open explorer; see blocks and transactions."""
    browser.get("http://localhost:3000")
    
    # Check dashboard shows block height
    height = browser.find_element("id", "block-height").text
    assert int(height) > 0
    
    # Click on latest block
    browser.find_element("id", "latest-block").click()
    
    # Should show block details (height, hash, transactions)
    assert browser.find_element("id", "block-height").is_displayed()
    assert browser.find_element("id", "block-hash").is_displayed()
```

**Sensor Registry**:
```python
@pytest.mark.e2e
def test_register_sensor_via_explorer(browser):
    """Register sensor through web UI."""
    browser.get("http://localhost:3000/sensors/register")
    
    # Fill form
    browser.find_element("id", "sensor-name").send_keys("temp-sensor-01")
    browser.find_element("id", "sensor-type").send_keys("temperature")
    browser.find_element("id", "submit").click()
    
    # Should redirect to sensor details
    time.sleep(2)
    assert "temp-sensor-01" in browser.page_source
```

---

## Performance Benchmarks (Stage 5+)

### Benchmark Scenarios

#### Scenario 1: Baseline Throughput (Single Shard)

**Setup**:
- 3 validators
- 1 shard
- 1000 transactions submitted at rate of 100 tx/sec

**Measurements**:
- Throughput (tx/sec accepted and finalized)
- Latency (p50, p95, p99 time from submission to finality)
- Memory usage
- CPU usage
- Storage growth

**Expected Results** (based on PBFT):
- Throughput: 800-1200 tx/sec
- Latency p99: <10 seconds
- Memory: <1 GB per validator

**Test Code**:
```python
@pytest.mark.benchmark
def test_baseline_throughput():
    """Measure single-shard throughput."""
    with LocalTestnet(num_validators=3, num_shards=1) as testnet:
        results = testnet.benchmark_throughput(
            num_transactions=1000,
            rate_tx_per_sec=100,
            duration_sec=30,
        )
        
        assert results["throughput_tx_per_sec"] > 800
        assert results["latency_p99_ms"] < 10000
        
        # Save results
        save_benchmark_results("baseline", results)
```

#### Scenario 2: Shard Scaling

**Setup**:
- 3 validators per shard
- Shards: 1, 2, 4, 8
- 1000 transactions per shard

**Measurements**:
- Throughput vs. shard count (expect near-linear)
- Shard imbalance (max/min load)
- Cross-shard coordination overhead

**Expected Results**:
- Throughput with 4 shards: ~4× baseline
- Shard imbalance: <5%

#### Scenario 3: ZKP Performance

**Setup**:
- Varying aggregation sizes (10, 50, 100, 500 sensors)
- Proof generation and verification

**Measurements**:
- Proof generation time (ms)
- Proof verification time (ms)
- Proof size (bytes)

**Expected Results**:
- Generation time: <10 seconds
- Verification time: <100 ms
- Proof size: <1 KB

#### Scenario 4: Network Latency Impact

**Setup**:
- 3 validators
- Simulated network latency: 0, 10, 50, 100 ms

**Measurements**:
- Block finality time vs. latency
- Throughput impact

**Expected Results**:
- Linear relationship: finality_time ≈ base_time + 2 × latency

#### Scenario 5: Validator Failure & Recovery

**Setup**:
- 5 validators
- Crash validator 0 after 100 blocks

**Measurements**:
- Time to elect new leader
- Time for validator 0 to sync and rejoin
- Throughput during failure

**Expected Results**:
- View change: <10 seconds
- Sync: <30 seconds
- Throughput during failure: same as normal (4 validators still functional)

---

## Benchmark Reporting

### Benchmark Result Format

Results saved as JSON for analysis:

```json
{
  "experiment": "baseline_throughput_2026-10-26",
  "timestamp": "2026-10-26T12:34:56Z",
  "parameters": {
    "num_validators": 3,
    "num_shards": 1,
    "block_time_ms": 5000,
    "transactions": 1000,
    "submission_rate_tx_per_sec": 100
  },
  "results": {
    "throughput_tx_per_sec": 950,
    "latency": {
      "p50_ms": 45,
      "p95_ms": 85,
      "p99_ms": 120
    },
    "memory_usage_mb": 520,
    "cpu_usage_percent": 35,
    "storage_growth_mb_per_sec": 2.5
  },
  "git_revision": "abc123def456"
}
```

### Benchmark Trending

Results tracked over time:
- `tests/benchmarks/results/{scenario}/{date}.json`
- Generate trend graphs
- Detect performance regressions

### Reproducibility

Each benchmark:
1. Uses fixed random seed
2. Records all parameters
3. Saves raw measurements
4. Documents environment (OS, hardware, Docker version)

---

## Continuous Integration (Stage 8)

### GitHub Actions Pipeline

**On Every PR**:
1. Unit tests (2 minutes)
2. Integration tests (5 minutes)
3. Code coverage check (threshold: >80%)
4. Lint and type checking (1 minute)

**Nightly**:
1. Full integration suite (30 minutes)
2. Benchmark suite (1 hour)
3. Security scan (dependency vulnerabilities, SAST)

**On Release**:
1. All tests + benchmarks
2. Docker image build and push
3. Generate release notes

---

## Test Coverage Goals

| Category | Target | Verification |
|----------|--------|--------------|
| Consensus core | >90% | Code coverage tool |
| Cryptography | 100% | All paths tested |
| Storage | 85% | Fault injection testing |
| Network | 70% | Peer simulation tests |
| API | 80% | Endpoint coverage |
| Overall | >80% | Coverage report |

---

## Known Limitations & Future Improvements

**Current**:
- No adversarial network conditions (loss, delay, partition simulation) in Stage 2-3
- No formal verification of consensus safety
- No property-based testing (fuzzing)

**Planned** (Stage 8):
- Network condition simulation (Toxiproxy)
- Formal verification (TLA+)
- Property-based testing (Hypothesis)
- Distributed tracing (Jaeger)

---

## Test Execution Examples

### Run All Unit Tests
```bash
pytest tests/unit -v
```

### Run Integration Tests (requires Docker)
```bash
pytest tests/integration -v -s
```

### Run Single Benchmark
```bash
pytest tests/benchmarks/test_throughput.py::test_baseline_throughput -v --benchmark-only
```

### Generate Coverage Report
```bash
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

---

**Next**: Proceed to Stage 2 implementation. Create blockchain core modules, Docker Compose, and execute unit tests.
