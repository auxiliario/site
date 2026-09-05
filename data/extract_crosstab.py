#!/usr/bin/env python3
"""
Re-extract a two-way cuadro from the source PDF by GEOMETRY, and diff it
against what is currently transcribed in sources/.

    python extract_crosstab.py --pdf a25.pdf --cuadro "Cuadro 3.5"
    python extract_crosstab.py --pdf a25.pdf --page 91 --cuadro "Cuadro 3.5"

Why geometry rather than `pdftotext -layout`: -layout reflows a wide table
into fixed-width text and silently drops or merges a column when the page
is wider than its assumed character grid. That is the failure mode under
suspicion in Cuadro 3.5. Here every number keeps its x-position, columns
are recovered by clustering those positions, and any row whose cell count
disagrees with the header is reported rather than quietly padded.

The verdict this prints is the thing that settles the Cuadro 3.5 dispute:

  MATCHES TRANSCRIPTION   the PDF really does print cells that do not sum
                          to its own margins -> the defect is ONE's, keep
                          the cells as published and keep trust downgraded
  DIFFERS                 the transcription was wrong; the corrected
                          literals are printed ready to paste into
                          sources/, after which `python build.py` and
                          `python validate.py` re-derive trust
"""
import argparse, hashlib, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "sources"))

NUM = re.compile(r"^-?[\d.,]+$")
SYMBOLS = {"-", "--", "..", "...", "n/d", "nd"}


# ---------------------------------------------------------------- helpers
def parse_cell(tok):
    """Return (value, symbol). ONE prints thousands separators, and uses
    symbols for 'not applicable' that must not be read as zero."""
    t = tok.strip()
    if t in SYMBOLS:
        return None, t
    if not NUM.match(t):
        return None, None          # ordinary text: not a cell at all
    t = t.replace(",", "")
    try:
        return (float(t) if "." in t else int(t)), None
    except ValueError:
        return None, None


def cluster(values, tol):
    """1-D gap clustering. Returns sorted cluster centres."""
    out = []
    for v in sorted(values):
        if out and v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(c) / len(c) for c in out]


def page_lines(page, ytol=2.5):
    """Group words into visual lines, preserving each word's x-span."""
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    lines = {}
    for w in words:
        key = min(lines, key=lambda k: abs(k - w["top"]), default=None)
        if key is None or abs(key - w["top"]) > ytol:
            key = w["top"]
        lines.setdefault(key, []).append(w)
    return [sorted(ws, key=lambda w: w["x0"])
            for _, ws in sorted(lines.items())]


# ------------------------------------------------------------- extraction
def find_pages(pdf, cuadro):
    hits = []
    for i, page in enumerate(pdf.pages, start=1):
        txt = page.extract_text() or ""
        if cuadro.lower() in txt.lower():
            hits.append(i)
    return hits


