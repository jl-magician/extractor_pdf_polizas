# Phase 1: Foundation - Research

**Researched:** 2026-03-18
**Domain:** Pydantic v2 data modeling, SQLAlchemy 2.0 schema design, Python project scaffolding
**Confidence:** HIGH — all patterns drawn from project pre-research (STACK.md, ARCHITECTURE.md, PITFALLS.md) verified against PyPI and official docs on 2026-03-17; no new uncertain unknowns for this phase.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Insured parties model:**
- A single policy can have BOTH persons and assets insured simultaneously (e.g., auto policy lists driver + vehicle)
- Person attributes: nombre completo, edad/fecha de nacimiento, RFC, CURP, dirección, parentesco con contratante
- Asset types: vehículos (marca, modelo, año, placas, VIN), inmuebles (dirección, tipo construcción, m2), otros bienes (descripción, número de serie, valor)
- Model as a single `asegurados` table with a `tipo` discriminator column (persona/bien) — shared fields (nombre/descripción) plus type-specific fields in JSON overflow column on the asegurado record itself
- No equipment/machinery type needed — only vehículos, inmuebles, and "otro"

**Coverage structure:**
- Core fields per coverage: nombre de cobertura, suma asegurada, deducible
- Some insurers add extra fields (coaseguro, copago, prima individual, periodo de espera) — handle via JSON overflow on coverage record
- Typical range: 5–20 coverages per policy
- Model as a `coberturas` table (one-to-many from policy) with core typed columns + JSON overflow for insurer-specific extras

**Core vs overflow fields:**
- Core typed columns (filterable): número de póliza, aseguradora, tipo de seguro, fecha de emisión, inicio de vigencia, fin de vigencia, nombre del agente, nombre del contratante, prima total
- Also core but less filtered: forma de pago, frecuencia de pago, moneda
- JSON overflow (informativo, no filtrable): VIN, placas, m2, tipo de construcción, RFC del contratante, datos específicos por tipo de seguro
- ALL fields selected for filtering → proper indexed columns

**Project conventions:**
- Package name: `policy_extractor`
- Code language: English (variables, functions, class names)
- Domain terms: Spanish — `contratante`, `asegurado`, `cobertura`, `vigencia`, `prima`, `deducible` kept in Spanish for field names in Pydantic models and database columns
- Comments: English
- Directory structure: Claude's discretion following Python best practices

### Claude's Discretion
- Exact directory/module structure within `policy_extractor/`
- SQLAlchemy model naming conventions
- Migration strategy (Alembic or manual for v1)
- Test framework choice
- Development tooling (linting, formatting)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | Database schema supports multiple insured parties (people or assets) per policy via relational table | Single `asegurados` table with `tipo` discriminator + FK to `polizas`; one-to-many relationship prevents flat-schema pitfall |
| DATA-02 | Schema supports dynamic/variable fields per insurer type via JSON overflow column | `campos_adicionales` JSON column on `polizas`, `asegurados`, and `coberturas`; SQLAlchemy `JSON` type maps to SQLite TEXT with automatic serialization |
| DATA-03 | All dates are stored in canonical ISO format regardless of source format | Pydantic `date` field type serializes as `YYYY-MM-DD`; SQLAlchemy `Date` column; Pydantic `field_validator` normalizes DD/MM/YYYY → ISO on ingest |
| DATA-04 | All monetary amounts are stored with explicit currency code | `prima_total: Decimal` paired with `moneda: str` (default "MXN"); same pattern on `coberturas.suma_asegurada` + `coberturas.moneda`; use `Decimal` not `float` |
| DATA-05 | System stores the raw Claude API response for each extraction (provenance logging) | `source_file_hash`, `model_id`, `prompt_version`, `extracted_at` columns on `polizas` table; raw JSON response saved to `data/raw/{hash}.json` |
</phase_requirements>

---

## Summary

