# Phase 1: Foundation and Data Infrastructure - Research

**Researched:** 2026-02-26
**Domain:** SAS I/O, CDISC reference data management, date conversion, XPT output, CLI scaffolding
**Confidence:** HIGH

## Summary

Phase 1 builds the deterministic data plumbing that all downstream agents depend on: reading SAS files, profiling datasets, accessing SDTM-IG and CT reference standards, converting dates to ISO 8601, generating USUBJID, producing valid XPT files, and providing a CLI entry point.

The standard approach is: pyreadstat for all SAS I/O (both reading .sas7bdat and writing .xpt), pandas for DataFrame manipulation, bundled JSON files for SDTM-IG and CT reference data (not API calls at runtime), a deterministic date conversion utility (not LLM), and typer+rich for CLI. The sample data from Fakedata/ has been profiled and reveals important characteristics: EDC metadata columns mixed with clinical data, dates stored as SAS DATETIME numeric values (seconds since 1960-01-01), string dates in "DD Mon YYYY" format, and USUBJID components spread across StudyEnvSiteNumber and Subject columns.

**Primary recommendation:** Build this phase as pure Python utilities with zero LLM dependency. Every function should be deterministic and unit-testable. The CLI is a thin shell that calls these utilities.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyreadstat | >=1.3.3 | Read .sas7bdat, write .xpt v5 | C-based (fast), preserves SAS metadata (labels, formats, types), writes XPT v5/v8 with column labels. Maintained by Roche. |
| pandas | >=2.2 | DataFrame operations | pyreadstat returns pandas DataFrames natively. All profiling and transformation happens on DataFrames. |
| pydantic | >=2.10 | Data models for all reference data and profiling output | Validation, serialization, type safety. Used by LangGraph internally. |
| typer | >=0.15 | CLI framework | Type-hint-based CLI with auto-completion. Uses Rich internally. |
| rich | >=13.9 | Terminal tables, progress bars, panels | Display profiling output, progress through pipeline stages. |
| loguru | >=0.7 | Structured logging | Debug data pipeline operations. |
| python-dotenv | >=1.0 | Environment variable management | Config and API keys. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| openpyxl | >=3.1 | Read NCI CT Excel files | Parse CDISC CT from Excel format during build/bundling step |
| pytest | >=8.0 | Testing | Unit tests for all utilities |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pyreadstat for XPT write | xport library | xport has less metadata support; pyreadstat is one lib for read+write |
| Bundled JSON for CT | CDISC Library API at runtime | Adds network dependency, rate limits, requires API key; bundled is faster and offline |
| typer | click | More boilerplate; typer wraps click with type hints |
| openpyxl for CT parsing | pandas read_excel | Either works; openpyxl gives more control over sheet structure |

**Installation:**
```bash
pip install pyreadstat>=1.3.3 pandas>=2.2 pydantic>=2.10 typer>=0.15 rich>=13.9 loguru>=0.7 python-dotenv>=1.0 openpyxl>=3.1 pytest>=8.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/
  astraea/
    __init__.py
    cli/
      __init__.py
      app.py              # Typer app, top-level commands
      display.py           # Rich formatting helpers
    io/
      __init__.py
      sas_reader.py        # Read .sas7bdat, extract metadata
      xpt_writer.py        # Write .xpt v5 with pre-validation
    profiling/
      __init__.py
      profiler.py          # Dataset profiling logic
    reference/
      __init__.py
      sdtm_ig.py           # SDTM-IG domain/variable lookup
      controlled_terms.py  # CT codelist lookup
      loader.py            # Load bundled JSON at startup
    transforms/
      __init__.py
      dates.py             # ISO 8601 date conversion
      usubjid.py           # USUBJID generation + validation
    models/
      __init__.py
      metadata.py          # Pydantic models for SAS metadata
      profiling.py         # Pydantic models for profiling results
      sdtm.py              # Pydantic models for SDTM-IG reference
      controlled_terms.py  # Pydantic models for CT
    data/
      sdtm_ig/             # Bundled SDTM-IG JSON files
        domains.json       # All domain definitions
        variables.json     # Variable specs per domain
        classes.json       # Domain class assignments
      ct/                  # Bundled CT JSON files
        codelists.json     # All codelists with terms
        codelist_mappings.json  # Variable-to-codelist mappings
tests/
  test_io/
  test_profiling/
  test_reference/
  test_transforms/
```

