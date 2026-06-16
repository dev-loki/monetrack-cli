# Implementation Plan: MoneTrack CLI

This plan outlines the step-by-step development of the MoneTrack CLI investment tracking tool.

---

## Phase 1: Project Setup & XDG Config
- [x] Install required dependencies:
  - `rich` for beautiful terminal formatting and tables.
  - `platformdirs` for resolving standard XDG directories (`~/.local/share`).
  - `prompt-toolkit` for the interactive autocomplete shell.
- [x] Implement XDG base directory setup:
  - Create directory `~/.local/share/monetrack/` if it does not exist.
  - Set up a connection manager for `monetrack.db`.
- [x] Create database initialization script that runs automatically on CLI startup to verify and apply the schema (`assets`, `transactions`, `snapshots`).

## Phase 2: Database Layer & Schema
- [x] Implement SQLite schema and database access layer in a new module (`db.py`):
  - Table `assets`: `id` (INT PK), `name` (TEXT UNIQUE), `type` (TEXT), `isin` (TEXT), `wkn` (TEXT), `comment` (TEXT).
  - Table `transactions`: `id` (INT PK), `asset_id` (INT FK), `timestamp` (TEXT), `type` (TEXT), `amount` (REAL), `comment` (TEXT).
  - Table `snapshots`: `id` (INT PK), `asset_id` (INT FK), `timestamp` (TEXT), `value` (REAL), `comment` (TEXT).
- [x] Write helper functions to query assets (by name/id/isin/wkn), insert records, and calculate historical balances.

## Phase 3: Core CLI Commands
- [x] Set up `typer` CLI entry points in `main.py`.
- [x] Implement commands:
  - `asset create <name>`: Create a new asset (support `--type`, `--isin`, `--wkn`, `--comment`).
  - `asset list`: List all assets.
  - `invest <asset> <amount>`: Record cash deposit or buy order (support `--date`, `--comment`).
  - `withdraw <asset> <amount>`: Record cash withdrawal or sell order (support `--date`, `--comment`).
  - `snapshot <asset> <value>`: Log valuation of an asset (support `--date`, `--comment`).
- [x] Implement lookup matching to let the user refer to assets by their Name, ID, or ISIN/WKN.

## Phase 4: Statistics & Calculation Engine
- [x] Implement calculations for:
  - Net invested per service.
  - Current value per service (based on the latest snapshot).
  - Total earnings (valuation - net invested) per service.
- [x] Implement monthly aggregation:
  - Group transactions and snapshots by month.
  - Calculate earnings for each month.
- [x] Implement total statistics across all services.

## Phase 5: Terminal Output & Aesthetics
- [x] Integrate `rich` for premium CLI feedback.
- [x] Create beautiful output tables for:
  - Service overview (Service Name, Net Invested, Current Value, Profit/Loss, ROI %).
  - Monthly earnings breakdown.
  - Transaction log list.

## Phase 6: Interactive Mode with Autocomplete
- [x] Integrate `prompt-toolkit` with `NestedCompleter` for interactive mode.
- [x] Handle root command routing so typing just `monetrack` opens the shell.
- [x] Implement dynamic autocomplete that pulls asset names/ISINs/WKNs directly from the database and updates in real-time.
- [x] Build multi-subcommand autocomplete and nested flags (e.g. `stats --by ...`).

## Phase 7: Ruff & prek Setup
- [x] Install `ruff` and `prek` dev dependencies.
- [x] Configure Ruff formatting and lint rules (pycodestyle, pyflakes, bugbear, isort, etc.).
- [x] Create initial pre-commit config with hooks for whitespace, end-of-file, and Ruff.
- [x] Reformat and lint all code.

## Phase 8: Static Type Checking & Additional Git Hooks
- [x] Add Astral's `ty` Rust-based type checker to dev dependencies.
- [x] Configure and clean up all type errors in `db.py` to achieve zero type diagnostics.
- [x] Add additional native pre-commit-hooks (`check-ast`, `check-case-conflict`, `mixed-line-ending`, `detect-private-key`, `check-shebang-scripts-are-executable`).
- [x] Configure a local git hook in `.pre-commit-config.yaml` to run `ty check` on commit, securing type-safety before pushing.
- [x] Run `prek` to verify all hooks execute and pass successfully.