Phase 1 establishes the non-retrofittable data contracts before any extraction code is written. Its entire value is prevention: three of the eight critical pitfalls documented in PITFALLS.md — flat insured schema, date/currency format inconsistency, and missing provenance — can only be avoided by getting the schema right in this phase. Retrofitting any of these after data is in production has HIGH recovery cost.

The work is pure Python: Pydantic v2 models defining the extraction contract, SQLAlchemy 2.0 table definitions for the SQLite database, and project scaffolding (`policy_extractor` package, pyproject.toml, uv environment). No LLM calls, no API costs, no external binaries required.

The key design insight is a three-level JSON overflow strategy. Every table (polizas, asegurados, coberturas) carries a `campos_adicionales` JSON column for insurer-specific extras. The core typed columns are limited to fields that will actually be queried or filtered. This avoids both the EAV anti-pattern (50+ nullable columns for every possible insurer field) and the blob anti-pattern (storing everything in one JSON and losing queryability). The `asegurados` table uses a single-table inheritance pattern with a `tipo` discriminator column — one row per insured party, whether person or asset — matching the user's locked decision.

**Primary recommendation:** Write Pydantic models first, derive SQLAlchemy models from them (or write them in parallel), keep domain terms in Spanish for field names, and lock canonical formats (ISO dates, Decimal + currency code) as Pydantic type annotations — not just documentation.

---

## Standard Stack

### Core (Phase 1 specific)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pydantic | 2.12.5 | Extraction schema + validation | Industry standard for typed models; `instructor` (Phase 3) requires pydantic v2; defines the contract for all downstream phases |
| SQLAlchemy | 2.0.48 | ORM + SQLite schema | 2.0 declarative style; same code targets SQLite now, PostgreSQL later; `JSON` column type handles overflow fields |
| Python | 3.11+ | Runtime | Required by ocrmypdf 17.x; best Windows ecosystem stability |
| uv | latest | Package manager + venv | Faster than pip on Windows; lock file reproducibility; use `uv sync` |
| python-dotenv | 1.0.1 | Environment variables | Store `ANTHROPIC_API_KEY` outside code; required before Phase 3 |

### Supporting (scaffolding + development)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | latest | Test runner | Validate schema round-trips and DB table creation in Phase 1 |
| ruff | latest | Linter + formatter | Replaces black + flake8 + isort; configure in pyproject.toml |
| alembic | 1.15.x | Schema migrations | Discretionary for v1 — manual `Base.metadata.create_all()` is acceptable for Phase 1 since there is no existing DB to migrate |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLAlchemy ORM | SQLModel | SQLModel is a thin pydantic+sqlalchemy bridge; lower boilerplate but less mature; SQLAlchemy direct gives more control over column types and JSON handling |
| SQLAlchemy ORM | raw sqlite3 | sqlite3 is built-in and zero-dependency, but loses type mapping, query building, and PostgreSQL migration path |
| `Decimal` for monetary amounts | `float` | `float` has IEEE 754 rounding errors (e.g., 1500000.00 becomes 1499999.9999...) — never use float for financial values |
| `date` type for dates | `str` | Storing dates as strings loses sortability, range queries, and format validation |

**Installation:**
```bash
# From project root
uv venv
uv pip install pydantic==2.12.5 sqlalchemy==2.0.48 python-dotenv==1.0.1 alembic
uv pip install --dev pytest ruff
```

---

## Architecture Patterns

### Recommended Project Structure

