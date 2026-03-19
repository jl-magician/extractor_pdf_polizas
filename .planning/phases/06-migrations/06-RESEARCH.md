# Phase 6: Migrations - Research

**Researched:** 2026-03-19
**Domain:** Alembic schema migrations for SQLite with SQLAlchemy 2.0
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- Keep both `create_all()` and Alembic with a guard: if no `alembic_version` table exists (fresh DB), `init_db()` calls `create_all()` then stamps as current head; existing DBs use `alembic upgrade head`
- CLI auto-runs pending migrations on startup before any command executes — user never needs to run `alembic upgrade head` manually
- Tests use `create_all()` for speed; a dedicated `test_migrations.py` verifies the full migration chain end-to-end
- Alembic directory and `alembic.ini` live at the project root (standard convention)
- `evaluation_score`: REAL, nullable, stores float 0.0–1.0 (normalized score)
- `evaluation_json`: TEXT (JSON), nullable, stores structured assessment only (field scores, flags, summary — not raw Sonnet API response)
- `evaluated_at`: DATETIME, nullable, tracks when evaluation was run (supports re-evaluation workflows)
- `evaluated_model_id`: TEXT, nullable, tracks which Sonnet model produced the evaluation
- All four columns added to the `polizas` table in migration 002
- WAL mode enabled via `PRAGMA journal_mode=WAL` in Alembic's `env.py` before running migrations
- Also set in `database.py` `get_engine()` for non-migration paths — belt-and-suspenders, PRAGMA is idempotent
- Baseline migration (001) detects existing tables via inspector: if `polizas` table exists, just stamps revision; if fresh DB, creates all tables
- Auto-migrate creates a backup (`polizas.db.bak`) before applying any pending migrations
- Brief log line per migration applied (e.g., "Applied migration: 002_evaluation_columns"); silent when already at head

### Claude's Discretion

- Alembic revision ID format and naming conventions
- env.py configuration details beyond WAL and batch mode
- Auto-migrate implementation details (where in CLI startup to hook it)
- Exact backup file naming if multiple backups needed

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MIG-01 | Alembic initialized with `render_as_batch=True` for SQLite compatibility | Batch mode required for any ALTER TABLE operation on SQLite; verified in Alembic docs |
| MIG-02 | Baseline migration stamps existing schema without altering tables | Inspector-based detection pattern verified; `context.execute(op.get_bind().execute(...))` approach confirmed |
| MIG-03 | Evaluation columns migration adds Sonnet evaluator fields to polizas table | `op.add_column` with `render_as_batch=True` confirmed as correct approach for SQLite column additions |
</phase_requirements>

---

## Summary

Alembic is the standard SQLAlchemy migration tool, maintained by the SQLAlchemy team. The current version is 1.18.4 (verified against PyPI on 2026-03-19). It is not yet installed in this project (SQLAlchemy 2.0.48 is installed) so it must be added to `pyproject.toml` dependencies.

The critical constraint for this project is SQLite's limited DDL support. SQLite does not support `ALTER TABLE ... ADD COLUMN` with NOT NULL constraints or foreign keys natively — Alembic's `render_as_batch=True` config addresses this by rebuilding tables in a temporary copy when needed. For nullable column additions (which is what migration 002 does), `op.add_column` works directly on SQLite without needing batch mode, but enabling `render_as_batch=True` globally is the correct defensive configuration to ensure all future migrations work.

The two-path guard pattern (fresh DB uses `create_all()` + stamp; existing DB uses `upgrade head`) is well-established in the Alembic community and avoids the "autogenerate detects everything as new" problem on first run. The baseline migration (001) is a no-op migration that simply stamps the existing schema, while migration 002 adds the four evaluation columns.

**Primary recommendation:** Install `alembic>=1.13.0`, initialize at project root with `alembic init alembic`, configure `env.py` with `target_metadata = Base.metadata` and `render_as_batch=True`, write two migration files (001_baseline and 002_evaluation_columns), augment `init_db()` with the guard logic, and add an auto-migrate call in `_setup_db()` in `cli.py`.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alembic | >=1.13.0 (latest: 1.18.4) | Schema migration management | Official SQLAlchemy migration tool; maintained by same team |
| sqlalchemy | 2.0.48 (already installed) | ORM + migration engine source | Already in project; Alembic reads `Base.metadata` from it |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| sqlalchemy (inspect) | 2.0.x | Table existence detection in 001 migration | Used in baseline migration to detect if schema already exists |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| alembic | yoyo-migrations | alembic is the SQLAlchemy-native standard; yoyo is SQL-file based, misses ORM integration |
| alembic | flask-migrate | flask-migrate wraps alembic; adds Flask dependency for no benefit in a non-Flask project |