### Pattern 1: Metadata-First SAS Reading
**What:** Read SAS files returning both DataFrame AND rich metadata object. Never discard metadata.
**When to use:** Every SAS file read operation.
**Example:**
```python
# Source: pyreadstat documentation + verified with sample data
import pyreadstat
from pydantic import BaseModel

class VariableMetadata(BaseModel):
    name: str
    label: str
    sas_format: str | None  # e.g., "DATETIME", "$", None (numeric)
    dtype: str              # "numeric" or "character"
    storage_width: int | None

class DatasetMetadata(BaseModel):
    filename: str
    row_count: int
    col_count: int
    variables: list[VariableMetadata]
    file_encoding: str | None

def read_sas_with_metadata(filepath: str) -> tuple[pd.DataFrame, DatasetMetadata]:
    """Read SAS file preserving all metadata."""
    df, meta = pyreadstat.read_sas7bdat(
        filepath,
        disable_datetime_conversion=True  # Keep raw numeric dates for our converter
    )
    variables = []
    for col in meta.column_names:
        sas_format = meta.original_variable_types.get(col)
        variables.append(VariableMetadata(
            name=col,
            label=meta.column_names_to_labels.get(col, ""),
            sas_format=sas_format,
            dtype="character" if sas_format == "$" else "numeric",
            storage_width=None,  # pyreadstat doesn't expose this directly
        ))
    dataset_meta = DatasetMetadata(
        filename=os.path.basename(filepath),
        row_count=meta.number_rows,
        col_count=meta.number_columns,
        variables=variables,
        file_encoding=meta.file_encoding,
    )
    return df, dataset_meta
```

### Pattern 2: Pre-Write XPT Validation
**What:** Validate all XPT v5 constraints BEFORE writing. pyreadstat silently truncates.
**When to use:** Every XPT write operation.
**Example:**
```python
# CRITICAL: pyreadstat silently truncates variable names to 8 chars
# and labels to 40 chars in XPT v5 without raising errors.
# Verified by testing: "LONGNAME9" becomes "LONGNAME", labels get cut at 40.

class XPTValidationError(Exception):
    pass

def validate_for_xpt_v5(df: pd.DataFrame, column_labels: dict[str, str], table_name: str) -> list[str]:
    """Validate DataFrame against XPT v5 constraints. Returns list of violations."""
    errors = []

    # Dataset name: <= 8 chars, alphanumeric, starts with letter
    if len(table_name) > 8:
        errors.append(f"Dataset name '{table_name}' exceeds 8 characters")
    if not table_name[0].isalpha():
        errors.append(f"Dataset name '{table_name}' must start with a letter")

    for col in df.columns:
        # Variable names: <= 8 chars
        if len(col) > 8:
            errors.append(f"Variable name '{col}' exceeds 8 characters")
        # Variable names: alphanumeric + underscore only
        if not all(c.isalnum() or c == '_' for c in col):
            errors.append(f"Variable name '{col}' contains invalid characters")
        # Labels: <= 40 chars
        label = column_labels.get(col, "")
        if len(label) > 40:
            errors.append(f"Label for '{col}' exceeds 40 characters: '{label[:45]}...'")

    # Character variable values: <= 200 bytes
    for col in df.select_dtypes(include='object').columns:
        max_len = df[col].dropna().str.len().max()
        if max_len and max_len > 200:
            errors.append(f"Variable '{col}' has values exceeding 200 characters")

    # ASCII only
    for col in df.select_dtypes(include='object').columns:
        non_ascii = df[col].dropna().str.contains(r'[^\x00-\x7F]', regex=True)
        if non_ascii.any():
            errors.append(f"Variable '{col}' contains non-ASCII characters")

    return errors
```

