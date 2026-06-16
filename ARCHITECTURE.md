# MoneTrack CLI: Architecture Overview

MoneTrack has been refactored from a single-file implementation into a robust, type-safe Clean/Hexagonal Architecture. This structure guarantees that core business logic is isolated from database access details and command-line presentation, laying a seamless foundation to overlay a FastAPI API or another database in the future.

---

## 1. Directory Structure

The project directory structure is laid out under the `monetrack` package:

```
monetrack/
├── __init__.py
├── domain/                  # Core entities & models (Pure Python, zero dependencies)
│   ├── __init__.py
│   └── models.py            # Dataclasses (Asset, Transaction, Snapshot, Stats)
├── ports/                   # Interfaces (ports) and adapter implementations
│   ├── __init__.py
│   ├── db_port.py           # Protocol (DatabasePort)
│   └── db_adapter.py        # SQLite Database adapter implementation
├── services/                # Business logic services (coordination & core rules)
│   ├── __init__.py
│   └── portfolio_service.py # Portfolio calculations and CSV import/export orchestration
└── application/             # Presentation & entry points (CLI, Prompts, Shell)
    ├── __init__.py
    ├── cli.py               # Typer command definitions & sub-renderers
    ├── interactive.py       # prompt-toolkit shell & autocomplete session loop
    └── formatters.py        # CLI output helpers & vertical monthly growth charts
```

---

## 2. Layer Responsibilities

### A. Domain Layer (`monetrack.domain`)
- **Location**: [models.py](file:///Users/torstenzielke/Projects/monetrack/monetrack/domain/models.py)
- **Role**: Holds the raw domain entities (`Asset`, `Transaction`, `Snapshot`) and presentation models (`AssetStats`, `GlobalSummary`, `MonthlyStats`, `HistoryEvent`).
- **Dependencies**: None. It is decoupled from any libraries or frameworks.

### B. Ports Layer (`monetrack.ports`)
- **Location**: [db_port.py](file:///Users/torstenzielke/Projects/monetrack/monetrack/ports/db_port.py)
- **Role**: Defines the `DatabasePort` Protocol (interface).
- **SQLite Adapter**: [db_adapter.py](file:///Users/torstenzielke/Projects/monetrack/monetrack/ports/db_adapter.py) implements the port, handling SQLite-specific logic, queries, and migrations, mapping row inputs to domain dataclass instances.

### C. Services Layer (`monetrack.services`)
- **Location**: [portfolio_service.py](file:///Users/torstenzielke/Projects/monetrack/monetrack/services/portfolio_service.py)
- **Role**: Acts as the Application Service orchestrator. It receives commands, handles logic coordination (like verifying withdrawal boundaries or directory checking), and implements CSV import/export logic.
- **Dependencies**: Depends only on the abstract `DatabasePort` interface (which is injected at runtime), keeping the service 100% database-agnostic.

### D. Application/Presentation Layer (`monetrack.application`)
- **Location**: `monetrack.application`
- **Role**: Parses command-line inputs and runs the interactive shell session.
- **CLI Commands**: [cli.py](file:///Users/torstenzielke/Projects/monetrack/monetrack/application/cli.py) defines the `typer` subcommands, handles user input validation, and renders results using `rich` tables.
- **Interactive Prompts**: [interactive.py](file:///Users/torstenzielke/Projects/monetrack/monetrack/application/interactive.py) runs the custom autocomplete loop.
- **Visuals**: [formatters.py](file:///Users/torstenzielke/Projects/monetrack/monetrack/application/formatters.py) formats signs/ROI and draws the vertical growth chart.

---

## 3. Future Extension: Adding FastAPI
Because the service layer (`PortfolioService`) and domain models are completely database- and presentation-independent, exposing an HTTP API is trivial:
1. Create a `monetrack/application/api.py` (or similar) file.
2. Instantiate `PortfolioService(SQLiteDatabaseAdapter())`.
3. Declare FastAPI routes that invoke `service.get_global_summary()`, `service.list_assets()`, etc.
4. Return the dataclass instances directly (FastAPI automatically converts them to JSON).