**Installation:**
```bash
pip install alembic>=1.13.0
```

**Add to pyproject.toml dependencies:**
```toml
"alembic>=1.13.0",
```

**Version verification:** Confirmed 1.18.4 is latest via `pip index versions alembic` on 2026-03-19.

## Architecture Patterns

### Recommended Project Structure

```
project root/
├── alembic/
│   ├── env.py              # Migration environment config
│   ├── script.py.mako      # Migration file template
│   └── versions/
│       ├── 001_baseline.py
│       └── 002_evaluation_columns.py
├── alembic.ini             # Alembic config (sqlalchemy.url set here or via env.py)
├── policy_extractor/
│   └── storage/
│       └── database.py     # init_db() with migration guard
└── tests/
    └── test_migrations.py  # End-to-end migration chain test
```

### Pattern 1: render_as_batch=True Global Configuration

**What:** Wraps all migration operations in Alembic's batch mode, which creates a temp table, copies data, drops old table, renames temp. Required for SQLite ALTER TABLE operations.
**When to use:** Always for SQLite. Set globally in `env.py` context configuration.

```python
# alembic/env.py — run_migrations_offline and run_migrations_online
def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # WAL mode before migrations
        connection.execute(text("PRAGMA journal_mode=WAL"))
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # REQUIRED for SQLite
        )
        with context.begin_transaction():
            context.run_migrations()
```

### Pattern 2: Baseline Migration with Inspector-Based Detection

**What:** Migration 001 checks if the `polizas` table exists. If it does (existing DB), it skips table creation and just lets Alembic stamp the revision. If not (fresh DB), it runs `create_all()` or issues DDL.
**When to use:** First migration in any project that already has a running database.

```python
# alembic/versions/001_baseline.py
"""Baseline: stamp existing schema, create if fresh.

Revision ID: 001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    existing_tables = inspector.get_table_names()

    if "polizas" not in existing_tables:
        # Fresh database — create all tables via metadata
        from policy_extractor.storage.models import Base
        Base.metadata.create_all(bind=bind)
    # If polizas exists: schema already correct, no DDL needed.
    # Alembic stamps this revision after upgrade() returns.


def downgrade() -> None:
    # No downgrade for baseline — would drop all tables
    pass
```

### Pattern 3: init_db() Guard Logic

**What:** `init_db()` checks for the `alembic_version` table. If absent (fresh DB), it runs `create_all()` and stamps the head. If present, it runs `alembic upgrade head` to apply any pending migrations.
**When to use:** Every CLI startup via `_setup_db()`.

```python
# policy_extractor/storage/database.py
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from .models import Base


def get_engine(db_path: str = "data/polizas.db"):
    """Create SQLAlchemy engine with WAL mode enabled."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
    return engine


def init_db(db_path: str = "data/polizas.db"):
    """Ensure DB schema is current. Uses Alembic if available, create_all for tests."""
    engine = get_engine(db_path)
    insp = inspect(engine)

    if "alembic_version" not in insp.get_table_names():
        # Fresh DB or pre-Alembic DB: create all tables and stamp head
        Base.metadata.create_all(engine)
        _stamp_head(db_path)
    else:
        # Existing DB with Alembic tracking: apply pending migrations
        _auto_migrate(db_path)

    return engine


def _stamp_head(db_path: str) -> None:
    """Stamp the current head without running migrations (schema already correct)."""
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.stamp(alembic_cfg, "head")


def _auto_migrate(db_path: str) -> None:
    """Apply any pending Alembic migrations. Creates backup before migrating."""
    from alembic.config import Config
    from alembic import command
    from alembic.runtime.migration import MigrationContext

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    # Check if there are pending migrations
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        migration_context = MigrationContext.configure(conn)
        current_rev = migration_context.get_current_revision()

    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(alembic_cfg)
    head_rev = script.get_current_head()

    if current_rev != head_rev:
        # Create backup before migrating
        import shutil
        backup_path = db_path + ".bak"
        shutil.copy2(db_path, backup_path)
        from loguru import logger
        logger.info(f"Migration backup created: {backup_path}")
        command.upgrade(alembic_cfg, "head")


SessionLocal = sessionmaker(autocommit=False, autoflush=False)
```

