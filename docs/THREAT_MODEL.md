# Threat Model & Security Analysis

**Version**: 1.0 (Stage 2)
**Classification**: Research Platform, NOT Production-Ready

## Executive Summary

IoT-ShardChain is a **research testnet** designed for academic and industrial researchers to experiment with blockchain-based IoT systems. **It is NOT suitable for production use, financial transactions, or critical infrastructure without independent security audits and hardening.**

This document enumerates threats, our assumptions, mitigations in the current and planned stages, and residual risks.

## System Boundaries & Assumptions

### What We Assume Is Secure

1. **Cryptographic Libraries**: Ed25519, BLAKE2b, CBOR
   - Assumption: Standard libraries (libsodium, hashlib) are correctly implemented
   - Risk: Cryptanalytic advances or implementation bugs
   - Mitigation: Use only well-reviewed libraries; plan for crypto agility

2. **Validator Hardware**: Validators run in trusted environments
   - Assumption: Operator controls the machines running validators
   - Risk: Compromised operating system or hypervisor
   - Mitigation: Operator responsibility; firewall access, use HSM for production

3. **Network Connectivity**: Validators can reach each other with bounded latency
   - Assumption: No perpetual network partition
   - Risk: BGP hijack, ISP failure, adversarial packet loss
   - Mitigation: Redundant peer connections, geographic distribution

4. **Node Storage**: RocksDB stores blocks securely
   - Assumption: Storage device is not tampered with
   - Risk: Disk encryption key compromised, physical access
   - Mitigation: Encrypt at-rest; restrict operator access

### What We Explicitly Do NOT Guarantee

1. **Sensor Reading Truthfulness**
   - Cryptographic signatures verify key ownership, NOT sensor accuracy
   - Compromised IoT hardware can send valid but false readings
   - No on-chain mechanism detects sensor faults (e.g., stuck sensor, calibration drift)

2. **Quantum Resistance**
   - Ed25519 signatures vulnerable to quantum computers
   - Future: Post-quantum cryptography migration (Stage 8)

3. **Privacy of Readings**
   - All sensor readings visible to blockchain nodes
   - Privacy-preserving aggregation added in Stage 6
   - Before Stage 6: assume readings are public

4. **Production Readiness**
   - No formal security audit
   - Known vulnerabilities not yet patched
   - Performance not optimized for load
   - Testnet deployment only

## Threat Categories

### A. Consensus-Level Attacks

#### A1: Byzantine Leader Attack
**Threat**: Leader proposes a block that violates consensus rules (e.g., double-spend, invalid signature).

**Impact**: If 2f+1 validators are honest, the invalid block is rejected in prepare or commit phase.

**Status**: ✅ **Mitigated by PBFT** (Stage 3)

**Residual Risk**: If > f validators are Byzantine, they could agree on an invalid block.
- Assumption: ≤ f out of N validators are Byzantine

#### A2: View Change Stalling
**Threat**: Byzantine validators ignore view-change messages, preventing new leader election.

**Impact**: Consensus halts; no new blocks finalized.

**Status**: 🔄 **Partial mitigation** (Stage 3)
- Timeout triggers automatic view change
- But if >f validators are Byzantine, they stall view change phase

**Residual Risk**: Same as A1; inherent to BFT under >f Byzantine faults.

#### A3: Double-Spending
**Threat**: Attacker submits the same transaction twice, spending the same balance twice.

**Impact**: Blockchain state corrupted; trust loss.

**Status**: ✅ **Mitigated by nonce** (Stage 2)
- Each sender maintains a monotonic nonce
- Second transaction with same nonce is rejected

#### A4: Replay Attack
**Threat**: Attacker captures a valid signed transaction and resubmits it to a different node or after restart.

**Impact**: Sensor reading processed multiple times; state corruption.

**Status**: ✅ **Mitigated by nonce + chain ID** (Stage 2-3)
- Chain ID (network identifier) included in signature
- Nonce incremented per transaction
- Resubmitted transaction has outdated nonce → rejected

