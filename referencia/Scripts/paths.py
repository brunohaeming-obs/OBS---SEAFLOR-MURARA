# paths.py (or at the top of your module)
from pathlib import Path
import os

def find_project_root(start: Path | None = None) -> Path:
    """
    Walk up from this file (or CWD) until we find a repo marker.
    Works even if launched from another folder.
    """
    p = (start or Path(__file__)).resolve()
    if p.is_file():
        p = p.parent
    for anc in [p, *p.parents]:
        if (anc / "pyproject.toml").exists() or (anc / ".git").exists() \
           or anc.name.lower() in {"dados-comex", "dados_comex"}:
            return anc
    return Path.cwd().resolve()  # last resort

# Allow overriding base via env if you want
ROOT = Path(os.getenv("COMEX_ROOT_DIR", find_project_root()))
DADOS = Path(os.getenv("COMEX_DADOS_DIR", ROOT / "Dados"))

GOLD_DIR  = DADOS / "gold" / "expimp"     # partitioned gold (kind=..., year=...)
MARTS_DIR = DADOS / "marts"
MARTS_DIR.mkdir(parents=True, exist_ok=True)

def gold_glob_for(kind: str) -> str:
    """Partitioned layout: Dados/gold/expimp/kind=EXP/year=*/*.parquet"""
    pat = GOLD_DIR / f"kind={kind}" / "year=*" / "*.parquet"
    return pat.as_posix()   # DuckDB is happy with forward slashes on Windows

def gold_single_path() -> str:
    """Single consolidated file fallback: Dados/gold/comexstat_ncm_sc.parquet"""
    p = DADOS / "gold" / "comexstat_ncm_sc.parquet"
    return p.as_posix()