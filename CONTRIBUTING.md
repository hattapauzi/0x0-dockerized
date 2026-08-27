# Contributing to 0x0-Dockerized

Thank you for contributing to `0x0-dockerized`!

Please see our comprehensive documentation guides for details:

- **[Development & Testing Guide](docs/development.md)**: Setting up virtual environment, running pytest suite, and database migrations.
- **[Architecture & Design](docs/architecture.md)**: System design, data flow, and security model.
- **[API Reference](docs/api.md)**: Endpoints, request/response formats, and status codes.
- **[Operations Runbook](docs/runbook.md)**: Deployment, reverse proxy configs, backups, and maintenance.

## Quick Contribution Checklist
1. Write tests for any new features or bug fixes in `0x0/tests/test_client.py`.
2. Ensure all tests pass: `~/.venvs/0x0/bin/python -m pytest tests/ -q` (from `0x0/`).
3. Ensure no secrets or runtime data (`data/`) are committed.
4. Update documentation in `docs/` and `README.md` if behavior or configuration changes.
