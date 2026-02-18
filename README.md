# Self-Healing Documentation Engine

A GitHub/GitLab bot that treats documentation like code, ensuring technical accuracy without manual intervention.

## Overview

The Self-Healing Documentation Engine automatically validates code snippets in documentation during pull request workflows, detects breaking changes from function renames or dependency updates, and generates corrected versions that maintain Single Source of Truth documentation.

## Features

- **Automatic Validation**: Validates all code snippets in documentation on every pull request
- **Auto-Correction**: AI-powered correction of broken code examples
- **Multi-Language Support**: Python, JavaScript, TypeScript, Java, Go, Rust
- **Secure Execution**: Isolated container-based code execution with resource limits
- **GitHub/GitLab Integration**: Seamless bot integration with status checks and comments
- **Code Mapping**: Intelligent tracking of relationships between code and documentation

## Architecture

The system is built as a cloud-native microservices architecture:

- **API Gateway**: FastAPI-based webhook handler and REST API
- **Validation Engine**: Container-based code execution with multi-language support
- **Healing Engine**: AI-powered correction generation using OpenAI
- **Code Mapping Service**: AST-based code-documentation relationship tracking
- **Queue System**: Redis Queue (RQ) for reliable event processing
- **Database**: PostgreSQL for persistent storage
- **Cache**: Redis for caching and rate limiting

## Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- Poetry for dependency management

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd ai-doc-healing
```

2. Install dependencies:
```bash
poetry install
```

3. Start the services:
```bash
docker-compose up -d
```

4. Run database migrations:
```bash
poetry run alembic upgrade head
```

5. Start the API server:
```bash
poetry run uvicorn doc_healing.api.main:app --reload
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=src/doc_healing

# Run specific test types
poetry run pytest -m unit
poetry run pytest -m property
poetry run pytest -m integration
```

### Code Quality

```bash
# Format code
poetry run black src tests

# Lint code
poetry run ruff check src tests

# Type checking
poetry run mypy src
```

## Configuration

Create a `.doc-healing.yml` file in your repository root:

```yaml
enabled: true

documentation:
  include:
    - "docs/**/*.md"
    - "README.md"
  exclude:
    - "docs/archive/**"

languages:
  python:
    enabled: true
    timeout: 30
    dependencies:
      - "requests"
      - "pytest"

validation:
  autoCorrect: true
  confidenceThreshold: 0.8
  blockOnFailure: true
```

## Development

### Project Structure

```
.
├── src/doc_healing/          # Main application code
│   ├── api/                  # FastAPI application
│   ├── db/                   # Database models and configuration
│   ├── models/               # Shared data models
│   └── queue/                # Queue management
├── tests/                    # Test suite
├── alembic/                  # Database migrations
├── k8s/                      # Kubernetes manifests
├── docker-compose.yml        # Local development setup
└── pyproject.toml           # Project dependencies

```

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]
