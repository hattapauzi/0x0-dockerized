# Contributing to 0x0-Dockerized

Thank you for contributing to `0x0-dockerized`!

Please see our comprehensive documentation guides for details:

- **[Development & Testing Guide](docs/development.md)**: Setting up virtual environment, running pytest suite, and database migrations.
- **[Architecture & Design](docs/architecture.md)**: System design, data flow, and security model.
- **[API Reference](docs/api.md)**: Endpoints, request/response formats, and status codes.
- **[Operations Runbook](docs/runbook.md)**: Deployment, reverse proxy configs, backups, and maintenance.

## Feature Branches & Documentation Policy

This project strictly separates application implementation from working feature documentation:

- **Implementation branches (`feat/...`, `fix/...`)**: Contain application code (`0x0/`), tests, templates, and runtime scripts.
- **Feature documentation branches (`docs/...`)**: Contain working/feature documentation, design specs, plans, and preliminary docs relevant to developing that specific feature.
- **Merging rule**:
  - Feature docs branches (`docs/...`) serve as working and design records relevant during feature development and review. They are **not** merged into `master` and can be left behind as historical/reference branches.
  - Only the implementation branch (`feat/...` or `fix/...`) is merged into `master`.
  - The merge commit to `master` must mention the corresponding `docs/` branch (e.g. `Working feature documentation and specs remain on docs/<feature-name>`).

## Quick Contribution Checklist
1. Write tests for any new features or bug fixes in `0x0/tests/test_client.py`.
2. Ensure all tests pass: `~/.venvs/0x0/bin/python -m pytest tests/ -q` (from `0x0/`).
3. Ensure no secrets or runtime data (`data/`) are committed.
4. Keep working specs/plans on a dedicated `docs/` branch rather than mixing them into the implementation branch.