### Pattern 3: Bundled Reference Data as JSON
**What:** Ship SDTM-IG and CT as pre-processed JSON files. Load at startup into lookup dictionaries.
**When to use:** All SDTM-IG and CT access.
**Example:**
```python
# Reference data loaded once, queried via tool-style functions
class SDTMReference:
    """Lookup interface for SDTM-IG domain and variable specifications."""

    def __init__(self, ig_path: str, ct_path: str):
        self.domains = json.load(open(f"{ig_path}/domains.json"))
        self.codelists = json.load(open(f"{ct_path}/codelists.json"))

    def get_domain_spec(self, domain: str) -> dict:
        """Get all variables for a domain with core/required designation."""
        return self.domains.get(domain)

    def get_required_variables(self, domain: str) -> list[str]:
        """Get only Required variables for a domain."""
        spec = self.domains.get(domain, {})
        return [v["name"] for v in spec.get("variables", []) if v["core"] == "Req"]

    def lookup_codelist(self, codelist_code: str) -> dict:
        """Get a codelist by NCI code (e.g., 'C66731' for SEX)."""
        return self.codelists.get(codelist_code)

    def is_extensible(self, codelist_code: str) -> bool:
        """Check if a codelist allows sponsor-defined terms."""
        cl = self.codelists.get(codelist_code, {})
        return cl.get("extensible", False)

    def validate_term(self, codelist_code: str, value: str) -> bool:
        """Check if a value is a valid submission value in a codelist."""
        cl = self.codelists.get(codelist_code, {})
        return value in cl.get("terms", {})
```

### Pattern 4: Deterministic Date Conversion
**What:** Convert SAS dates and string dates to ISO 8601, handling partial dates per SDTM rules.
**When to use:** Every date/time variable conversion.
**Example:**
```python
from datetime import datetime, date, timedelta

SAS_EPOCH = date(1960, 1, 1)

def sas_date_to_iso(sas_numeric: float) -> str:
    """Convert SAS date numeric (days since 1960-01-01) to ISO 8601."""
    if pd.isna(sas_numeric):
        return ""
    d = SAS_EPOCH + timedelta(days=int(sas_numeric))
    return d.strftime("%Y-%m-%d")

def sas_datetime_to_iso(sas_numeric: float) -> str:
    """Convert SAS datetime numeric (seconds since 1960-01-01 00:00:00) to ISO 8601."""
    if pd.isna(sas_numeric):
        return ""
    dt = datetime(1960, 1, 1) + timedelta(seconds=sas_numeric)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")

def parse_string_date_to_iso(date_str: str) -> str:
    """Parse various string date formats to ISO 8601.

    Handles: 'DD Mon YYYY', 'DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD',
             partial dates like 'Mon YYYY', 'YYYY'
    """
    # Implementation handles each format with regex detection
    pass

def format_partial_iso8601(year: int | None, month: int | None, day: int | None,
                           hour: int | None = None, minute: int | None = None,
                           second: int | None = None) -> str:
    """Format partial date/time per SDTM-IG rules.

    SDTM rules: truncate from the right at the first missing component.
    - Year only: "2023"
    - Year-month: "2023-03"
    - Full date: "2023-03-15"
    - Date with time: "2023-03-15T10:30:00"

    NOT valid: "2023---15" (cannot have gaps)
    """
    if year is None:
        return ""
    result = f"{year:04d}"
    if month is None:
        return result
    result += f"-{month:02d}"
    if day is None:
        return result
    result += f"-{day:02d}"
    if hour is None:
        return result
    result += f"T{hour:02d}"
    if minute is None:
        return result
    result += f":{minute:02d}"
    if second is None:
        return result
    result += f":{second:02d}"
    return result
```

### Anti-Patterns to Avoid
- **Using LLM for date conversion:** Dates are deterministic. LLM adds non-determinism and cost to what is a pure parsing problem.
- **Fetching CDISC reference data at runtime via API:** Adds network dependency, latency, rate limits. Bundle it.
- **Ignoring pyreadstat's silent truncation:** pyreadstat does NOT raise errors when variable names exceed 8 chars in XPT v5. It silently truncates. You MUST validate before writing.
- **Using `disable_datetime_conversion=False` (default):** pyreadstat auto-converts SAS dates to Python datetime objects, losing the original format information. Use `disable_datetime_conversion=True` and convert manually for full control.
- **Discarding EDC metadata columns:** The sample data has ~30 EDC system columns (projectid, instanceId, folderid, etc.) mixed with clinical data. These must be identified and separated, not blindly processed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SAS file reading | Custom binary parser | pyreadstat.read_sas7bdat | SAS binary format is complex; C-based reader is 10x faster and handles encoding |
| XPT file writing | Custom XPT format writer | pyreadstat.write_xport(file_format_version=5) | XPT v5 binary format has specific header/record layout requirements |
| CLI argument parsing | argparse manual setup | typer with type hints | Auto-generates help, completion, validation |
| Terminal tables/progress | print() formatting | rich.table.Table / rich.progress | Handles terminal width, colors, alignment |
| Data validation models | Dict-based schemas | Pydantic BaseModel | Type coercion, validation, serialization built-in |
| CDISC CT Excel parsing | Manual CSV/text parsing | openpyxl (read NCI Excel) -> JSON bundling | Excel is the authoritative format from NCI EVS |