```
extractor_pdf_polizas/
├── pyproject.toml               # Package metadata, dependencies, ruff config
├── .env.example                 # Template: ANTHROPIC_API_KEY=, DB_PATH=
├── .gitignore                   # .env, data/raw/, *.db, .venv/
│
├── policy_extractor/
│   ├── __init__.py
│   ├── config.py                # Settings from env (DB_PATH, API_KEY, LOG_LEVEL)
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── poliza.py            # PolicyExtraction Pydantic model (extraction contract)
│   │   ├── asegurado.py         # AseguradoExtraction — persona + bien discriminated union
│   │   └── cobertura.py         # CoberturaExtraction model
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLAlchemy engine + session factory + Base
│   │   ├── models.py            # ORM table definitions (Poliza, Asegurado, Cobertura)
│   │   └── migrations/          # Alembic env.py + initial migration (if using alembic)
│   │
│   ├── ingestion/               # Placeholder __init__.py — implemented Phase 2
│   ├── extraction/              # Placeholder __init__.py — implemented Phase 3
│   ├── validation/              # Placeholder __init__.py — implemented Phase 5
│   └── api/                     # Placeholder __init__.py — implemented Phase 6
│
├── data/
│   ├── raw/                     # Raw Claude API responses: {sha256_hash}.json
│   ├── input/                   # Drop folder for PDFs to process
│   └── .gitkeep                 # Keep data/ tracked but empty in git
│
└── tests/
    ├── __init__.py
    ├── conftest.py               # Shared fixtures: in-memory SQLite engine, sample models
    ├── test_schemas.py           # Pydantic model validation, date normalization, currency
    └── test_models.py            # SQLAlchemy table creation, FK constraints, JSON column
```

### Pattern 1: Pydantic v2 Model with Discriminated Union for Asegurados

**What:** A single `AseguradoExtraction` model uses `tipo` as a `Literal` discriminator. Both persons and assets are represented, type-specific fields live in `campos_adicionales` on the same record. Matches the user's locked decision: single `asegurados` table, `tipo` discriminator column.

**When to use:** Always — this is the locked schema decision.

```python
# policy_extractor/schemas/asegurado.py
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date

class AseguradoExtraction(BaseModel):
    """Single insured party — either a person (persona) or an asset (bien)."""
    tipo: Literal["persona", "bien"]

    # Shared field — person name or asset description
    nombre_descripcion: str

    # Person-specific (None for assets)
    fecha_nacimiento: Optional[date] = None
    rfc: Optional[str] = None
    curp: Optional[str] = None
    direccion: Optional[str] = None
    parentesco: Optional[str] = None  # parentesco con contratante

    # Asset-specific extras go in campos_adicionales rather than typed columns
    # because they vary by asset type (vehículo vs inmueble vs otro)
    # Examples: {"tipo_bien": "vehiculo", "marca": "Toyota", "modelo": "Corolla",
    #            "anio": 2022, "placas": "ABC1234", "vin": "1HGCM82633A004352"}
    campos_adicionales: dict = Field(default_factory=dict)

    class Config:
        # Allow Claude to return extra fields — they go to campos_adicionales
        # Note: use model_config = ConfigDict(extra="ignore") in Pydantic v2
        pass
```

### Pattern 2: Pydantic v2 Date Normalization with field_validator

**What:** Use Pydantic's `field_validator` to accept multiple date formats from insurers and always store as `datetime.date` (ISO 8601 when serialized). The validator runs before type coercion, catching string inputs like "15/01/2025" or "enero 15, 2025".

**When to use:** On ALL date fields in PolicyExtraction and AseguradoExtraction.

```python
# policy_extractor/schemas/poliza.py  (excerpt)
from pydantic import BaseModel, field_validator
from datetime import date, datetime
from typing import Optional

class PolicyExtraction(BaseModel):
    fecha_emision: Optional[date] = None
    inicio_vigencia: Optional[date] = None
    fin_vigencia: Optional[date] = None

    @field_validator("fecha_emision", "inicio_vigencia", "fin_vigencia", mode="before")
    @classmethod
    def parse_date(cls, v):
        """Normalize DD/MM/YYYY, MM/DD/YYYY, and ISO 8601 to date objects."""
        if v is None or isinstance(v, date):
            return v
        if isinstance(v, str):
            # Try ISO 8601 first (Claude should return this if prompted correctly)
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(v, fmt).date()
                except ValueError:
                    continue
        raise ValueError(f"Cannot parse date: {v!r}")
```

### Pattern 3: Decimal + Currency Code for Monetary Fields

**What:** Use Python `Decimal` (not `float`) for all monetary amounts. Pair every monetary field with a currency code field defaulting to "MXN". This satisfies DATA-04 and prevents IEEE 754 rounding errors on financial values.

