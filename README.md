# IoT-ShardChain: A Research Blockchain Platform for Secure IoT Sensor Networks

**Status: Pre-alpha Stage 2 Implementation**

A distributed, multi-node blockchain research platform designed to implement sharding-based consensus, zero-knowledge proofs for secure data aggregation, and cryptographically signed IoT sensor transactions.

Based on the research:
- *Securing IoT Sensors Using Sharding-Based Blockchain Network Technology Integration: A Systematic Review*
- *A Blockchain-based Decentralized Secure Data Aggregation Scheme with ZKP for WSNs*

**Developed by Ammad Aslam with AI-assisted tooling**

## Quick Start (Development)

### Prerequisites
- Docker and Docker Compose
- Python 3.9+
- Git

### Run Local Testnet (3 nodes)

```bash
docker-compose -f docker/compose.dev.yml up
```

This starts three independent blockchain nodes that automatically discover each other and reach consensus.

### Verify Testnet

```bash
curl http://localhost:8001/api/v1/status
curl http://localhost:8002/api/v1/status
curl http://localhost:8003/api/v1/status
```

All three should report the same chain height and block hash.

### Stop and Clean

```bash
docker-compose -f docker/compose.dev.yml down
docker-compose -f docker/compose.dev.yml down -v  # Remove volumes
```

## Architecture Overview

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed design.

**Core components:**

- **Consensus Engine**: Byzantine Fault Tolerant (BFT) consensus with permissioned validators
- **Blockchain Core**: Transaction signing, block validation, persistent storage, mempool management
- **Sharding Engine**: Deterministic sensor-to-shard assignment, independent shard processing
- **Sensor Identity**: Cryptographic sensor registration and authentication
- **Zero-Knowledge Proofs**: Privacy-preserving aggregation verification
- **REST API**: Developer-friendly endpoints for all operations
- **Web Explorer**: Block/transaction viewer, sensor registry, proof verification UI

## Implementation Stages

| Stage | Component | Status |
|-------|-----------|--------|
| 1 | Repository audit, research mapping, consensus spec | ✅ Complete |
| 2 | Minimal blockchain, transactions, storage, Docker testnet | 🔄 In Progress |
| 3 | Consensus integration, peer sync, failure tests | ⏳ Planned |
| 4 | Sensor identity, signed submissions, replay protection | ⏳ Planned |
| 5 | Sharding, independent shard processing | ⏳ Planned |
| 6 | ZKP generation, verification, privacy tests | ⏳ Planned |
| 7 | REST API, SDK, explorer, testing portal | ⏳ Planned |
| 8 | Benchmarks, security tests, testnet deployment | ⏳ Planned |

## Documentation

- [Architecture & Design](docs/ARCHITECTURE.md)
- [Research-to-Code Mapping](docs/RESEARCH_MAPPING.md)
- [Consensus Protocol](docs/CONSENSUS.md)
- [Threat Model & Security](docs/THREAT_MODEL.md)
- [Roadmap](docs/ROADMAP.md)
- [Testing Plan](docs/TESTING_PLAN.md)

## API Documentation

See [docs/API.md](docs/API.md) for REST API endpoints and examples.

## License

[TBD - to be selected with research author approval]

## Contributing

Contributions welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Security & Bug Reports

This is a **research-stage platform**. It is not production-ready and should not be used for financial transactions or critical IoT applications without independent security audits.

Report security issues to: **[security contact TBD]**

## Research Attribution

This implementation builds upon:
- Ammad Aslam's systematic review on sharding-based blockchain for IoT security
- Ammad Aslam's research on zero-knowledge proofs for decentralized data aggregation in wireless sensor networks

See [docs/RESEARCH_MAPPING.md](docs/RESEARCH_MAPPING.md) for detailed mapping of research concepts to implementation.

## Authors & Acknowledgments

- **Research & Implementation**: Ammad Aslam (aamdm1@iscte-iul.pt)
- **Development Methodology**: AI-assisted development using Claude Code
- **Contributing Researchers**: [To be added]

---

**Repository**: https://github.com/engr-dr-ammad/blockchain-
**Questions?** Open an issue or contact the maintainers.