def extract_grid(page, n_cols, xtol=6.0, min_cells=None):
    """Recover a numeric grid plus its row stubs.

    Two passes. The first identifies DATA lines -- those carrying at least
    `min_cells` numeric tokens -- and clusters only their x-centres, so a
    caption or a rotated column header cannot invent a column. The second
    places each cell in its nearest column, leaving a HOLE where a cell is
    missing rather than shifting its neighbours left. That distinction is
    the whole point: a silently-padded row is exactly the corruption under
    investigation.

    `xtol` is auto-tuned to land on `n_cols` clusters when it can; the
    tolerance actually used is returned so the result is reproducible.
    """
    lines = page_lines(page)
    min_cells = min_cells or max(3, n_cols // 2)

    def cells_of(ws):
        out = []
        for w in ws:
            v, sym = parse_cell(w["text"])
            if v is not None or sym is not None:
                out.append((w, v, sym))
        return out

    data_lines = [(ws, cs) for ws in lines
                  if len(cs := cells_of(ws)) >= min_cells]
    centres_x = [(w["x0"] + w["x1"]) / 2 for _, cs in data_lines
                 for w, _, _ in cs]
    if not centres_x:
        return [], [], xtol, ["no data lines found on this page"]

    # auto-tune the clustering tolerance to the expected column count
    best = (xtol, cluster(centres_x, xtol))
    for t in [x / 2 for x in range(2, 61)]:
        c = cluster(centres_x, t)
        if len(c) == n_cols:
            best = (t, c)
            break
        if abs(len(c) - n_cols) < abs(len(best[1]) - n_cols):
            best = (t, c)
    xtol, centres = best

    rows, warnings = [], []
    if len(centres) != n_cols:
        warnings.append(f"clustered {len(centres)} column positions, expected "
                        f"{n_cols} (best tolerance {xtol}); inspect the page")
    for ws, cs in data_lines:
        stub = " ".join(w["text"] for w in ws
                        if parse_cell(w["text"]) == (None, None)).strip()
        cells = [None] * len(centres)
        for w, v, sym in cs:
            cx = (w["x0"] + w["x1"]) / 2
            j = min(range(len(centres)), key=lambda k: abs(centres[k] - cx))
            if cells[j] is not None:
                warnings.append(f"{stub!r}: two tokens collide in column {j} "
                                f"({cells[j]} and {v if v is not None else sym})")
            cells[j] = v if v is not None else sym
        holes = [j for j, c in enumerate(cells) if c is None]
        if holes:
            warnings.append(f"{stub!r}: no cell under column(s) "
                            f"{holes} -- printed blank, or the row is short")
        rows.append((stub, cells))
    return rows, centres, xtol, warnings


# ------------------------------------------------------------------ diff
def diff_grid(expected_rows, expected_cols, expected, got_rows):
    """Compare a recovered grid to the transcribed literals."""
    by_stub = {}
    for stub, cells in got_rows:
        key = stub.strip()
        if key:
            by_stub[key] = cells

    def match(label):
        for k in by_stub:
            if k.lower().startswith(label.lower()[:12]):
                return k
        return None

    diffs, missing = [], []
    for r in expected_rows:
        k = match(r)
        if k is None:
            missing.append(r)
            continue
        got = by_stub[k]
        exp = expected[r]
        for j, ev in enumerate(exp):
            gv = got[j] if j < len(got) else None
            if gv != ev:
                diffs.append((r, expected_cols[j] if j < len(expected_cols)
                              else f"col{j}", ev, gv))
    return diffs, missing


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--cuadro", default="Cuadro 3.5")
    ap.add_argument("--page", type=int,
                    help="1-based PDF page index; omit to search by caption")
    ap.add_argument("--expect-sha",
                    default="42ec03d0ef6d7e2e18af0f4555eb8270"
                            "fae0b624aa89cd74d24fc6880956ef70")
    args = ap.parse_args()

    import pdfplumber
    import anuario_2025 as A

    sha = hashlib.sha256(open(args.pdf, "rb").read()).hexdigest()
    print(f"sha256 {sha}")
    if args.expect_sha and sha != args.expect_sha:
        print(f"  WARNING: does not match the recorded source_document sha256\n"
              f"           expected {args.expect_sha}\n"
              f"  This is a different file from the one the transcription came "
              f"from; a diff below may reflect an edition change, not an "
              f"extraction error.")
    else:
        print("  matches source_document.sha256 -- same file as transcribed")

    SPECS = {
        "Cuadro 3.5": (list(A.C35), A.C35_COLS, A.C35,
                       A.C35_ROW_TOTALS, A.C35_COL_TOTALS, 40750),
        "Cuadro 4.5": (list(A.C45), A.C45_COLS, A.C45,
                       A.C45_ROW_TOTALS, None, 24711),
    }
    if args.cuadro not in SPECS:
        sys.exit(f"no transcription on file for {args.cuadro}")
    exp_rows, exp_cols, expected, row_tot, col_tot, control = SPECS[args.cuadro]

    with pdfplumber.open(args.pdf) as pdf:
        pages = [args.page] if args.page else find_pages(pdf, args.cuadro)
        if not pages:
            sys.exit(f"{args.cuadro} not found in {args.pdf}")
        print(f"{args.cuadro} found on PDF page(s): {pages}")
        page = pdf.pages[pages[-1] - 1]
        rows, centres, xtol, warnings = extract_grid(page, len(exp_cols) + 1)

    print(f"\nrecovered {len(rows)} data lines across {len(centres)} column "
          f"positions at tolerance {xtol} "
          f"(expected {len(exp_cols)} data columns + 1 total)")
    for w in warnings:
        print("  WARN " + w)

    diffs, missing = diff_grid(exp_rows, exp_cols, expected, rows)
    if missing:
        print("\nrows not located on the page: " + ", ".join(missing))

    if not diffs and not missing:
        print(f"\nVERDICT: MATCHES TRANSCRIPTION")
        print(f"  Every cell in the PDF equals what sources/anuario_2025.py "
              f"already records.\n"
              f"  The published cells genuinely do not sum to the published "
              f"margins, so the\n"
              f"  defect is ONE's, not the extractor's. Keep the cells as "
              f"published, keep\n"
              f"  trust='marginals_only', and cite known_issue 1 when "
              f"reporting.")
    else:
        print(f"\nVERDICT: DIFFERS -- {len(diffs)} cell(s) disagree")
        print(f"  {'row':<24}{'column':<24}{'transcribed':>12}{'in PDF':>12}")
        for r, c, ev, gv in diffs[:60]:
            print(f"  {r:<24}{c:<24}{ev!s:>12}{gv!s:>12}")
        if len(diffs) > 60:
            print(f"  ... and {len(diffs)-60} more")
        new_total = sum(v for _, cells in rows for v in cells
                        if isinstance(v, (int, float)))
        print(f"\n  Re-extracted interior sums to {new_total:,.0f}; "
              f"the control total is {control:,}.")
        print("  Paste the corrected grid into sources/anuario_2025.py, then "
              "run:\n    python build.py && python validate.py\n"
              "  Trust is re-derived from the numbers; nothing needs editing "
              "by hand.")


if __name__ == "__main__":
    main()