**Key insight:** Phase 1 has zero LLM components. Everything is deterministic I/O and data manipulation. The temptation to "just use Claude for date parsing" or "let the LLM figure out the CT mapping" should be resisted. Deterministic code is testable, reproducible, and fast.

## Common Pitfalls

### Pitfall 1: pyreadstat Silent Truncation in XPT v5
**What goes wrong:** Variable names longer than 8 characters and labels longer than 40 characters are silently truncated when writing XPT v5 files. No error is raised. "LONGNAME9" becomes "LONGNAME" and you only discover it when downstream tools read the file.
**Why it happens:** pyreadstat delegates to the C library ReadStat which follows SAS transport format behavior of truncating without error.
**How to avoid:** Build a pre-write validation function that checks all constraints before calling write_xport(). Raise an error if any constraint is violated.
**Warning signs:** Column names differ between the DataFrame and the read-back XPT file.

### Pitfall 2: SAS DATETIME vs DATE Numeric Values
**What goes wrong:** SAS stores dates as days since 1960-01-01 but datetimes as seconds since 1960-01-01 00:00:00. Using the wrong conversion produces dates that are off by decades.
**Why it happens:** pyreadstat's `original_variable_types` metadata distinguishes DATE from DATETIME formats, but if you ignore this distinction and treat all numeric date columns the same way, you get wrong results. The sample data has format="DATETIME" for all date columns (values like 1964217600.0 = seconds, not days).
**How to avoid:** Always check `original_variable_types` to determine whether a column is DATE (days) or DATETIME (seconds). Apply the correct conversion function.
**Warning signs:** Converted dates in the year 5000+ (applied days-since-epoch to a seconds value) or in 1960 (applied seconds-since-epoch to a days value).

### Pitfall 3: EDC System Columns in Raw Data
**What goes wrong:** Raw SAS exports from EDC systems (Rave, InForm, etc.) contain 20-30 system/metadata columns alongside clinical data: projectid, studyid, environmentName, instanceId, DataPageId, RecordDate, MinCreated, MaxUpdated, etc. Treating these as clinical variables to profile and map wastes time and confuses downstream agents.
**Why it happens:** EDC exports dump everything. The DM dataset in our sample has 61 columns, of which roughly 30 are EDC system columns.
**How to avoid:** Build an EDC column detection heuristic (known EDC column names, metadata-like patterns) and tag columns as "EDC system" vs "clinical data" during profiling. Present both in profiling output but flag the distinction.
**Warning signs:** Profiling output showing variables like "DataPageId" and "RecordPosition" as clinical data.

### Pitfall 4: Character Encoding in SAS Files
**What goes wrong:** SAS files may use WINDOWS-1252 encoding (as our sample data does), which contains characters not valid in XPT v5 (ASCII only). Special characters in site names, investigator names, or free-text fields will cause XPT validation failures.
**Why it happens:** Clinical sites worldwide enter data in local character sets. EDC systems store in Windows encoding.
**How to avoid:** Detect encoding from pyreadstat metadata (meta.file_encoding), normalize to ASCII for XPT output, and flag/replace non-ASCII characters during profiling.
**Warning signs:** pyreadstat metadata showing file_encoding="WINDOWS-1252" or similar non-ASCII encoding.

### Pitfall 5: Partial Date Handling Per SDTM Rules
**What goes wrong:** Partial dates like "Mar 2022" (no day) or "2022" (no month/day) exist in clinical data. Converting them to full ISO 8601 dates by imputing missing components (e.g., defaulting to day 01) violates SDTM rules -- SDTM requires truncation from the right: "2022-03" not "2022-03-01".
**Why it happens:** Natural instinct is to fill in missing date parts. SDTM explicitly forbids this for --DTC variables (imputation belongs in ADaM, not SDTM).
**How to avoid:** Build the date converter to detect partial dates and produce truncated ISO 8601 strings. Unit test with all partial date combinations.
**Warning signs:** All dates having full YYYY-MM-DD format including ones that were originally partial.