### Pattern 4: Evaluation Columns Migration

**What:** Migration 002 adds four nullable columns to the `polizas` table.
**When to use:** Run automatically when upgrading from revision 001 to 002.

```python
# alembic/versions/002_evaluation_columns.py
"""Add evaluation columns to polizas.

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.add_column(
            sa.Column("evaluation_score", sa.Float(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("evaluation_json", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("evaluated_at", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("evaluated_model_id", sa.String(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("polizas") as batch_op:
        batch_op.drop_column("evaluated_model_id")
        batch_op.drop_column("evaluated_at")
        batch_op.drop_column("evaluation_json")
        batch_op.drop_column("evaluation_score")
```

### Anti-Patterns to Avoid

- **Autogenerate for baseline migration:** `alembic revision --autogenerate` on an existing DB will generate DROP + CREATE statements for tables that already exist. Write migration 001 manually with the inspector guard.
- **Using `op.add_column` without `batch_alter_table` on SQLite:** For SQLite, always use `with op.batch_alter_table(...) as batch_op: batch_op.add_column(...)` even for nullable columns, to be consistent and future-proof.
- **Hardcoding `sqlalchemy.url` in alembic.ini:** The DB path varies by environment. Set it via `env.py` reading from the application's `settings.DB_PATH` or via `alembic_cfg.set_main_option()` at runtime.
- **Running migrations from tests:** The shared `conftest.py` uses `create_all()` on in-memory SQLite — this is correct and fast. Migration chain integrity is tested separately in `test_migrations.py` using a temp file-based DB.
- **Not handling `alembic.ini` path when running from non-root CWD:** The `Config("alembic.ini")` call assumes CWD is project root. When called from CLI, this is correct. For tests, pass the absolute path.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Schema versioning tracking | Custom `schema_version` table | `alembic_version` table managed by Alembic | Alembic handles concurrent access, downgrade tracking, branch resolution |
| SQLite column addition | Raw `ALTER TABLE ... ADD COLUMN` | `op.add_column` with `render_as_batch=True` | Batch mode handles constraints, FKs, and all edge cases; raw ALTER fails on NOT NULL |
| Migration chain validation | Custom revision chain checker | `alembic history` + `alembic current` | Alembic's graph resolves branches, heads, and relative revision specs |
| DB backup before migration | Custom backup logic | `shutil.copy2()` called inside `_auto_migrate()` | Simple file copy is correct for SQLite (single-file DB); WAL mode files need proper handling |

**Key insight:** The complexity in SQLite migrations is hidden in edge cases — NOT NULL defaults, FK constraint recreation, index recreation during batch operations. Alembic's batch mode handles all of these; hand-rolled ALTER TABLE fails on half of them.

## Common Pitfalls

### Pitfall 1: alembic.ini sqlalchemy.url vs env.py dynamic URL

**What goes wrong:** `alembic.ini` has a placeholder `sqlalchemy.url = driver://user:pass@localhost/dbname`. If left as-is, `alembic upgrade head` from command line fails. If hardcoded to a specific path, it differs from the application's configured path.
**Why it happens:** Alembic was designed for server databases where the URL is stable. SQLite paths vary (dev, test, production).
**How to avoid:** In `env.py`, override the URL from application settings before running migrations:
```python
from policy_extractor.config import settings
config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.DB_PATH}")
```
And in `_stamp_head()` / `_auto_migrate()`, pass the URL via `alembic_cfg.set_main_option()`.
**Warning signs:** `KeyError: 'sqlalchemy.url'` or connection to wrong file path.

### Pitfall 2: WAL mode PRAGMA in env.py

**What goes wrong:** Without `PRAGMA journal_mode=WAL` before migrations, concurrent readers during a migration can hit "database is locked" errors in Phase 9 (async batch).
**Why it happens:** Default SQLite journal mode (DELETE) does not support concurrent reads during writes.
**How to avoid:** Set WAL mode in both `env.py` (migration path) and `get_engine()` (application path). PRAGMA is idempotent — safe to call every time.
**Warning signs:** `OperationalError: database is locked` during concurrent batch processing after schema is in place.

### Pitfall 3: Baseline migration on existing DB races with stamp