**Note**: If blockchain restarts with same chain ID, replayed old transaction with correct nonce is valid. **Mitigation**: Always increment network version on restart (not yet implemented).

### B. Network-Level Attacks

#### B1: Sybil Attack
**Threat**: Attacker creates many fake identities to influence validator set.

**Impact**: If validator set is dynamic, attacker could gain consensus control.

**Status**: ✅ **Mitigated by permissioned consensus** (Stage 2)
- Validator set is static, signed in genesis block
- No mechanism to add new validators without hard fork
- Attacker cannot create fake validators

**Residual Risk**: A compromised validator operator can act Byzantine; mitigated by f < N/3.

#### B2: Network Partition
**Threat**: Attacker partitions network; validators isolated in groups.

**Impact**: Neither partition has 2f+1 validators; no progress.

**Status**: ⚠️ **Safety preserved, liveness compromised** (Stage 3)
- Honest validators cannot finalize conflicting blocks on separate partitions
- But no new blocks finalized until partition heals

**Mitigation**: Operator detects partition and alerts; may require manual intervention.

#### B3: Denial of Service (DoS) via Flooding
**Threat**: Attacker sends many invalid transactions, overwhelming mempool and network.

**Impact**: Legitimate transactions delayed or dropped; apparent network outage.

**Status**: 🔄 **Partial mitigation** (Stage 5)

**Implemented** (Stage 2-3):
- Message size limits (max transaction size, max block size)
- Signature validation (drop unsigned or malformed messages)

**Planned** (Stage 5):
- Rate limiting per IP address
- Rate limiting per sender account
- Mempool capacity limits with priority fees

**Residual Risk**: Validator does not authenticate API clients (Stage 7 plan); DoS via API is possible.

#### B4: Man-in-the-Middle (MITM) Attack
**Threat**: Attacker intercepts peer-to-peer messages, modifies or replays them.

**Impact**: Consensus disrupted; fake blocks injected; validators disagree.

**Status**: 🔄 **Partial mitigation** (Stage 3)

**Implemented**:
- Signatures on all consensus messages → attacker cannot forge messages

**Planned** (Stage 5):
- TLS between peer nodes
- Peer authentication before message processing

**Residual Risk**: Attacker can still drop messages or reorder them (reflected in latency, mitigated by timeouts).

### C. Sensor & Data Attacks

#### C1: Compromised Sensor (Stolen Private Key)
**Threat**: Attacker obtains a sensor's private key and impersonates it.

**Impact**: Attacker submits arbitrary readings under the sensor's identity.

**Status**: ⚠️ **No mitigation** (inherent to public-key cryptography)

**What the system cannot do**: Detect a compromised sensor based on signature alone.

**What the system can do** (Stage 4+):
- Operator revokes sensor credentials (subsequent readings rejected)
- Reputation scoring: sensors with outlier readings flagged (Stage 7)
- Anomaly detection on aggregated values (Stage 8)

**Residual Risk**: Once key is compromised, all prior readings from that sensor are suspect.

#### C2: Forged Sensor Reading (Tampered Hardware)
**Threat**: Sensor hardware modified to report false values (e.g., temperature sensor reporting wrong temp).

**Impact**: Blockchain contains false data; applications make wrong decisions.

**Status**: ⚠️ **No mitigation** (out-of-band problem)

**Mitigation Strategy**: 
- Application-level (not blockchain level)
  - Cross-check readings against multiple sensors
  - Use domain knowledge to detect anomalies
  - Periodic sensor calibration and verification

**Residual Risk**: Blockchain provides no evidence of sensor faults.

#### C3: Replay of Old Sensor Reading
**Threat**: Attacker replays an old, valid sensor reading as if it's current.

**Impact**: Stale data treated as fresh; wrong decisions.

**Status**: ✅ **Mitigated by timestamp + sequence number** (Stage 4)

**Implementation**:
- Sensor reading includes timestamp and sequence number
- Application checks timestamp is recent (within acceptable window)
- Sequence number must be monotonically increasing per sensor

#### C4: Denial of Service on Sensor Submission API
**Threat**: Attacker floods the sensor submission endpoint with invalid requests.