### Pitfall 6: CDISC Version Coupling
**What goes wrong:** Using SDTM-IG v3.4 domain specs with the wrong CT version. FDA requires specific version alignment.
**Why it happens:** CT is updated quarterly (latest: 2025-09-26). IG versions change less frequently.
**How to avoid:** Create a version manifest config that locks SDTM-IG version + CT version together. Validate at startup.
**Warning signs:** Validation errors about terms not found in codelists when the term exists in a different CT version.

## Code Examples

### Reading All SAS Files From a Directory
```python
# Source: verified against Fakedata/ sample data
import pyreadstat
from pathlib import Path

def read_all_sas_files(data_dir: str) -> dict[str, tuple[pd.DataFrame, DatasetMetadata]]:
    """Read all .sas7bdat files from a directory."""
    results = {}
    data_path = Path(data_dir)

    for sas_file in sorted(data_path.glob("*.sas7bdat")):
        df, meta = pyreadstat.read_sas7bdat(
            str(sas_file),
            disable_datetime_conversion=True,
        )
        dataset_meta = extract_metadata(meta, sas_file.name)
        results[sas_file.stem] = (df, dataset_meta)

    return results
```

### Dataset Profiling
```python
# Source: designed for Fakedata/ structure
from pydantic import BaseModel

class ValueDistribution(BaseModel):
    value: str
    count: int
    percentage: float

class VariableProfile(BaseModel):
    name: str
    label: str
    dtype: str                          # "numeric" or "character"
    sas_format: str | None
    n_total: int
    n_missing: int
    n_unique: int
    missing_pct: float
    sample_values: list[str]            # First 10 unique non-null values
    top_values: list[ValueDistribution] # Top 5 most common values
    is_date: bool                       # True if SAS date/datetime format
    detected_date_format: str | None    # e.g., "DD Mon YYYY", "SAS_DATETIME"

class DatasetProfile(BaseModel):
    filename: str
    row_count: int
    col_count: int
    variables: list[VariableProfile]
    date_variables: list[str]           # Names of detected date columns
    edc_columns: list[str]              # Detected EDC system columns

def profile_dataset(df: pd.DataFrame, meta: DatasetMetadata) -> DatasetProfile:
    """Profile a raw dataset for downstream mapping agents."""
    variables = []
    date_vars = []
    edc_cols = []

    EDC_COLUMN_PATTERNS = {
        'projectid', 'project', 'studyid', 'environmentname',
        'subjectid', 'studysiteid', 'siteid', 'instanceid',
        'instancename', 'instancerepeatnumber', 'folderid',
        'folder', 'foldername', 'folderseq', 'targetdays',
        'datapageid', 'datapagename', 'pagerepeatnumber',
        'recorddate', 'recordid', 'recordposition',
        'mincreated', 'maxupdated', 'savets', 'studyenvsitenumber',
    }

    for var_meta in meta.variables:
        col = var_meta.name
        series = df[col]

        # Detect EDC columns
        if col.lower() in EDC_COLUMN_PATTERNS:
            edc_cols.append(col)

        # Detect dates
        is_date = var_meta.sas_format in ('DATETIME', 'DATE', 'TIME', 'DDMMYY',
                                           'MMDDYY', 'YYMMDD', 'DTDATE')
        if is_date:
            date_vars.append(col)

        # Detect string date formats from _RAW columns
        detected_format = None
        if var_meta.dtype == "character" and "_RAW" in col and "DAT" in col.upper():
            sample = series.dropna().head(10).tolist()
            detected_format = detect_date_format(sample)

        # Build profile
        non_null = series.dropna()
        n_unique = non_null.nunique()

        top_values = []
        if n_unique <= 100:  # Only for categorical-ish variables
            vc = non_null.value_counts().head(5)
            total = len(non_null)
            for val, count in vc.items():
                top_values.append(ValueDistribution(
                    value=str(val), count=count,
                    percentage=round(count / total * 100, 1)
                ))

        variables.append(VariableProfile(
            name=col,
            label=var_meta.label,
            dtype=var_meta.dtype,
            sas_format=var_meta.sas_format,
            n_total=len(series),
            n_missing=series.isna().sum(),
            n_unique=n_unique,
            missing_pct=round(series.isna().mean() * 100, 1),
            sample_values=[str(v) for v in non_null.unique()[:10]],
            top_values=top_values,
            is_date=is_date,
            detected_date_format=detected_format,
        ))

    return DatasetProfile(
        filename=meta.filename,
        row_count=meta.row_count,
        col_count=meta.col_count,
        variables=variables,
        date_variables=date_vars,
        edc_columns=edc_cols,
    )
```