**When to use:** On `prima_total`, `coberturas.suma_asegurada`, `coberturas.deducible`, and any other monetary field.

```python
# policy_extractor/schemas/poliza.py  (excerpt)
from decimal import Decimal
from typing import Optional

class PolicyExtraction(BaseModel):
    prima_total: Optional[Decimal] = None
    moneda: str = "MXN"  # ISO 4217 currency code
    # ...

# policy_extractor/schemas/cobertura.py
class CoberturaExtraction(BaseModel):
    nombre_cobertura: str
    suma_asegurada: Optional[Decimal] = None
    deducible: Optional[Decimal] = None
    moneda: str = "MXN"
    campos_adicionales: dict = Field(default_factory=dict)
    # ^ coaseguro, copago, prima_individual, periodo_espera go here
```

### Pattern 4: SQLAlchemy 2.0 Declarative Models with JSON Column

**What:** SQLAlchemy 2.0 declarative style with `mapped_column` and `Mapped` type annotations. Use `JSON` type for overflow columns — SQLAlchemy serializes/deserializes automatically. Foreign keys from `asegurados` and `coberturas` to `polizas`.

**When to use:** These are the canonical ORM table definitions for the entire project.

```python
# policy_extractor/storage/models.py
from sqlalchemy import String, Numeric, Date, DateTime, JSON, ForeignKey, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

class Base(DeclarativeBase):
    pass

class Poliza(Base):
    __tablename__ = "polizas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # --- Core filterable columns ---
    numero_poliza: Mapped[str] = mapped_column(String, index=True)
    aseguradora: Mapped[str] = mapped_column(String, index=True)
    tipo_seguro: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    fecha_emision: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    inicio_vigencia: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    fin_vigencia: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    nombre_agente: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    nombre_contratante: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Monetary ---
    prima_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2), nullable=True)
    moneda: Mapped[str] = mapped_column(String(3), default="MXN")  # ISO 4217

    # --- Payment info (core but less filtered) ---
    forma_pago: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    frecuencia_pago: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # --- Provenance (DATA-05) ---
    source_file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    model_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # --- JSON overflow (DATA-02) ---
    campos_adicionales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # Raw Claude response stored in data/raw/{source_file_hash}.json (not in DB)

    # --- Relationships ---
    asegurados: Mapped[list["Asegurado"]] = relationship("Asegurado", back_populates="poliza", cascade="all, delete-orphan")
    coberturas: Mapped[list["Cobertura"]] = relationship("Cobertura", back_populates="poliza", cascade="all, delete-orphan")


class Asegurado(Base):
    __tablename__ = "asegurados"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id"), index=True)

    # Discriminator (DATA-01)
    tipo: Mapped[str] = mapped_column(String)  # "persona" | "bien"
    nombre_descripcion: Mapped[str] = mapped_column(String)

    # Person fields (nullable — also used for None when tipo="bien")
    fecha_nacimiento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rfc: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    curp: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    direccion: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    parentesco: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Type-specific extras (asset details, additional person fields)
    campos_adicionales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    poliza: Mapped["Poliza"] = relationship("Poliza", back_populates="asegurados")


class Cobertura(Base):
    __tablename__ = "coberturas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    poliza_id: Mapped[int] = mapped_column(ForeignKey("polizas.id"), index=True)

    nombre_cobertura: Mapped[str] = mapped_column(String)
    suma_asegurada: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2), nullable=True)
    deducible: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=15, scale=2), nullable=True)
    moneda: Mapped[str] = mapped_column(String(3), default="MXN")

    # Insurer-specific extras: coaseguro, copago, prima_individual, periodo_espera
    campos_adicionales: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    poliza: Mapped["Poliza"] = relationship("Poliza", back_populates="coberturas")
```

### Pattern 5: Database Engine Setup (database.py)

**What:** Single module owns the SQLAlchemy engine, session factory, and `Base.metadata.create_all()` for initial schema creation. Phase 1 uses `create_all()` — no Alembic migration needed for a greenfield DB.

