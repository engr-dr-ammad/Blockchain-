# Contributing to IoT-ShardChain

Thank you for your interest in contributing to the IoT-ShardChain research platform!

## Development Setup

### Prerequisites
- Python 3.9+
- Docker and Docker Compose
- Git

### Local Environment

```bash
# Clone repository
git clone https://github.com/engr-dr-ammad/blockchain-.git
cd blockchain-

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
pytest tests/unit/test_crypto.py -v
```

### Running the Local Testnet

```bash
# Start 3-node testnet
docker-compose -f docker/compose.dev.yml up

# In another terminal, verify nodes are running
curl http://localhost:8001/status
curl http://localhost:8002/status
curl http://localhost:8003/status

# Shut down
docker-compose -f docker/compose.dev.yml down
```

## Development Workflow

### Creating a Feature Branch

```bash
# Create a new branch for your feature
git checkout -b feature/your-feature-name

# Make changes, test locally
# Run tests before committing
pytest tests/unit -v
pytest tests/integration -v
```

### Code Style

We follow PEP 8 with some conventions:

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Check types
mypy src/ --ignore-missing-imports

# Lint
flake8 src/ tests/ --max-line-length=100 --ignore=E203,W503
```

### Committing

Please write clear commit messages:

```
Format: <type>: <subject>

<body>

<footer>

Example:
-----
feat: add PBFT consensus engine

Implement Practical Byzantine Fault Tolerance with:
- Pre-prepare, prepare, commit phases
- View change on leader failure
- Quorum validation (2f+1)

Related to Stage 3 implementation.
Tests: tests/integration/test_pbft.py::test_3_validators_reach_consensus

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

### Types of Changes

- **feat**: New feature (consensus, sensor module, etc.)
- **fix**: Bug fix
- **docs**: Documentation update
- **test**: Test addition or improvement
- **refactor**: Code reorganization without behavior change
- **perf**: Performance improvement
- **chore**: Dependency update, CI configuration, etc.

## Testing Requirements

### Before Submitting PR

1. **Unit Tests Must Pass**
   ```bash
   pytest tests/unit -v --cov=src --cov-report=term
   ```

2. **Integration Tests (if applicable)**
   ```bash
   pytest tests/integration -v
   ```

3. **Code Coverage**
   - Target: >80% for changed files
   - Use `--cov=src` to generate report

4. **Type Checking**
   ```bash
   mypy src/your_module.py --ignore-missing-imports
   ```

### Adding Tests

When adding a feature:
- Add unit tests in `tests/unit/test_*.py`
- Add integration tests in `tests/integration/test_*.py`
- Document test scenarios in comments

Example:
```python
def test_block_signature_validation():
    """Verify signed block is accepted; tampered block rejected."""
    block = Block(height=1, ...)
    signature = sign_block(block)
    
    # Valid signature
    assert block.verify_signature(signature)
    
    # Tampered block
    block.timestamp = 999999
    assert not block.verify_signature(signature)
```

## Documentation

### Docstring Convention

```python
def sign_transaction(tx: Transaction, private_key: bytes) -> bytes:
    """
    Sign a transaction with a private key.
    
    Args:
        tx: Transaction to sign
        private_key: Ed25519 private key (32 bytes)
    
    Returns:
        Signature bytes (64 bytes)
    
    Raises:
        ValueError: If private key is invalid
    """
```

### Code Comments

- **Avoid**: Comments that repeat code (`x = 1  # Set x to 1`)
- **Use**: Comments explaining WHY (`x = 1  # Timeout in seconds; empirically tuned`)
- **Document**: Non-obvious assumptions, cryptographic details, performance trade-offs

### Architecture Documentation

When proposing changes to architecture:
1. Update `docs/ARCHITECTURE.md` with new components
2. Add diagrams if helpful
3. Document assumptions and threat model impacts

## PR Submission Checklist

Before submitting a pull request:

- [ ] Code formatted with `black`
- [ ] Imports sorted with `isort`
- [ ] Type checking passes (`mypy`)
- [ ] Linting passes (`flake8`)
- [ ] Unit tests passing
- [ ] Integration tests passing (if applicable)
- [ ] Code coverage >80% for new code
- [ ] Docstrings added for public functions
- [ ] Commit messages clear and follow convention
- [ ] PR description explains WHAT and WHY (link to issue/stage)

## Research Attribution

When implementing research paper concepts:

1. **Cite the paper** in docstrings
   ```python
   def pbft_consensus(block):
       """
       Practical Byzantine Fault Tolerance consensus.
       
       Reference: Castro & Liskov (1999), "Practical Byzantine Fault Tolerance"
       """
   ```

2. **Update `docs/RESEARCH_MAPPING.md`** with implementation mapping

3. **Link to research** in commit messages
   ```
   feat: implement PBFT consensus engine

   Maps to Paper 1 (Section 3.2, Consensus Mechanism).
   Provides Byzantine fault tolerance for IoT sensors.
   
   Tests: tests/integration/test_consensus.py
   ```

## Reporting Issues

### Security Issues

**Do not open a public issue for security vulnerabilities.**

Email: [security contact TBD]

Include:
- Description of vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Bug Reports

1. **Title**: Clear, specific description
   - Bad: "blockchain crashes"
   - Good: "PBFT consensus crashes on validator timeout with 4 nodes"

2. **Environment**:
   ```
   - OS: Linux 6.18
   - Python: 3.9
   - Docker: 24.0
   ```

3. **Steps to Reproduce**:
   - Commands to run
   - Input data
   - Expected vs. actual behavior

4. **Logs**:
   - Include error messages
   - Include relevant debug output

### Feature Requests

1. **Title**: Clear feature description
2. **Motivation**: Why is this needed?
3. **Proposed Solution**: How might it work?
4. **Related to Stage**: Which implementation stage?

## Code Review Process

### What Reviewers Look For

- **Correctness**: Does the code do what it claims?
- **Testing**: Are edge cases covered?
- **Performance**: Any obvious inefficiencies?
- **Security**: Any vulnerabilities or assumptions?
- **Documentation**: Clear enough for future readers?
- **Style**: Follows project conventions?

### Responding to Review

- Address all comments or open discussion threads
- Re-request review after changes
- Small fixes can be grouped in follow-up commit
- Larger refactors may warrant separate PR

## Merge Criteria

A PR is ready to merge when:

1. ✅ All tests pass
2. ✅ Code review approved (at least 1 maintainer)
3. ✅ No merge conflicts
4. ✅ CI checks all green
5. ✅ Documentation updated
6. ✅ Commit messages clear

## Licensing

By contributing, you agree that your code is licensed under the same license as this project (to be selected with research author approval).

---

## Questions?

- **Architecture**: See `docs/ARCHITECTURE.md`
- **Research Mapping**: See `docs/RESEARCH_MAPPING.md`
- **Consensus Details**: See `docs/CONSENSUS.md`
- **Testing Strategy**: See `docs/TESTING_PLAN.md`
- **Roadmap & Stages**: See `docs/ROADMAP.md`

---

## Recognition

Contributors will be acknowledged in:
- `README.md` (Authors & Acknowledgments)
- Git commit history
- Release notes

Thank you for helping build the IoT-ShardChain research platform!