### Writing Validated XPT v5
```python
# Source: pyreadstat docs + verified silent truncation behavior
import pyreadstat

def write_xpt_v5(df: pd.DataFrame, path: str, table_name: str,
                  column_labels: dict[str, str]) -> None:
    """Write a validated XPT v5 file. Raises on constraint violations."""
    # Step 1: Validate
    errors = validate_for_xpt_v5(df, column_labels, table_name)
    if errors:
        raise XPTValidationError(
            f"XPT v5 validation failed with {len(errors)} errors:\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    # Step 2: Ensure uppercase column names (SDTM convention)
    df_out = df.copy()
    df_out.columns = [c.upper() for c in df_out.columns]
    labels_upper = {k.upper(): v for k, v in column_labels.items()}

    # Step 3: Write
    pyreadstat.write_xport(
        df_out,
        path,
        table_name=table_name.upper(),
        column_labels=labels_upper,
        file_format_version=5,
    )

    # Step 4: Read-back verification
    df_check, meta_check = pyreadstat.read_xport(path)
    assert list(df_check.columns) == list(df_out.columns), \
        "Column names changed during write (truncation occurred)"
    assert len(df_check) == len(df_out), \
        f"Row count mismatch: wrote {len(df_out)}, read back {len(df_check)}"
```

### USUBJID Generation and Validation
```python
# Source: SDTM-IG v3.4 specification + sample data analysis
# Sample data shows: StudyEnvSiteNumber="301-04401", Subject="01"
# USUBJID format: STUDYID-SITEID-SUBJID (delimiter is study-specific)

def generate_usubjid(studyid: str, siteid: str, subjid: str,
                     delimiter: str = "-") -> str:
    """Generate USUBJID from components.

    Per SDTM-IG: USUBJID must uniquely identify a subject across all studies
    for the sponsor. Standard format: STUDYID + SITEID + SUBJID.
    """
    return f"{studyid}{delimiter}{siteid}{delimiter}{subjid}"

def validate_usubjid_consistency(datasets: dict[str, pd.DataFrame],
                                  usubjid_col: str = "USUBJID") -> list[str]:
    """Validate USUBJID consistency across all domains.

    Rules:
    1. Every USUBJID in any domain must exist in DM
    2. USUBJID format must be consistent (same delimiter, same component count)
    3. No duplicate USUBJIDs within DM
    """
    errors = []

    if "dm" not in datasets and "DM" not in datasets:
        errors.append("DM dataset not found - cannot validate USUBJID consistency")
        return errors

    dm_key = "dm" if "dm" in datasets else "DM"
    dm_usubjids = set(datasets[dm_key][usubjid_col].dropna())

    for name, df in datasets.items():
        if usubjid_col in df.columns:
            domain_ids = set(df[usubjid_col].dropna())
            orphans = domain_ids - dm_usubjids
            if orphans:
                errors.append(
                    f"Dataset '{name}' has {len(orphans)} USUBJIDs not in DM: "
                    f"{list(orphans)[:5]}"
                )

    return errors
```

