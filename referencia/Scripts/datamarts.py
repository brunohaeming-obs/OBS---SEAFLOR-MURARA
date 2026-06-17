# cli_datamarts.py
import argparse
from pathlib import Path
from datamart_utils import (
    build_mart_top_products_report,
    build_mart_exp_top_destinations_report,
    build_mart_products_by_sc_competitiva_report,
)

def _add_common(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--kind", choices=["EXP", "IMP"], default="EXP",
                    help="Flow kind (default: EXP)")
    sp.add_argument("--ref-year", type=int, default=None,
                    help="Reference year (e.g., 2025). If omitted, auto-detects.")
    sp.add_argument("--ref-month", type=int, default=None,
                    help="Reference month 1–12. If omitted, auto-detects.")

def _read_sc_file(p: Path | None) -> list[str]:
    if not p:
        return []
    text = Path(p).read_text(encoding="utf-8")
    return [ln.strip() for ln in text.splitlines() if ln.strip()]

def _merge_sc_args(values: list[str] | None, sc_file: Path | None) -> list[str]:
    """Accept repeated --sc, comma-separated values, and/or a file (--sc-file)."""
    out: list[str] = []
    out.extend(_read_sc_file(sc_file))
    if values:
        for v in values:
            out.extend([s.strip() for s in v.split(",") if s.strip()])
    # dedupe preserving order (case-insensitive compare)
    seen = set()
    uniq = []
    for s in out:
        k = s.upper()
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    return uniq

def main():
    p = argparse.ArgumentParser(prog="datamarts", description="Build Comex datamarts")
    sub = p.add_subparsers(dest="cmd", required=True)

    # top-products
    sp = sub.add_parser("top-products", help="Top products report")
    _add_common(sp)

    # top-destinations
    sd = sub.add_parser("top-destinations", help="Top destinations report")
    _add_common(sd)

    # products-by-sc (needs sc list + optional top-n)
    sps = sub.add_parser("products-by-sc", help="Products by SC Competitiva category")
    _add_common(sps)
    sps.add_argument("--sc", dest="sc_comp", action="append",
                     help="Category name(s). Repeat flag or comma-separated.")
    sps.add_argument("--sc-file", type=Path,
                     help="UTF-8 file with one category per line (PowerShell-friendly).")
    sps.add_argument("--top-n", type=int, default=None,
                     help="Limit number of products (default: all)")
    sps.add_argument("--each", action="store_true",
                     help="Build a separate mart for each category (default: one combined).")

    # --- Build everything for both EXP/IMP and selected sectors ---
    sa = sub.add_parser("all", help="Build top-products, top-destinations, and products-by-sc for EXP & IMP")
    _add_common(sa)  # kind will be ignored; we loop both
    sa.add_argument("--sc", dest="sc_comp", action="append",
                    help="Sector(s). Repeat flag or comma-separated.")
    sa.add_argument("--sc-file", type=Path,
                    help="UTF-8 file with one sector per line.")
    sa.add_argument("--top-n", type=int, default=None,
                    help="Limit for products-by-sc (default: all)")
    sa.add_argument("--each", action="store_true",
                    help="Separate output per sector (default: combined).")

    args = p.parse_args()

    if args.cmd == "all":
        cats = _merge_sc_args(args.sc_comp, getattr(args, "sc_file", None))
        outs = []
        for kind in ("EXP", "IMP"):
            outs.append(build_mart_top_products_report(
                ref_year=args.ref_year, ref_month=args.ref_month, kind=kind))
            outs.append(build_mart_exp_top_destinations_report(
                ref_year=args.ref_year, ref_month=args.ref_month, kind=kind))

            if args.each and cats:
                for cat in cats:
                    outs.append(build_mart_products_by_sc_competitiva_report(
                        sc_competitiva=cat,  # 👈 one categoria per file
                        ref_year=args.ref_year, ref_month=args.ref_month,
                        kind=kind, top_n=args.top_n))
            else:
                outs.append(build_mart_products_by_sc_competitiva_report(
                    sc_competitiva=cats or None,  # combined or no filter
                    ref_year=args.ref_year, ref_month=args.ref_month,
                    kind=kind, top_n=args.top_n))
        print("✔ wrote:\n" + "\n".join(str(p) for p in outs))
        return

    if args.cmd == "top-products":
        out = build_mart_top_products_report(
            ref_year=args.ref_year, ref_month=args.ref_month, kind=args.kind
        )

    elif args.cmd == "top-destinations":
        out = build_mart_exp_top_destinations_report(
            ref_year=args.ref_year, ref_month=args.ref_month, kind=args.kind
        )

    elif args.cmd == "products-by-sc":
        cats = _merge_sc_args(args.sc_comp, getattr(args, "sc_file", None))
        if args.each and cats:
            outs = []
            for cat in cats:
                outs.append(build_mart_products_by_sc_competitiva_report(
                    sc_competitiva=cat,
                    ref_year=args.ref_year, ref_month=args.ref_month,
                    kind=args.kind, top_n=args.top_n
                ))
            print("✔ wrote:\n" + "\n".join(str(p) for p in outs))
            return
        else:
            out = build_mart_products_by_sc_competitiva_report(
                sc_competitiva=cats or None,
                ref_year=args.ref_year, ref_month=args.ref_month,
                kind=args.kind, top_n=args.top_n
            )

    print(f"✔ wrote {out}")

if __name__ == "__main__":
    main()