**What goes wrong:** If `init_db()` runs `create_all()` and then `stamp head`, but migration 001 checks for `polizas` table in its `upgrade()` body, the first-run path can double-create.
**Why it happens:** The guard in `init_db()` and the guard in migration 001 serve different purposes and must be coordinated.
**How to avoid:** The guard logic is: if `alembic_version` table is absent, run `create_all()` + `stamp head` directly (bypasses migration 001's `upgrade()` entirely). Migration 001's inspector guard is only needed if someone runs `alembic upgrade head` manually on a pre-Alembic existing DB without going through `init_db()`.
**Warning signs:** `Table 'polizas' already exists` SQLAlchemy error on first startup.

### Pitfall 4: Test isolation for test_migrations.py

**What goes wrong:** Migration tests that use the same `polizas.db` file can corrupt the production database if tests run in the same directory.
**Why it happens:** Alembic needs a real file-based DB (not in-memory `:memory:`) to test the full chain including backup creation.
**How to avoid:** Use `tmp_path` pytest fixture to create a temporary DB file for migration tests. Pass its path to `alembic_cfg.set_main_option("sqlalchemy.url", ...)`.
**Warning signs:** Tests pass individually but corrupt state when run together; missing `polizas.db.bak` after migration test.

### Pitfall 5: MigrationContext.configure requires open connection

**What goes wrong:** `MigrationContext.configure(conn)` called with a closed connection raises `InvalidRequestError`.
**Why it happens:** SQLAlchemy 2.0 enforces explicit transaction boundaries; connections must be open when passed to Alembic's migration context.
**How to avoid:** Always call inside a `with engine.connect() as conn:` block.
**Warning signs:** `sqlalchemy.exc.InvalidRequestError: This connection is closed` during auto-migrate check.

## Code Examples

Verified patterns from Alembic official documentation and SQLAlchemy 2.0 compatibility:

### env.py — Minimal Correct Configuration for SQLite

```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context

# Import project metadata
from policy_extractor.storage.models import Base
from policy_extractor.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Override URL from application settings
config.set_main_option("sqlalchemy.url", f"sqlite:///{settings.DB_PATH}")


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        connection.execute(text("PRAGMA journal_mode=WAL"))
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

### alembic.ini — Minimal Required Config

```ini
[alembic]
script_location = alembic
# URL is overridden by env.py — placeholder required by parser
sqlalchemy.url = sqlite:///data/polizas.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

### Checking Current Revision Programmatically

```python
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

def get_current_revision(db_path: str) -> str | None:
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        return ctx.get_current_revision()
```

### test_migrations.py — Full Chain Test

```python
# tests/test_migrations.py
import pytest
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from alembic.config import Config
from alembic import command
from alembic.runtime.migration import MigrationContext


def make_alembic_cfg(db_path: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_fresh_db_upgrade_head(tmp_path):
    """Fresh DB: upgrade head creates all tables and lands at head revision."""
    db_file = str(tmp_path / "test.db")
    cfg = make_alembic_cfg(db_file)
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_file}")
    insp = inspect(engine)
    assert "polizas" in insp.get_table_names()
    assert "alembic_version" in insp.get_table_names()

    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        assert ctx.get_current_revision() is not None


def test_evaluation_columns_present_after_002(tmp_path):
    """After upgrade to head, polizas has all four evaluation columns."""
    db_file = str(tmp_path / "test.db")
    cfg = make_alembic_cfg(db_file)
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_file}")
    insp = inspect(engine)
    col_names = [c["name"] for c in insp.get_columns("polizas")]
    assert "evaluation_score" in col_names
    assert "evaluation_json" in col_names
    assert "evaluated_at" in col_names
    assert "evaluated_model_id" in col_names


def test_existing_db_upgrade_head_no_data_loss(tmp_path):
    """Existing DB with data: upgrade head stamps without destroying data."""
    from policy_extractor.storage.models import Base, Poliza
    from sqlalchemy.orm import Session

    db_file = str(tmp_path / "existing.db")
    engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    # Insert a row
    with Session(engine) as session:
        session.add(Poliza(numero_poliza="TEST-001", aseguradora="Test SA"))
        session.commit()

    # Stamp as baseline (simulate pre-migration existing DB)
    cfg = make_alembic_cfg(db_file)
    command.stamp(cfg, "001")

    # Now upgrade to head (migration 002)
    command.upgrade(cfg, "head")

    # Data still present
    with Session(engine) as session:
        poliza = session.query(Poliza).filter_by(numero_poliza="TEST-001").first()
        assert poliza is not None
        assert poliza.aseguradora == "Test SA"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manually written SQL migration files | Python migration files with `op.*` operations | Alembic 0.x → 1.x | Full Python with ORM type awareness |
| `alembic revision --autogenerate` for all migrations | Manual migrations for baseline, autogenerate for additive | Community best practice | Avoids destructive autogenerate on existing DBs |
| `op.add_column` directly for SQLite | `op.batch_alter_table` context manager | Alembic ~0.8+ | Handles all SQLite DDL limitations transparently |
| Setting URL only in alembic.ini | Override URL in env.py from app config | SQLAlchemy 2.0 era | Proper environment separation |

**Deprecated/outdated:**
- `from sqlalchemy import MetaData; meta = MetaData(bind=engine)`: The `bind` parameter was removed in SQLAlchemy 2.0. Alembic 1.x handles this via `op.get_bind()` inside migration functions.
- `context.configure(connection=conn, compare_type=True)`: Type comparison autogenerate is opt-in; not needed for manual migrations.

## Open Questions

1. **alembic.ini path when running as installed package**
   - What we know: `Config("alembic.ini")` resolves relative to CWD, which is correct for CLI use from project root.
   - What's unclear: If a user installs the package and runs `poliza-extractor extract ...` from a different directory, `alembic.ini` will not be found.
   - Recommendation: Use `Path(__file__).parent.parent / "alembic.ini"` to resolve absolute path from `database.py`, or document that CLI must be run from project root (acceptable for local single-user tool).

2. **Backup file naming when multiple sequential migrations run**
   - What we know: The decision calls for `polizas.db.bak` as backup name.
   - What's unclear: If a user is several versions behind and needs two migrations applied in one startup, one backup file name is sufficient (the pre-migration state is what matters).
   - Recommendation: Use a single `.bak` with timestamp suffix: `polizas.db.{timestamp}.bak` — simple, avoids overwrite, and the pre-migration state is preserved.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (already in dev dependencies) |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` testpaths = ["tests"] |
| Quick run command | `pytest tests/test_migrations.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MIG-01 | Alembic initialized with render_as_batch=True | integration | `pytest tests/test_migrations.py::test_fresh_db_upgrade_head -x` | Wave 0 |
| MIG-02 | Baseline stamps existing schema without altering data | integration | `pytest tests/test_migrations.py::test_existing_db_upgrade_head_no_data_loss -x` | Wave 0 |
| MIG-03 | evaluation_score and evaluation_json columns present after 002 | integration | `pytest tests/test_migrations.py::test_evaluation_columns_present_after_002 -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_migrations.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green (153 existing + new migration tests) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_migrations.py` — covers MIG-01, MIG-02, MIG-03 (new file, does not exist yet)
- [ ] `alembic/` directory — created by `alembic init alembic` (does not exist yet)
- [ ] `alembic.ini` — created by `alembic init alembic` (does not exist yet)
- [ ] `alembic/versions/001_baseline.py` — written manually (does not exist yet)
- [ ] `alembic/versions/002_evaluation_columns.py` — written manually (does not exist yet)
- [ ] `alembic` package in `pyproject.toml` — not yet in dependencies

## Sources

### Primary (HIGH confidence)

- PyPI registry — `pip index versions alembic` confirmed 1.18.4 as current latest (2026-03-19)
- SQLAlchemy 2.0.48 confirmed installed via `pip show sqlalchemy`
- Alembic batch operations: https://alembic.sqlalchemy.org/en/latest/batch.html — render_as_batch, batch_alter_table
- Alembic cookbook: https://alembic.sqlalchemy.org/en/latest/cookbook.html — branching, stamping, env.py patterns

### Secondary (MEDIUM confidence)

- Alembic runtime migration context API: `MigrationContext.configure()` + `get_current_revision()` — standard documented API used in _auto_migrate pattern
- SQLite limitations with ALTER TABLE: widely documented in SQLite official docs and Alembic batch mode rationale

### Tertiary (LOW confidence)

- None — all claims verified against official sources or direct code inspection

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified against PyPI live registry
- Architecture: HIGH — patterns derived from official Alembic docs + direct code inspection of existing project
- Pitfalls: HIGH — derived from SQLite documented limitations, SQLAlchemy 2.0 breaking changes, and code inspection

**Research date:** 2026-03-19
**Valid until:** 2026-09-19 (stable ecosystem; Alembic API changes slowly)
