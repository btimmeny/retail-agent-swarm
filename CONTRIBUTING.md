```markdown
# Contributing to retail-agent-swarm

Welcome! We appreciate your interest in contributing to **retail-agent-swarm**. This document outlines the guidelines and processes for contributing code, reporting issues, and collaborating on this Python project.

---

## Table of Contents

- [Development Environment Setup](#development-environment-setup)
- [Branch Naming Conventions](#branch-naming-conventions)
- [Commit Message Format](#commit-message-format)
- [Pull Request Process](#pull-request-process)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Issue and Bug Reporting](#issue-and-bug-reporting)

---

## Development Environment Setup

1. **Clone the repository:**
    ```bash
    git clone https://github.com/your-org/retail-agent-swarm.git
    cd retail-agent-swarm
    ```

2. **Create and activate a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Set up environment variables:**
    - Copy `.env.example` to `.env` and adjust values as needed:
      ```bash
      cp .env.example .env
      ```

5. **(Optional) Run with Docker:**
    ```bash
    docker build -t retail-agent-swarm .
    docker run --env-file .env -p 8000:8000 retail-agent-swarm
    ```

---

## Branch Naming Conventions

- **Feature branches:**  
  `feat/<short-description>`  
  _Example:_ `feat/inventory-reservation`

- **Bugfix branches:**  
  `fix/<short-description>`  
  _Example:_ `fix/order-validation-error`

- **Documentation branches:**  
  `docs/<short-description>`  
  _Example:_ `docs/update-readme`

- **Chore/maintenance branches:**  
  `chore/<short-description>`  
  _Example:_ `chore/update-dependencies`

Use hyphens to separate words. Keep branch names concise and descriptive.

---

## Commit Message Format

We use [Conventional Commits](https://www.conventionalcommits.org/) for all commit messages.

**Format:**
```
<type>(<scope>): <short description>
```

**Types:**  
- `feat` – New feature  
- `fix` – Bug fix  
- `docs` – Documentation changes  
- `test` – Adding or updating tests  
- `refactor` – Code changes that neither fix a bug nor add a feature  
- `chore` – Maintenance tasks  
- `ci` – Continuous integration changes  
- `style` – Formatting, missing semi colons, etc.

**Examples:**
```
feat(inventory): add bulk stock check for DCs
fix(order): handle missing customer_id in requests
docs(api): update order endpoint usage
```

---

## Pull Request Process

1. **Fork** the repository and create your branch from `main`.
2. **Write clear, descriptive PR titles** and link related issues.
3. **Ensure your code passes all tests** and follows style guidelines.
4. **Describe your changes** in the PR body. Include context, screenshots, or references as needed.
5. **Request review** from at least one maintainer.
6. **Address review comments** promptly.
7. **Do not merge your own PR** unless you are a project maintainer.

All PRs are automatically checked by CI (see `.github/ci.yml`). PRs must pass all checks before merging.

---

## Code Style Guidelines

- **Python version:** 3.10+
- **Formatting:** Use [Black](https://black.readthedocs.io/en/stable/) for code formatting.
    ```bash
    black .
    ```
- **Linting:** Use [flake8](https://flake8.pycqa.org/) or [ruff](https://beta.ruff.rs/) for linting.
    ```bash
    flake8 .
    # or
    ruff check .
    ```
- **Type hints:** Use type hints where possible.
- **Docstrings:** Public modules, classes, and functions should have docstrings.
- **Imports:** Group standard library, third-party, and local imports separately.

---

## Testing Requirements

- All new features and bugfixes **must include tests**.
- Tests are located in the `tests/` directory and use [pytest](https://docs.pytest.org/).
- To run tests:
    ```bash
    pytest
    ```
- For integration/smoke tests, see `smoke_test.py`.
- Ensure all tests pass before submitting a PR.

---

## Issue and Bug Reporting

- **Search existing issues** before opening a new one.
- **When reporting a bug**, include:
    - Steps to reproduce
    - Expected and actual behavior
    - Relevant logs, error messages, or screenshots
    - Environment details (OS, Python version, etc.)

- **For feature requests**, describe the problem, proposed solution, and alternatives considered.

- Use clear, descriptive titles and labels.

---

Thank you for contributing to **retail-agent-swarm**!  
If you have any questions, open an issue or reach out to the maintainers.
```
