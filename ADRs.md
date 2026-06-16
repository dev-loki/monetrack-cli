# Architectural Decision Records (ADRs)

This document lists the core architectural decisions made in the development of the MoneTrack CLI.

---

## ADR 001: SQLite for Local Data Storage

### Status
Accepted

### Context
MoneTrack is a command-line investment tracking tool designed to run locally on a user's machine. It requires a relational schema to manage `assets`, `transactions`, and `snapshots` while maintaining relational integrity (e.g. foreign keys linking transactions to assets).

### Decision
We chose SQLite as the storage engine.
- It is zero-configuration and does not require running a separate database server.
- It is natively supported in Python via the `sqlite3` module.
- It is lightweight, fast, and easily portable as a single database file.

### Consequences
Data is stored locally in a single file (`monetrack.db`). The CLI must handle schema creation and migrations on startup. Relational integrity is enforced using foreign keys (which must be explicitly enabled via `PRAGMA foreign_keys = ON`).

---

## ADR 002: XDG Base Directory Standard for Configuration and Data

### Status
Accepted

### Context
To prevent cluttering the user's home directory with project-specific hidden files (e.g., `.monetrack`), the database and configurations should be stored in standard OS directories.

### Decision
We use the XDG Base Directory Specification, resolving directories using the `platformdirs` package. Specifically, we store the database in the user's standard data directory (e.g. `~/.local/share/monetrack/monetrack.db` on Linux/macOS).

### Consequences
The application remains clean and well-behaved, keeping user directories clean and matching standard OS behaviors.

---

## ADR 003: Typer for CLI Framework

### Status
Accepted

### Context
We need a robust, clean, and maintainable framework to build command-line commands and parse inputs.

### Decision
We chose `typer` to build the CLI interface.
- It uses Python type hints to declare command-line arguments and options.
- It automatically generates help menus.
- It is built on top of `click`, ensuring high stability.

### Consequences
Defining new commands is straightforward and type-safe. Validation of input types (e.g., floats for amounts) is performed automatically by Typer.

---

## ADR 004: prompt-toolkit for Autocomplete Interactive Shell

### Status
Accepted

### Context
Using traditional CLI arguments for nested commands and dynamic parameters (e.g. asset names) can be tedious. An interactive mode improves user experience by providing autocomplete suggestions.

### Decision
We integrated `prompt-toolkit` with `NestedCompleter` to implement an interactive shell mode.
- It allows multi-subcommand autocomplete and options completion.
- Suggestions for assets (names, ISINs, WKNs) are queried dynamically from the database and updated in real-time as the user types.

### Consequences
Running the CLI without arguments drops the user into an interactive shell, providing a premium autocomplete shell experience.

---

## ADR 005: Ruff and Ty for Code Quality

### Status
Accepted

### Context
We need quick linting, formatting, and type safety tools to guarantee code quality.

### Decision
We chose `ruff` for code linting/formatting, and `ty` (Astral's Rust-based mypy wrapper) for static type checking.

### Consequences
- Ruff provides extremely fast linting and formatting (under 10ms).
- `ty check` verifies PEP-compliant type annotations, catching bugs statically before running tests.

---

## ADR 006: Prek for Git Hook Management

### Status
Accepted

### Context
We need to run code quality tools locally on git commits to ensure no broken code is pushed.

### Decision
We chose `prek` (a Rust-based drop-in alternative to `pre-commit`) to manage local git hooks.

### Consequences
Prek provides faster hook installation and runtimes, executing checks for trailing whitespaces, EOF lines, TOML/YAML files, Ruff format/lint, and type checker before committing.

---

## ADR 007: GitHub Actions CI/CD with Native Actions and Automatic Releases

### Status
Accepted

### Context
We need a CI/CD pipeline to validate PRs and tag-triggered releases automatically.

### Decision
We use GitHub Actions with native actions (`astral-sh/ruff-action` for ruff linting, `j178/prek-action` for prek checks, and `softprops/action-gh-release` for releases). We also configured `cache-suffix` parameters on `setup-uv` steps to prevent parallel cache key conflicts.

### Consequences
Every PR is tested and verified. Tagging a commit with `v*` automatically triggers package builds (`uv build`) and creates a new GitHub release with built wheel and source distribution artifacts.