```python
# policy_extractor/storage/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pathlib import Path
from .models import Base

def get_engine(db_path: str = "data/polizas.db"):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return engine

def init_db(db_path: str = "data/polizas.db"):
    """Create all tables. Safe to call repeatedly — CREATE TABLE IF NOT EXISTS."""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False)
```

### Anti-Patterns to Avoid

- **Flat insured columns:** Never add `nombre_asegurado_1`, `nombre_asegurado_2` to `polizas`. One-to-many from day one. Recovery from this is a full data migration.
- **`float` for monetary fields:** IEEE 754 errors corrupt financial data silently. Use `Decimal`/`Numeric` end-to-end.
- **`str` for date fields:** Mixed `DD/MM/YYYY` and `YYYY-MM-DD` strings in the same column destroy date range queries. The `Date` column type forces ISO storage.
- **No provenance columns:** Missing `source_file_hash`, `model_id`, `prompt_version` makes targeted re-extraction impossible after bugs or schema changes. These cost 4 columns to add now vs. a full re-extraction of the corpus later.
- **Alembic auto-migrate on import:** Never call `create_all()` or `upgrade head` inside FastAPI startup. Make it an explicit CLI command (`python -m policy_extractor.storage.database`).
- **Putting type-specific asset columns in `asegurados`:** Do not add `vin`, `placas`, `m2` as typed columns to `asegurados`. These go in `campos_adicionales` to avoid 20+ nullable columns for the minority of asset types.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Date format parsing | Custom regex/strptime chains | Pydantic `field_validator` + `datetime.strptime` with known Mexican date formats | Pydantic handles None, type coercion, and validation error context automatically |
| JSON column serialization | Manual `json.dumps()` / `json.loads()` in ORM | SQLAlchemy `JSON` column type | SQLAlchemy handles serialization, type conversion, and None handling; works identically on SQLite (TEXT) and PostgreSQL (JSONB) |
| Schema migrations | Custom SQL ALTER TABLE scripts | `Base.metadata.create_all()` for v1; Alembic for v2 | `create_all()` is idempotent (IF NOT EXISTS); Alembic adds history tracking when schema evolves in later phases |
| Currency parsing | Regex to strip "$", "MXN", European decimal notation | Pydantic `field_validator` on Decimal fields + explicit extraction prompt instructions | The LLM will be instructed to return numeric values; the validator is a safety net, not the primary parser |

**Key insight:** Pydantic v2 validators are the correct place to normalize data from external sources (LLM, PDFs). They run before the value is stored, they generate clear error messages, and they compose cleanly with SQLAlchemy without coupling the two layers.

---

## Common Pitfalls

### Pitfall 1: Single `insured_name` String for Multi-Person Policies

**What goes wrong:** A vida (life insurance) policy covering a family of four gets one concatenated string in `polizas.nombre_asegurado`. Batch extraction either picks the first person or comma-joins all names. Once data is in production, splitting this back into rows requires parsing free text — lossy and error-prone.

**Why it happens:** The schema is designed around the simplest case.

**How to avoid:** The `asegurados` table with FK to `polizas.id` is mandatory. Every individual person or asset is a separate row. Test with a gastos médicos family policy during Phase 1 schema validation (even with mock data).

**Warning signs:** A `nombre_asegurado` column anywhere on `polizas` — that column must not exist.

### Pitfall 2: `float` Silently Corrupts Monetary Values

**What goes wrong:** `float('1500000.00')` → `1499999.9999999998` in Python. Stored, retrieved, formatted — the value looks correct until a SUM or comparison exposes the error.

**Why it happens:** `float` is the default numeric type. JSON deserialization returns `float` by default.

**How to avoid:** Use `Decimal` in Pydantic models and `Numeric(precision=15, scale=2)` in SQLAlchemy. Instruct pydantic: `model_config = ConfigDict(use_enum_values=True)` — and set JSON deserialization to parse decimals: when using `model_validate_json()`, pass `strict=False` which handles Decimal from JSON strings.

