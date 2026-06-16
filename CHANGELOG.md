# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-06-16

### Added
- Documentation in README.md on installing the application from source or via built wheels.
- Documentation in README.md on installing prek as a local Git hook.

---

## [1.0.0] - 2026-06-16

### Added
- First full production release of MonetRack CLI.

---

## [1.0.0-rc.1] - 2026-06-16

### Changed
- Bumped version to `1.0.0-rc.1` following SemVer updates workflow.

---

## [1.0.0-rc] - 2026-06-16

### Added
- GitHub Actions CI/CD pipeline ([.github/workflows/ci.yml](file:///Users/torstenzielke/Projects/monetrack/.github/workflows/ci.yml)) utilizing native actions for Ruff, prek hooks check, Ty typechecking, Pytest test runner, and automated releases.
- Automated release packaging (`uv build`) and assets upload to GitHub Releases for tag pushes (`v*`).
- Structured [README.md](file:///Users/torstenzielke/Projects/monetrack/README.md) explaining features, CLI commands, setup, and development instructions.
- MIT [LICENSE](file:///Users/torstenzielke/Projects/monetrack/LICENSE) file.
- [ADRs.md](file:///Users/torstenzielke/Projects/monetrack/ADRs.md) documenting core architectural decisions.

### Fixed
- Fixed concurrent cache reservation errors in GitHub Actions by adding unique `cache-suffix` parameters to `setup-uv` steps.

---

## [0.1.0] - 2026-06-16

### Added
- Initial project layout and structure using `uv` and Python 3.14.
- XDG base directory setup mapping to `~/.local/share/monetrack/`.
- SQLite database layer and schema for `assets`, `transactions`, and `snapshots`.
- CLI commands (`asset create`, `asset list`, `invest`, `withdraw`, `snapshot`, `stats`) powered by `typer`.
- Stats calculation engine supporting net invested, current value, total earnings, ROI %, and monthly breakdowns.
- Visual formatting for CLI tables and responses using `rich`.
- Autocomplete interactive shell using `prompt-toolkit` with `NestedCompleter` and dynamic database-based completions.
- Pre-commit / `prek` quality hooks configuration.
- Static type checking with `ty` and code styling with `ruff`.
