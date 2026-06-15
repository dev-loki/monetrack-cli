# Concept: MonetRack CLI Investment Tracker

MonetRack is a terminal-based CLI tool designed to track your investments (stocks, ETFs, P2P loans, crypto, etc.) directly from the command line. It uses a local SQLite database stored in compliance with the XDG Base Directory specification.

---

## 1. Storage & Database Design

### SQLite Database
MonetRack uses **SQLite** as its storage engine:
- **No JSON**: Meets the requirement of using a non-JSON format.
- **Embedded & Zero Config**: Built directly into Python (`sqlite3`), making it highly portable.
- **Transactional Safety**: Protects data integrity during command executions.
- **Relational Capabilities**: Allows joins between assets, transactions, and snapshots for accurate financial reporting.

### XDG Directory Compliance
MonetRack stores its data in the standard XDG data directory:
- **Default Path**: `~/.local/share/monetrack/monetrack.db`
- The directory is initialized automatically if it doesn't exist.

### Database Schema

```mermaid
erDiagram
    ASSETS {
        integer id PK
        text name UNIQUE "e.g., Bondora Go & Grow, Core MSCI World ETF"
        text type "p2p, stock, etf, crypto, other"
        text isin "Optional International Securities Identification Number"
        text wkn "Optional Wertpapierkennnummer"
        text comment "Optional details"
    }
    TRANSACTIONS {
        integer id PK
        integer asset_id FK "References ASSETS"
        text timestamp "ISO8601 format"
        text type "invest or withdraw"
        real amount "EUR amount"
        text comment "Optional details"
    }
    SNAPSHOTS {
        integer id PK
        integer asset_id FK "References ASSETS"
        text timestamp "ISO8601 format"
        real value "Current total value of this asset in EUR"
        text comment "Optional details"
    }
```

---

## 2. CLI Command Design

We use `typer` to define the commands:

### Asset Management
1. **`asset create <name>`**
   - **Purpose**: Create a new asset (P2P platform, ETF, stock, etc.).
   - **Options**:
     - `--type` (Choices: `p2p`, `stock`, `etf`, `crypto`, `other`; default: `other`)
     - `--isin` (Optional, e.g., `IE00B4L5Y983`)
     - `--wkn` (Optional, e.g., `A0RPWH`)
     - `--comment` (Optional notes)
   - **Usage**: `monetrack asset create "Core MSCI World" --type etf --isin IE00B4L5Y983 --wkn A0RPWH`

2. **`asset list`**
   - **Purpose**: List all registered assets.
   - **Usage**: `monetrack asset list`

### Transaction & Snapshot Recording
3. **`invest <asset-name-or-id> <amount>`**
   - **Purpose**: Record money deposited or asset purchased.
   - **Options**: `--date` (ISO8601, defaults to today), `--comment`
   - **Usage**: `monetrack invest "Bondora Go & Grow" 250.00 --comment "Monthly deposit"`

4. **`withdraw <asset-name-or-id> <amount>`**
   - **Purpose**: Record money withdrawn or asset sold.
   - **Options**: `--date` (ISO8601, defaults to today), `--comment`
   - **Usage**: `monetrack withdraw "Monefit" 100.00`

5. **`snapshot <asset-name-or-id> <value>`**
   - **Purpose**: Log the current total value of the asset.
   - **Options**: `--date` (ISO8601, defaults to today), `--comment`
   - **Usage**: `monetrack snapshot "Core MSCI World" 1245.50`

### Statistics & Reporting
6. **`stats`**
   - **Purpose**: Show breakdown of earnings, net invested, and ROI.
   - **Options**:
     - `--by` (Choices: `asset`, `type`, `month`; default: `asset`)
     - `--asset` (Filter statistics to a specific asset)
     - `--month` (Filter statistics to a specific month, e.g., `2026-06`)
   - **Usage**: `monetrack stats --by asset`

### Interactive Mode
When `monetrack` is executed without any subcommands, it automatically starts a full-featured **Interactive Shell**:
- **Prompt**: Styled as `monetrack> ` in hot-pink and cyan.
- **Autocompletion**: Built-in tab-completion for all command names, subcommands, and options (e.g. `--by`, `--asset`).
- **Dynamic Asset Autocomplete**: Reads your assets (name, ISIN, WKN) directly from the database and updates autocomplete suggestions in real-time. E.g. typing `invest ` will show a dropdown of your actual registered investments.
- **Commands**: Supports all main CLI subcommands plus `help`, `exit`, and `quit`.


---

## 3. Financial Calculations

All values are tracked in **EUR**.

- **Net Invested**:
  $$\text{Net Invested} = \sum(\text{Investments}) - \sum(\text{Withdrawals})$$
- **Current Value**:
  The value of the most recent snapshot for the asset. If no snapshot exists, defaults to the net invested amount.
- **Total Earnings**:
  $$\text{Earnings} = \text{Current Value} - \text{Net Invested} + \text{Total Withdrawals (after final snapshot? No, Current Value is the value of the holdings. If we withdrew money, the holdings decreased, but the withdrew money went back to our bank, so our total return is Current Value - Net Invested)}$$
  *Note on mathematical consistency*: If we invest €1000, it grows to €1200. We withdraw €200. Net Invested is now €800 (€1000 - €200). Current Value of the remaining holdings is €1000. Earnings = Current Value (€1000) - Net Invested (€800) = €200. This is correct!
- **Monthly Earnings**:
  Calculated by tracking changes in snapshots and transaction flows within the month:
  $$\text{Earnings}_{\text{month}} = (\text{End Value} - \text{Start Value}) - (\text{Investments}_{\text{month}} - \text{Withdrawals}_{\text{month}})$$
  where $\text{Start Value}$ is the value at the beginning of the month (last snapshot of the previous month) and $\text{End Value}$ is the last snapshot of the current month.
