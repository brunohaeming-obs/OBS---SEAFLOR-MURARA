from __future__ import annotations

import argparse
import csv
import hashlib
import io
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

import requests

try:
    from .paths import DADOS
except ImportError:
    from paths import DADOS

BASE_URL = "https://balanca.economia.gov.br/balanca/bd/comexstat-bd/ncm"
KINDS = ("EXP", "IMP")
DEFAULT_START_YEAR = 1997
DEFAULT_TIMEOUT = 90
DEFAULT_CHUNK_SIZE = 1 << 15

BRONZE_DIR = DADOS / "bronze"
MANIFESTS_DIR = DADOS / "manifests"
STATE_PATH = MANIFESTS_DIR / "bronze_state.csv"
MANIFEST_PATH = MANIFESTS_DIR / "bronze_manifest.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://balanca.economia.gov.br/",
}

STATE_FIELDS = [
    "kind",
    "year",
    "etag",
    "last_modified",
    "content_length",
    "sha256",
    "path",
    "ts_updated",
]

MANIFEST_FIELDS = [
    "ts",
    "stage",
    "action",
    "kind",
    "year",
    "url",
    "path",
    "sha256",
    "size_bytes",
    "n_cols",
    "header_sample",
    "n_rows_sampled",
]

CHANGED_ACTIONS = {"downloaded_new", "replaced_changed"}


def ensure_directories() -> None:
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)


def url_for(kind: str, year: int) -> str:
    return f"{BASE_URL}/{kind}_{year}.csv"


def bronze_path(kind: str, year: int) -> Path:
    return BRONZE_DIR / kind / f"{kind}_{year}.csv"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_state_map(path: Path = STATE_PATH) -> Dict[tuple[str, int], dict[str, str]]:
    if not path.exists():
        return {}

    rows: Dict[tuple[str, int], dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows[(row["kind"], int(row["year"]))] = row
    return rows


def write_state_map(state_map: Dict[tuple[str, int], dict[str, str]], path: Path = STATE_PATH) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATE_FIELDS)
        writer.writeheader()
        for _, row in sorted(state_map.items()):
            writer.writerow(row)


def append_manifest_row(row: dict[str, object], path: Path = MANIFEST_PATH) -> None:
    write_header = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def manifest_stub(
    *,
    timestamp: str,
    action: str,
    kind: str,
    year: int,
    url: str,
    path: str = "",
    sha256: str = "",
) -> dict[str, object]:
    return {
        "ts": timestamp,
        "stage": "bronze",
        "action": action,
        "kind": kind,
        "year": year,
        "url": url,
        "path": path,
        "sha256": sha256,
        "size_bytes": "",
        "n_cols": "",
        "header_sample": "",
        "n_rows_sampled": "",
    }


def try_head(url: str, *, timeout: int, verify: bool) -> Optional[requests.Response]:
    try:
        response = requests.head(
            url,
            headers=HEADERS,
            timeout=timeout,
            allow_redirects=True,
            verify=verify,
        )
        return response if response.status_code == 200 else None
    except requests.RequestException:
        return None


def extract_remote_meta(response: requests.Response) -> dict[str, str]:
    headers = response.headers
    return {
        "etag": headers.get("ETag", ""),
        "last_modified": headers.get("Last-Modified", ""),
        "content_length": headers.get("Content-Length", ""),
    }


def needs_download(previous: Optional[dict[str, str]], remote: dict[str, str]) -> bool:
    if previous is None:
        return True
    if remote.get("etag") and remote["etag"] != previous.get("etag"):
        return True
    if remote.get("last_modified") and remote["last_modified"] != previous.get("last_modified"):
        return True
    if remote.get("content_length") and remote["content_length"] != previous.get("content_length"):
        return True
    return False


def download_csv(
    kind: str,
    year: int,
    *,
    timeout: int,
    chunk_size: int,
    verify: bool,
) -> Path:
    out_path = bronze_path(kind, year)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    url = url_for(kind, year)

    with requests.get(url, headers=HEADERS, stream=True, timeout=timeout, verify=verify) as response:
        response.raise_for_status()
        tmp_path = out_path.with_suffix(".downloading")
        with tmp_path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    handle.write(chunk)
        tmp_path.replace(out_path)

    return out_path


def validate_csv_basic(path: Path) -> dict[str, object]:
    size_bytes = path.stat().st_size
    if size_bytes == 0:
        raise ValueError(f"Empty CSV file: {path}")

    with path.open("rb") as handle:
        head = handle.read(512 * 1024)

    sample = io.TextIOWrapper(io.BytesIO(head), encoding="utf-8", errors="replace")
    reader = csv.reader(sample, delimiter=";")

    try:
        header = next(reader)
    except StopIteration as exc:
        raise ValueError("CSV has no header") from exc

    sampled_rows = 0
    for _ in range(10):
        try:
            row = next(reader)
        except StopIteration:
            break
        if row:
            sampled_rows += 1

    if sampled_rows == 0:
        raise ValueError("CSV has no sampled data rows")

    return {
        "size_bytes": size_bytes,
        "n_cols": len(header),
        "header_sample": "|".join(header[:20]),
        "n_rows_sampled": sampled_rows,
    }


