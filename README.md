# MonetRack CLI 📈

MonetRack is a premium command-line investment tracking tool designed to help you monitor and calculate the performance of your assets, deposits, and valuations.

## Features

- 💼 **Asset Management**: Organize and categorize assets by type, name, ISIN, WKN, or custom comments.
- 💸 **Transaction Logging**: Record deposits (investments) and withdrawals with timestamps.
- 📸 **Valuation Snapshots**: Log historical valuations of assets to track net value over time.
- 📊 **Performance Engine**: Calculate net invested value, current market value, total earnings, and return on investment (ROI %).
- 🗓️ **Monthly Aggregation**: Group financial statistics and earnings breakdown by month.
- 🎨 **Rich UI**: High-fidelity terminal tables and formatting powered by `rich`.
- ⌨️ **Interactive Shell**: Full autocomplete terminal interface with `prompt-toolkit`, dynamically matching asset names, ISINs, and WKNs from the database.
- 🚀 **Modern Tooling**: Developed using Python 3.14+ with `uv` package manager, `ruff` formatting, and `ty` type checking.

---

## Installation

MonetRack CLI uses the modern and fast Python package manager `uv`.

### Prerequisites
- Python >= 3.14
- [uv](https://github.com/astral-sh/uv)

### Setup
Clone the repository and install all dependencies:
```bash
git clone https://github.com/your-username/monetrack.git
cd monetrack
uv sync
```

---

## Usage

You can run MonetRack directly or launch the interactive autocomplete shell.

### Launch Interactive Shell
Running the command without any arguments launches the interactive autocomplete shell:
```bash
uv run monetrack
```

### CLI Commands

#### 1. Assets
- **Create an asset**:
  ```bash
  uv run monetrack asset create "My ETF" --type "ETF" --isin "IE00B4L5Y983" --comment "World ETF"
  ```
- **List all assets**:
  ```bash
  uv run monetrack asset list
  ```

#### 2. Transactions
- **Record an investment**:
  ```bash
  uv run monetrack invest "My ETF" 500.00 --date "2026-06-01" --comment "Monthly savings plan"
  ```
- **Record a withdrawal**:
  ```bash
  uv run monetrack withdraw "My ETF" 200.00 --date "2026-06-15"
  ```

#### 3. Snapshots
- **Log asset valuation**:
  ```bash
  uv run monetrack snapshot "My ETF" 520.00 --date "2026-06-16" --comment "Mid-month valuation check"
  ```

#### 4. Statistics & Overview
- **View investment overview & ROI**:
  ```bash
  uv run monetrack stats
  ```

---

## Development

We enforce code quality checks before commits using `prek`, `ruff`, and `ty`.

### Local Check Tools
- **Run Tests**:
  ```bash
  uv run pytest
  ```
- **Run Linter & Formatter**:
  ```bash
  uv run ruff check
  uv run ruff format
  ```
- **Run Type Checker**:
  ```bash
  uv run ty check
  ```
- **Run Prek Checks**:
  ```bash
  uv run prek run --all-files
  ```

---

## CI/CD Pipeline

MonetRack CLI is equipped with a modern GitHub Actions pipeline defined in `.github/workflows/ci.yml`.

- **On Pull Requests & Main Pushes**: Runs Ruff (lint/format), Prek hooks, Ty typechecker, and Pytest.
- **On Tag Pushes (e.g. `v*`)**: Automatically builds packages (`uv build`) and creates a new GitHub Release with the built wheel and source distributions.