**Impact**: Legitimate sensors cannot submit readings.

**Status**: 🔄 **Partial mitigation** (Stage 5)

**Implemented**:
- Input validation (malformed readings rejected)
- Request size limits

**Planned**:
- Rate limiting per sensor ID
- API key or authentication (Stage 7)

### D. Cryptographic Attacks

#### D1: Signature Forgery
**Threat**: Attacker forges a signature under a sensor's public key.

**Impact**: Attacker impersonates sensor; false readings accepted.

**Status**: ✅ **Mitigated by Ed25519** (Stage 2)
- Ed25519 is conjectured to be secure under strong assumptions
- Assume cryptanalytic strength

**Residual Risk**: Cryptanalytic weakness or implementation bug in Ed25519 library.
- Mitigation: Use audited library (libsodium); plan for crypto migration

#### D2: Hash Collision
**Threat**: Attacker finds two inputs with same BLAKE2b hash.

**Impact**: Attacker crafts malicious block with same hash as valid block; confusion.

**Status**: ✅ **Mitigated by BLAKE2b** (Stage 2)
- BLAKE2b (256-bit) collision probability ~ 2^-128 (negligible)

**Residual Risk**: Negligible; only relevant if hash function is broken.

#### D3: Side-Channel Attack on Cryptography
**Threat**: Attacker measures timing, power, or EM emissions from validator to extract private keys.

**Impact**: Private key compromised; attacker can forge signatures.

**Status**: ⚠️ **No direct mitigation** (environmental concern)

**Mitigation Strategy**:
- Use certified hardware security module (HSM) for production (operator responsibility)
- Constant-time implementations in libsodium

**Residual Risk**: Practical attacks possible in hostile environments.

### E. Smart Contract & Application Attacks

#### E1: Contract Logic Bugs (if contracts implemented)
**Threat**: Malicious contract code or logic error causes unexpected behavior.

**Impact**: Funds/state lost; incorrect execution.

**Status**: 🔄 **No smart contracts in Stage 2-3** (blockchain only)
- Stage 6+: Custom logic for aggregation, could introduce bugs

**Mitigation**: Formal verification, audits (Stage 7+)

### F. Operational & Configuration Attacks

#### F1: Misconfiguration (e.g., Wrong Genesis Block)
**Threat**: Validator initialized with wrong genesis block or network ID.

**Impact**: Validator joins wrong network; consensus fails or diverges.

**Status**: ⚠️ **Operator responsibility** (Stage 2)

**Mitigation**:
- Configuration validation scripts (Stage 3)
- Public genesis hash published; operator verifies before starting
- Network ID explicitly set and checked

#### F2: Key Compromise at Operator Level
**Threat**: Operator's machine compromised; private keys stolen.

**Impact**: Attacker can forge blocks/transactions as that validator.

**Status**: ⚠️ **Environmental issue** (operator security)

**Mitigation**:
- Operator must secure their machines (firewalls, SELinux, intrusion detection)
- Use hardware security modules (HSM) for key storage in production
- Key rotation procedure (Stage 7)

#### F3: Upgrade / Restart Window
**Threat**: During validator restart, network halts (no leader consensus).

**Impact**: Temporary loss of liveness; no new blocks.

**Status**: ✅ **Mitigated by f < N/3** (Stage 3)
- If only 1 validator down, remaining 2f validators can still reach quorum (if N ≥ 4)
- Procedure: Upgrade validators one at a time

**Residual Risk**: If >f validators restart simultaneously, consensus halts.

### G. Privacy Attacks

#### G1: Traffic Analysis
**Threat**: Attacker observes which sensors submit readings and correlates with location/time.

**Impact**: Privacy of sensor identities and locations leaked.

**Status**: ⚠️ **No mitigation** (inherent to public blockchain)

**Mitigation** (Stage 6+):
- Encrypted submissions → attacker cannot see plaintext
- Proxy aggregation → individual readings not visible
- Onion routing of peer messages (TBD)

**Residual Risk**: Metadata (timestamps, IP addresses) still visible to peer observers.

