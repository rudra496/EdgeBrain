# Contributing to EdgeBrain

Thanks for your interest in contributing! This guide will help you get started.

## Getting Started

1. Fork the repository
2. Clone your fork locally
3. Follow the [Setup Guide](SETUP.md) to get the system running
4. Create a feature branch: `git checkout -b feature/your-feature`
5. Make your changes
6. Test thoroughly
7. Open a Pull Request

## Code Style

### Python (Backend)
- Follow PEP 8
- Use type hints where practical
- Keep functions focused and small
- Add docstrings to public functions
- Use `logging` module, not `print()`

### JavaScript/React (Frontend)
- Use functional components with hooks
- Keep components small and focused
- Use descriptive variable names
- CSS: prefer single-file styles per component

## Project Structure

```
backend/app/
├── api/          → REST endpoints, WebSocket handlers
├── core/         → Config, database, MQTT, events
├── ai/           → Decision engine, strategies, anomaly detection
├── agents/       → Multi-agent system
├── models/       → Database models
└── services/     → Business logic
```

## Adding a New Decision Strategy

1. Create a new file in `backend/app/ai/` or add to existing
2. Implement the `DecisionStrategy` interface
3. Register it in `agents/multi_agent.py`

```python
from app.ai.rules import DecisionStrategy, Decision

class MyStrategy(DecisionStrategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    def evaluate(self, device_id, device_type, value, history):
        # Your logic here
        return []  # list of Decision objects
```

## Adding a New Device Type

1. Add simulation logic in `device-simulator/simulator.py`
2. Add rules in `backend/app/ai/rules.py` (ThresholdStrategy)
3. Add anomaly detection thresholds in `backend/app/ai/anomaly.py` if needed

## Adding a New API Endpoint

1. Add route in `backend/app/api/routes.py`
2. Keep it under `/api/v1/` prefix
3. Use proper HTTP methods and status codes

## Commit Messages

Use conventional commits format:

```
feat: add humidity sensor support
fix: resolve MQTT reconnection issue
docs: update architecture documentation
refactor: simplify decision engine pipeline
test: add unit tests for anomaly detector
```

## Pull Request Process

1. Keep PRs focused — one feature/fix per PR
2. Include a clear description of what and why
3. Test your changes before submitting
4. Respond to review feedback promptly

## Reporting Issues

Use the [bug report](../.github/ISSUE_TEMPLATE/bug_report.md) or [feature request](../.github/ISSUE_TEMPLATE/feature_request.md) templates.

## Questions?

Open a [discussion](https://github.com/rudra496/EdgeBrain/discussions) or ask in Issues.

---

Thank you for contributing to EdgeBrain! 🧠