**Warning signs:** Any `Float` column on monetary fields in `models.py`.

### Pitfall 3: Date Fields Stored as String Columns

**What goes wrong:** SQLAlchemy `String` column accepts "15/01/2025", "2025-01-15", and "01/15/2025" with equal indifference. The column contains mixed formats. Date range queries (`WHERE fin_vigencia < '2026-01-01'`) fail or return wrong results because string comparison is not date comparison.

**Why it happens:** The developer defers normalization, intending to "fix it later."

**How to avoid:** Use `Date` type in SQLAlchemy. Pydantic `field_validator` normalizes before the value reaches the ORM. The `Date` type enforces ISO 8601 at the SQLite column level.

**Warning signs:** `mapped_column(String)` on any field named `fecha_*` or `vigencia_*`.

### Pitfall 4: Missing Provenance Columns

**What goes wrong:** A bug is found in the extraction prompt 6 months after launch — certain insurer policies have a wrong `prima_total` due to a currency parsing error in the prompt. There is no `model_id` or `prompt_version` column. It is impossible to identify which of the 1,200 records in the DB were extracted with the buggy prompt. All records must be re-extracted at full API cost.

**Why it happens:** Provenance feels like infrastructure detail that can be added later.

**How to avoid:** The 4 provenance columns (`source_file_hash`, `model_id`, `prompt_version`, `extracted_at`) must be in the initial `create_all()`. They have zero cost to add now and HIGH cost to add retroactively.

**Warning signs:** `polizas` table with no `model_id` or `prompt_version` columns.

### Pitfall 5: Alembic Configured but Not Initialized Correctly for SQLite

**What goes wrong:** Alembic's `env.py` default configuration uses `compare_type=False`. New column additions are detected but type changes (e.g., `String` → `Date`) are silently missed. The migration runs without error but the DB still has the old column type.

**Why it happens:** Alembic default SQLite config is minimal.

**How to avoid:** For Phase 1, skip Alembic — use `Base.metadata.create_all()` only. Add Alembic in Phase 5 when schema evolution becomes likely. If Alembic is added early, set `compare_type=True` in `env.py` and `render_as_batch=True` (SQLite requires batch operations for column modification).

**Warning signs:** Running `alembic revision --autogenerate` and seeing an empty migration on a schema that was just changed.

---

## Code Examples

### Full PolicyExtraction Pydantic Model

```python
# policy_extractor/schemas/poliza.py
from pydantic import BaseModel, Field, field_validator, ConfigDict
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from .asegurado import AseguradoExtraction
from .cobertura import CoberturaExtraction

class PolicyExtraction(BaseModel):
    """
    Extraction contract for a single insurance policy.
    Used by: instructor (Phase 3), storage/writer.py (Phase 5).
    Field names intentionally in Spanish — agency team reads JSON output directly.
    """
    model_config = ConfigDict(populate_by_name=True)

    # --- Identity (required) ---
    numero_poliza: str
    aseguradora: str

    # --- Policy metadata ---
    tipo_seguro: Optional[str] = None
    fecha_emision: Optional[date] = None
    inicio_vigencia: Optional[date] = None
    fin_vigencia: Optional[date] = None

    # --- Parties ---
    nombre_contratante: Optional[str] = None
    nombre_agente: Optional[str] = None

    # --- Financial ---
    prima_total: Optional[Decimal] = None
    moneda: str = "MXN"
    forma_pago: Optional[str] = None
    frecuencia_pago: Optional[str] = None

    # --- Related objects (one-to-many) ---
    asegurados: list[AseguradoExtraction] = Field(default_factory=list)
    coberturas: list[CoberturaExtraction] = Field(default_factory=list)

    # --- Provenance (DATA-05) ---
    source_file_hash: Optional[str] = None   # sha256 hex string
    model_id: Optional[str] = None           # e.g., "claude-sonnet-4-6-20250514"
    prompt_version: Optional[str] = None     # e.g., "v1.0.0"
    extracted_at: Optional[datetime] = None  # UTC timestamp

    # --- Overflow (DATA-02) ---
    campos_adicionales: dict = Field(default_factory=dict)

    @field_validator("fecha_emision", "inicio_vigencia", "fin_vigencia", mode="before")
    @classmethod
    def normalize_date(cls, v):
        if v is None or isinstance(v, date):
            return v
        if isinstance(v, str) and v.strip():
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(v.strip(), fmt).date()
                except ValueError:
                    continue
        return None  # Unknown format → null, logged by extraction layer
```