### CLI Entry Point with Rich Progress
```python
# Source: typer + rich documentation
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(name="astraea", help="SDTM mapping pipeline")
console = Console()

@app.command()
def profile(
    data_dir: str = typer.Argument(..., help="Path to folder containing SAS files"),
    output: str = typer.Option(None, "--output", "-o", help="Output JSON path"),
):
    """Profile raw SAS datasets and display metadata summary."""
    from pathlib import Path

    sas_files = list(Path(data_dir).glob("*.sas7bdat"))
    if not sas_files:
        console.print(f"[red]No .sas7bdat files found in {data_dir}[/red]")
        raise typer.Exit(1)

    console.print(f"Found [bold]{len(sas_files)}[/bold] SAS files in {data_dir}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Profiling datasets...", total=len(sas_files))

        for sas_file in sas_files:
            progress.update(task, description=f"Reading {sas_file.name}...")
            # ... profile logic ...
            progress.advance(task)

    # Display summary table
    table = Table(title="Dataset Summary")
    table.add_column("Dataset", style="cyan")
    table.add_column("Rows", justify="right")
    table.add_column("Columns", justify="right")
    table.add_column("Date Cols", justify="right")
    table.add_column("Missing %", justify="right")
    # ... add rows ...
    console.print(table)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pandas.read_sas() | pyreadstat.read_sas7bdat() | ~2020 | Full metadata extraction (labels, formats, encoding) |
| xport library for XPT write | pyreadstat.write_xport() | pyreadstat 1.2+ | Single library for read + write, better label support |
| CDISC Library API for runtime lookup | Bundled JSON from NCI EVS exports | Architecture decision | Offline, fast, no API key needed |
| Click for CLI | Typer (wraps Click) | ~2022 | Type hints, less boilerplate, Rich integration |
| SAS date imputation | Truncated ISO 8601 per SDTM-IG | SDTM-IG standard | No imputation in SDTM; partial dates stay partial |

**Deprecated/outdated:**
- `sas7bdat` Python package: Effectively deprecated. Slow, poor date handling.
- `pandas.read_sas()`: Works but cannot extract SAS metadata (labels, formats). Use pyreadstat.
- Manual XPT binary construction: Never do this. Use pyreadstat.

## Key Findings from Sample Data Analysis

Analysis of the 36 SAS files in Fakedata/ reveals:

1. **EDC System Columns:** Every dataset has ~20-30 EDC metadata columns (projectid, studyid, environmentName, instanceId, DataPageId, etc.) that must be filtered from clinical data during profiling.

2. **Date Storage:** Dates are stored as SAS DATETIME format (seconds since 1960-01-01), not DATE format (days). The value 1964217600.0 = "30 Mar 2022". Raw string versions exist in *_RAW columns using "DD Mon YYYY" format.

3. **Variable Naming:** Raw variable names are long and descriptive (e.g., "RACEAME_RAW", "StudyEnvSiteNumber") -- well beyond the 8-char XPT v5 limit. These are source names, not SDTM target names, but profiling must track them.

4. **USUBJID Components:** StudyEnvSiteNumber follows "301-XXXXX" pattern (e.g., "301-04401"), Subject is just a short number (e.g., "01", "02"). The study appears to use convention: STUDYID + "-" + SITENUMBER + SUBJID from StudyEnvSiteNumber.

5. **Encoding:** Files use WINDOWS-1252 encoding. Non-ASCII characters possible in site names.

6. **Scale:** 36 datasets, most small (3-14 rows in fake data), but real data will be larger. DM has 3 subjects, AE has 14 records, EX has 12.

## Reference Data Bundling Strategy

### SDTM-IG v3.4 Domain Specifications

**Source:** The SDTM-IG v3.4 PDF contains domain specification tables. These need to be converted to structured JSON.

**Approach:** Manually create JSON files from the SDTM-IG v3.4 specification tables. Each domain gets entries for all variables with:
- Variable name (e.g., "STUDYID")
- Variable label (e.g., "Study Identifier")
- Type (Char/Num)
- Core designation (Req/Exp/Perm)
- CDISC Notes
- Associated codelist (if any)
- Domain class (Interventions/Events/Findings/Special Purpose)

**Estimated effort:** ~35 domains, ~20-50 variables each. This is a one-time manual task that can be supplemented by CDISC Library API extraction.

**Alternative:** Use `cdisc-library-client` Python package to pull specifications from CDISC Library API once and cache as JSON. Requires CDISC membership or open-source developer access.

### NCI Controlled Terminology

**Source:** NCI EVS publishes CT in Excel format at `evs.nci.nih.gov/ftp1/CDISC/SDTM/`.

**Structure (from NCI documentation):**
- Excel columns: Code, Codelist Code, Codelist Extensible (Yes/No), Codelist Name, CDISC Submission Value, CDISC Synonym(s), CDISC Definition, NCI Preferred Term
- Organized as "terms by codelist"
- Latest SDTM CT version: 2025-09-26

**Bundling approach:**
1. Download Excel from NCI EVS
2. Parse with openpyxl into structured JSON
3. Index by codelist code (e.g., C66731 for SEX)
4. Store extensible/non-extensible flag per codelist
5. Store variable-to-codelist mappings (which SDTM variable uses which codelist)
6. Bundle JSON files with the package

**JSON schema for bundled CT:**
```json
{
  "version": "2025-09-26",
  "ig_version": "3.4",
  "codelists": {
    "C66731": {
      "name": "Sex",
      "extensible": false,
      "variable_mappings": ["SEX"],
      "terms": {
        "F": {"synonym": "Female", "definition": "..."},
        "M": {"synonym": "Male", "definition": "..."},
        "U": {"synonym": "Unknown", "definition": "..."},
        "UNDIFFERENTIATED": {"synonym": "Undifferentiated", "definition": "..."}
      }
    }
  }
}
```

## Open Questions

1. **CDISC Library API access for IG extraction:**
   - What we know: CDISC Library provides JSON API for domain specs. Requires membership or open-source developer access.
   - What's unclear: Whether the project has CDISC Library API access.
   - Recommendation: Start with manual JSON creation for the ~10 most common domains (DM, AE, CM, EX, LB, VS, EG, MH, DS, IE). Add others incrementally. Use CDISC Library API if access is available.

2. **CT version selection strategy:**
   - What we know: CT is published quarterly. FDA requires specific version alignment with SDTM-IG.
   - What's unclear: Which CT version should be the default for this tool.
   - Recommendation: Bundle CT 2025-09-26 (latest) aligned with SDTM-IG v3.4. Support version override via config.

3. **Ambiguous date format detection:**
   - What we know: The sample data uses "DD Mon YYYY" format (unambiguous). But other studies may use "MM/DD/YYYY" or "DD/MM/YYYY" (ambiguous).
   - What's unclear: How to handle truly ambiguous dates (e.g., "03/04/2023" - March 4 or April 3?).
   - Recommendation: Detect format from column-level patterns (if most dates have day>12, it resolves ambiguity). Flag truly ambiguous cases for human review.

4. **EDC column detection scope:**
   - What we know: The sample data comes from what appears to be Medidata Rave (based on column naming patterns).
   - What's unclear: How EDC metadata columns differ across EDC systems (Rave vs InForm vs Veeva).
   - Recommendation: Start with the known Rave pattern from sample data. Make EDC detection configurable (user can specify columns to exclude or include).

## Sources

### Primary (HIGH confidence)
- [pyreadstat GitHub (Roche)](https://github.com/Roche/pyreadstat) - read_sas7bdat, write_xport API, metadata attributes
- [pyreadstat documentation](https://ofajardo.github.io/pyreadstat_documentation/_build/html/index.html) - function signatures, parameters
- [SAS Transport v5 Format (Library of Congress)](https://www.loc.gov/preservation/digital/formats/fdd/fdd000466.shtml) - XPT v5 constraints (8-char names, 40-char labels, 200-char values, ASCII only)
- [CDISC SDTM-IG v3.4](https://www.cdisc.org/standards/foundational/sdtmig/sdtmig-v3-4) - domain specs, variable definitions
- [NCI EVS CDISC SDTM CT](https://www.cancer.gov/about-nci/organization/cbiit/vocabulary/cdisc) - CT download formats and structure
- Fakedata/ directory - verified against actual sample data (36 SAS files from Phase 3 HAE trial)
- pyreadstat write_xport silent truncation behavior - verified by direct testing

### Secondary (MEDIUM confidence)
- [Typer Progress Bar docs](https://typer.tiangolo.com/tutorial/progressbar/) - CLI progress display patterns
- [Rich Progress Display](https://rich.readthedocs.io/en/stable/progress.html) - terminal output formatting
- [ISO 8601 Date Conversion for SDTM (sdtm.oak R package)](https://cran.r-project.org/web/packages/sdtm.oak/vignettes/iso_8601.html) - partial date handling rules
- [Date Conversions in SDTM (PharmaSUG)](https://www.lexjansen.com/nesug/nesug10/ph/ph11.pdf) - SAS epoch details

### Tertiary (LOW confidence)
- NCI EVS CT Excel column structure - inferred from documentation, not directly parsed

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all libraries verified, versions confirmed, APIs tested against sample data
- Architecture: HIGH - project structure follows standard Python package patterns; data flow verified
- Pitfalls: HIGH - XPT truncation verified by direct testing; date format issues confirmed in sample data
- Reference data bundling: MEDIUM - CT Excel structure inferred from docs, not yet parsed; SDTM-IG JSON schema needs manual creation

**Research date:** 2026-02-26
**Valid until:** 2026-03-26 (stable domain, libraries unlikely to change significantly)