def bronze_ingest_incremental(
    kind: str,
    year: int,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    verify: bool = True,
    force: bool = False,
) -> dict[str, object]:
    ensure_directories()

    kind = kind.upper()
    url = url_for(kind, year)
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    state_map = read_state_map()
    previous = state_map.get((kind, year))

    print(f"[bronze] checking {kind}_{year}")
    head_response = try_head(url, timeout=timeout, verify=verify)
    if head_response is None:
        append_manifest_row(
            manifest_stub(
                timestamp=timestamp,
                action="source_unavailable",
                kind=kind,
                year=year,
                url=url,
                path=str(bronze_path(kind, year)),
            )
        )
        raise RuntimeError(f"Remote not available for {kind}_{year}: {url}")

    remote_meta = extract_remote_meta(head_response)
    path = bronze_path(kind, year)

    if not force and path.exists() and not needs_download(previous, remote_meta):
        manifest_row = manifest_stub(
            timestamp=timestamp,
            action="skip_unchanged",
            kind=kind,
            year=year,
            url=url,
            path=str(path),
            sha256=previous.get("sha256", "") if previous else "",
        )
        manifest_row["size_bytes"] = path.stat().st_size
        append_manifest_row(manifest_row)
        print(f"[bronze] skipped unchanged {kind}_{year}")
        return {"kind": kind, "year": year, "action": "skip_unchanged", "path": path}

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            print(f"[bronze] downloading {kind}_{year} attempt {attempt}/3")
            path = download_csv(kind, year, timeout=timeout, chunk_size=chunk_size, verify=verify)
            meta = validate_csv_basic(path)
            file_hash = sha256_file(path)

            action = "downloaded_new" if previous is None else "replaced_changed"
            state_row = {
                "kind": kind,
                "year": year,
                "etag": remote_meta.get("etag", ""),
                "last_modified": remote_meta.get("last_modified", ""),
                "content_length": remote_meta.get("content_length", ""),
                "sha256": file_hash,
                "path": str(path),
                "ts_updated": timestamp,
            }
            state_map[(kind, year)] = state_row
            write_state_map(state_map)

            append_manifest_row(
                {
                    "ts": timestamp,
                    "stage": "bronze",
                    "action": action,
                    "kind": kind,
                    "year": year,
                    "url": url,
                    "path": str(path),
                    "sha256": file_hash,
                    **meta,
                }
            )
            print(f"[bronze] {action} {kind}_{year} -> {path}")
            return {"kind": kind, "year": year, "action": action, "path": path}
        except Exception as exc:
            last_error = exc
            print(f"[bronze] failed {kind}_{year} attempt {attempt}/3: {exc}")

    raise RuntimeError(f"Failed bronze ingest for {kind}_{year}: {last_error}")


def discover_years(
    kind: str,
    *,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> list[int]:
    if end_year is None:
        end_year = datetime.utcnow().year

    found: list[int] = []
    for year in range(start_year, end_year + 1):
        if try_head(url_for(kind, year), timeout=timeout, verify=verify):
            found.append(year)
    return found


def bronze_backfill_all(
    *,
    start_year: int = DEFAULT_START_YEAR,
    end_year: int | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    verify: bool = True,
    force: bool = False,
) -> list[int]:
    touched_years: set[int] = set()
    final_year = end_year or datetime.utcnow().year

    for kind in KINDS:
        years = discover_years(
            kind,
            start_year=start_year,
            end_year=final_year,
            timeout=timeout,
            verify=verify,
        )
        print(f"[bronze] discovered {len(years)} {kind} files between {start_year} and {final_year}")
        for year in years:
            result = bronze_ingest_incremental(
                kind,
                year,
                timeout=timeout,
                chunk_size=chunk_size,
                verify=verify,
                force=force,
            )
            touched_years.add(int(result["year"]))

    return sorted(touched_years)


def bronze_monthly_incremental(
    *,
    lookback_years: int = 0,
    timeout: int = DEFAULT_TIMEOUT,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    verify: bool = True,
    force: bool = False,
) -> list[dict[str, object]]:
    current_year = datetime.utcnow().year
    years = list(range(current_year - lookback_years, current_year + 1))
    results: list[dict[str, object]] = []

    for kind in KINDS:
        for year in years:
            try:
                result = bronze_ingest_incremental(
                    kind,
                    year,
                    timeout=timeout,
                    chunk_size=chunk_size,
                    verify=verify,
                    force=force,
                )
            except RuntimeError as exc:
                if str(exc).startswith("Remote not available for "):
                    print(f"[bronze] unavailable {kind}_{year}")
                    results.append({"kind": kind, "year": year, "action": "source_unavailable"})
                    continue
                raise

            results.append(result)

    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download bronze ComexStat CSVs with incremental state tracking.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    monthly = subparsers.add_parser("monthly")
    monthly.add_argument("--lookback-years", type=int, default=0)
    monthly.add_argument("--verify", action=argparse.BooleanOptionalAction, default=True)
    monthly.add_argument("--force", action="store_true")

    backfill = subparsers.add_parser("backfill")
    backfill.add_argument("--start-year", type=int, default=DEFAULT_START_YEAR)
    backfill.add_argument("--end-year", type=int, default=None)
    backfill.add_argument("--verify", action=argparse.BooleanOptionalAction, default=True)
    backfill.add_argument("--force", action="store_true")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "monthly":
        results = bronze_monthly_incremental(
            lookback_years=args.lookback_years,
            verify=args.verify,
            force=args.force,
        )
        changed_years = sorted({int(row["year"]) for row in results if row["action"] in CHANGED_ACTIONS})
        skipped_years = sorted({int(row["year"]) for row in results if row["action"] == "skip_unchanged"})
        unavailable_years = sorted({int(row["year"]) for row in results if row["action"] == "source_unavailable"})
        print(f"[bronze] changed years: {changed_years}")
        print(f"[bronze] skipped years: {skipped_years}")
        print(f"[bronze] unavailable years: {unavailable_years}")
        return

    touched = bronze_backfill_all(
        start_year=args.start_year,
        end_year=args.end_year,
        verify=args.verify,
        force=args.force,
    )
    print(f"[bronze] touched years: {touched}")


if __name__ == "__main__":
    main()