### DB Initialization Script

```python
# Run to initialize database:
# python -m policy_extractor.storage.database

if __name__ == "__main__":
    from policy_extractor.storage.database import init_db
    engine = init_db()
    print(f"Database initialized: {engine.url}")
```

### pyproject.toml Skeleton

```toml
[project]
name = "policy-extractor"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.12.5",
    "sqlalchemy>=2.0.48",
    "python-dotenv>=1.0.1",
]

[project.optional-dependencies]
dev = ["pytest", "ruff"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]  # pycodestyle, pyflakes, isort, pyupgrade
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `class Config:` | Pydantic v2 `model_config = ConfigDict(...)` | Pydantic v2.0 (2023) | `instructor` 1.14.5 requires pydantic v2; do not use v1 patterns |
| SQLAlchemy 1.4 `Column(String)` syntax | SQLAlchemy 2.0 `mapped_column(String)` + `Mapped[str]` | SQLAlchemy 2.0 (2023) | Type-annotated models; better IDE support; same SQL output |
| `@validator` (pydantic v1) | `@field_validator(..., mode="before")` (pydantic v2) | Pydantic v2.0 | `@validator` is removed in v2; use `@field_validator` |
| `orm_mode = True` (pydantic v1) | `model_config = ConfigDict(from_attributes=True)` | Pydantic v2.0 | Needed when converting SQLAlchemy ORM objects to Pydantic models in Phase 5 |

**Deprecated/outdated:**
- `pydantic.validator`: Removed in pydantic v2. Use `field_validator`.
- `pydantic.orm_mode`: Renamed to `from_attributes` in `ConfigDict`.
- SQLAlchemy `Column(JSON)` without `Mapped`: Works but loses type checking; use `mapped_column(JSON)` with `Mapped[Optional[dict]]`.

---

## Open Questions

1. **Alembic vs. manual migrations for v1**
   - What we know: `Base.metadata.create_all()` is sufficient for a greenfield DB with no existing data to migrate.
   - What's unclear: At what point does schema evolution in v2 justify adding Alembic now vs. adding it as a Phase 5 task?
   - Recommendation: Skip Alembic in Phase 1. Add it as the first task of Phase 5 when the schema is confirmed by real extraction data. Document this decision in the plan.

2. **`campos_adicionales` vs. separate asset sub-tables for vehículos/inmuebles**
   - What we know: User locked in JSON overflow on `asegurados` for type-specific fields.
   - What's unclear: If vehículo fields (VIN, placas) become filterable requirements in v2, they will need typed columns added via migration.
   - Recommendation: Accept the locked decision. Document in `models.py` which fields are known asset properties stored in `campos_adicionales` so future migrations are scripted, not guessed.

3. **`source_file_hash` as unique constraint on `polizas`?**
   - What we know: The hash enables idempotency checks (CLI-04: skip already-processed PDFs).
   - What's unclear: Should `source_file_hash` be a UNIQUE constraint, or can the same PDF be intentionally re-extracted with a new prompt (creating a new row)?
   - Recommendation: Do NOT add a UNIQUE constraint in Phase 1. The hash is used for lookup, not enforcement. Idempotency logic lives in the CLI (Phase 4): "if hash in DB and status = success, skip." Multiple rows for the same file (with different `prompt_version`) are valid for re-extraction workflows.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (latest stable) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — Wave 0 task |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-01 | `asegurados` table has FK to `polizas`; multiple rows per policy created correctly | unit | `pytest tests/test_models.py::test_asegurado_one_to_many -x` | Wave 0 |
| DATA-01 | `AseguradoExtraction` accepts `tipo="persona"` and `tipo="bien"` | unit | `pytest tests/test_schemas.py::test_asegurado_tipos -x` | Wave 0 |
| DATA-02 | `campos_adicionales` JSON column round-trips arbitrary dicts | unit | `pytest tests/test_models.py::test_json_overflow_roundtrip -x` | Wave 0 |
| DATA-03 | `normalize_date` converts DD/MM/YYYY and MM/DD/YYYY to `date` | unit | `pytest tests/test_schemas.py::test_date_normalization -x` | Wave 0 |
| DATA-03 | SQLAlchemy `Date` column rejects non-ISO strings at the ORM level | unit | `pytest tests/test_models.py::test_date_column_type -x` | Wave 0 |
| DATA-04 | `prima_total` stored as `Decimal` without float rounding error | unit | `pytest tests/test_schemas.py::test_decimal_precision -x` | Wave 0 |
| DATA-04 | `moneda` defaults to "MXN"; accepts "USD" | unit | `pytest tests/test_schemas.py::test_currency_code -x` | Wave 0 |
| DATA-05 | `polizas` table has `source_file_hash`, `model_id`, `prompt_version`, `extracted_at` columns | unit | `pytest tests/test_models.py::test_provenance_columns -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/__init__.py` — package marker
- [ ] `tests/conftest.py` — in-memory SQLite engine fixture (`engine = create_engine("sqlite:///:memory:")` + `Base.metadata.create_all(engine)`)
- [ ] `tests/test_schemas.py` — covers DATA-01 (Pydantic), DATA-03, DATA-04
- [ ] `tests/test_models.py` — covers DATA-01 (ORM), DATA-02, DATA-03, DATA-04, DATA-05
- [ ] Framework install: `uv pip install --dev pytest` (if not already in pyproject.toml)

---

## Sources

### Primary (HIGH confidence)
- `.planning/research/STACK.md` — All verified library versions, compatibility matrix, Windows installation notes (researched 2026-03-17)
- `.planning/research/ARCHITECTURE.md` — Project structure, build order, ORM + JSON hybrid schema pattern (researched 2026-03-17)
- `.planning/research/PITFALLS.md` — Flat schema (Pitfall 8), date/currency inconsistency (Pitfall 5), no provenance (Pitfall 6) (researched 2026-03-17)
- `.planning/research/SUMMARY.md` — Executive synthesis; confirms Phase 1 as non-retrofittable foundation (researched 2026-03-17)
- [Pydantic v2 field_validator docs](https://docs.pydantic.dev/latest/concepts/validators/) — `mode="before"`, `@classmethod` pattern
- [SQLAlchemy 2.0 mapped_column docs](https://docs.sqlalchemy.org/en/20/orm/mapping_columns.html) — `Mapped`, `mapped_column`, `JSON` type

### Secondary (MEDIUM confidence)
- `.planning/phases/01-foundation/01-CONTEXT.md` — User-locked decisions on asegurados model, coverage structure, core vs overflow fields (gathered 2026-03-18)
- [SQLite JSON1 extension — Charles Leifer](https://charlesleifer.com/blog/using-the-sqlite-json1-and-fts5-extensions-with-python/) — Hybrid column pattern validation

### Tertiary (LOW confidence)
None — all Phase 1 patterns are well-established and covered by primary sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions verified against PyPI March 2026; pydantic v2 + SQLAlchemy 2.0 are stable and extensively documented
- Architecture: HIGH — project-specific pre-research from ARCHITECTURE.md cross-referenced with locked user decisions from CONTEXT.md
- Pitfalls: HIGH — drawn from PITFALLS.md which cites official docs, post-mortems, and multiple sources for each finding

**Research date:** 2026-03-18
**Valid until:** 2026-09-18 (stable libraries; pydantic and SQLAlchemy have long release cycles)
