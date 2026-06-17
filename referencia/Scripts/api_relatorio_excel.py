# report_api.py
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
from uuid import uuid4
import os

# 👇 import your builder + default dirs
from your_report_module import create_excel_report, MARTS_DIR  # <- change module name

app = FastAPI(title="Comex Reports API")

def _safe_unlink(path: Path):
    try:
        path.unlink(missing_ok=True)
    except Exception:
        pass

@app.get("/reports/comex.xlsx")
def export_comex_excel(
    bg: BackgroundTasks,
    include_charts: bool = Query(False, description="Enable charts (if implemented)"),
    marts_dir: str | None = Query(None, description="Override marts directory (optional)"),
    filename: str | None = Query(None, description="Download filename (optional)")
):
    # choose marts dir
    mdir = Path(marts_dir).resolve() if marts_dir else MARTS_DIR

    # unique temp output to avoid collisions
    out_path = Path.cwd() / "reports" / f"comex_{uuid4().hex}.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # build the file
        create_excel_report(marts_dir=mdir, out_path=out_path, include_charts=include_charts)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # clean up if something failed mid-way
        _safe_unlink(out_path)
        raise HTTPException(status_code=400, detail=f"Report failed: {e}")

    # schedule deletion after response is sent
    bg.add_task(_safe_unlink, out_path)

    download_name = filename or out_path.name
    return FileResponse(
        path=out_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=download_name,
    )