#### G2: Proof Leaks Private Data (if ZKP implemented incorrectly)
**Threat**: Zero-knowledge proof accidentally reveals sensor readings or aggregation details.

**Impact**: Privacy goal defeated.

**Status**: 🔄 **To be evaluated in Stage 6**
- Proof system must be carefully verified
- Circuits must be audited

## Security Testing Plan

### Unit Tests (Stage 2-3)

- ✅ Valid signature verification
- ✅ Invalid signature rejection
- ✅ Nonce enforcement (replay prevention)
- ✅ Hash correctness (no collisions)

### Integration Tests (Stage 3-4)

- ✅ Byzantine leader proposal (invalid block rejected)
- ✅ Byzantine validator vote (honest nodes disagree, valid block finalized)
- ✅ Network partition recovery
- ✅ View change under leader failure

### Adversarial Tests (Stage 5-6)

- 🔄 Sensor impersonation (stolen key)
- 🔄 DoS on API (traffic flooding)
- 🔄 Malformed transaction injection
- 🔄 ZKP with tampered proof

### Penetration Testing (Stage 8)

- External security audit of consensus, storage, API
- Adversarial network conditions (loss, latency, reordering)
- Resource exhaustion tests (memory, disk, CPU)

## Security Governance

### Responsibility Matrix

| Component | Stage | Owner | Review Required |
|-----------|-------|-------|-----------------|
| Consensus core | 3 | Dev team | Independent review |
| Cryptography (Ed25519, BLAKE2b) | 2 | Libsodium | Use standard library |
| Storage (RocksDB) | 2 | RocksDB project | Use standard library |
| Network (peer auth) | 5 | Dev team | Independent review |
| API authentication | 7 | Dev team | Security audit |
| ZKP circuit | 6 | Dev team | Formal verification |

### Incident Response (Post-Testnet)

If a vulnerability is discovered:

1. **Assess severity**: Does it affect consensus safety? Data integrity? Privacy?
2. **Triage**: Security patch vs. documentation update vs. design change?
3. **Fix**: Code fix in new branch; tests; review
4. **Release**: Testnet upgrade with new version; changelog entry
5. **Audit**: Post-mortem; document root cause and prevention

## Residual Risk Summary

| Risk | Severity | Mitigation | Acceptance |
|------|----------|-----------|-----------|
| Byzantine > f validators | High | f < N/3 by design | Accepted (design choice) |
| Compromised sensor key | High | Credential revocation (Stage 4) | Accepted (out-of-band issue) |
| False sensor readings (hardware fault) | High | Application-level checks | Accepted (not blockchain responsibility) |
| MITM peer messages | Medium | Signatures (Stage 2), TLS (Stage 5) | Acceptable in testnet |
| Network partition | Medium | Liveness halts, safety preserved | Acceptable (failover requires operator) |
| DoS on API | Medium | Rate limiting (Stage 5), auth (Stage 7) | Acceptable for testnet |
| Operator key compromise | High | HSM in production (operator responsibility) | Accepted (environmental) |
| ZKP implementation bug | High | Audit and formal verification (Stage 8) | Deferred to Stage 8 |

## Non-Testnet Production Deployment

If IoT-ShardChain is ever deployed to production beyond research:

**MANDATORY**:
1. Independent third-party security audit (Stage 8+)
2. Formal verification of consensus protocol
3. Formal verification of ZKP circuit
4. Hardware security modules (HSM) for validator keys
5. Network hardening (TLS, firewall, intrusion detection)
6. Operational security procedures (key rotation, incident response, backups)
7. Regulatory compliance review (data protection, financial services if applicable)
8. Insurance and liability coverage

**We cannot guarantee production readiness without these steps.**

## Further Reading

- PBFT safety and liveness: Castro & Liskov (1999), "Practical Byzantine Fault Tolerance"
- Sensor security: NIST SP 800-152, Guidelines for Securing Wireless Sensor Networks
- Blockchain security: Antonopoulos & Wood (2018), Mastering Ethereum

---

**Document Status**: Complete for Stage 2 review. Updates expected after Stages 3, 6.
