# PrizmForge Test Suite

This directory contains the test framework for PrizmForge.

## Quick Start

### 1. Install development dependencies

```bash
pip install pytest pytest-cov responses pytest-mock
```

Or add to your environment:

```txt
# requirements-dev.txt
pytest>=8.0
pytest-cov>=5.0
responses>=0.25
pytest-mock>=3.14
```

### 2. Run all tests

```bash
pytest tests/ -v
```

### 3. Run with coverage

```bash
pytest tests/ --cov=. --cov-report=html
```

## Mocking LLM Endpoints

We use the `responses` library to mock OpenAI-compatible chat endpoints.

### Using the fixture (recommended)

```python
def test_my_agent(mock_openai_chat):
    mock_openai_chat(response_text="Mocked reply from LLM")
    
    result = call_agent("developer", "Build something", "task_001")
    assert "Mocked reply" in result
```

### Advanced mocking

See `tests/mocks/openai.py` for manual control.

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures (mock_openai_chat, temp_db, etc.)
├── test_schema.py           # Schema initialization & DB structure tests
├── test_governed_editing.py # Core governed editing tests (proposals, apply, concurrency)
├── unit/
│   ├── test_json_parser.py
│   ├── test_truncation_detector.py
│   ├── test_token_modules.py
│   ├── test_resource_controller.py
│   └── test_cli_commands.py
├── mocks/
│   └── openai.py
└── README.md
```

## Philosophy

- Mock external LLM calls by default in unit tests
- Keep tests fast and deterministic
- Gradually add integration tests that exercise real flows
- Expand the mock as you implement more of the real OpenAI-compatible endpoint
```

---

**Next Steps**

1. Install the dev dependencies above.
2. Run `pytest tests/ -v` to verify everything works.
3. Start writing tests for your agents using the `mock_openai_chat` fixture.

The framework is now ready for serious expansion. Would you like me to add more example tests (e.g., for the JSON parser, truncation detector, or governed editing)?