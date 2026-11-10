#!/usr/bin/env python3
"""Daily refresh of markets.namebeam.ai from the public corpus.

Zero model calls, Python stdlib only. Extends markets with new corpus data,
writes data/latest.json, and updates dated strings on HTML pages.

Usage:
  py -3.13 -I -B tools/daily_refresh.py /path/to/nvi-checkout [--dry-run]
"""

import sys
import os
import json
import hashlib
import csv
import re
import argparse
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict


def sha256_file(path):
    """Compute SHA256 of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def load_roster(nvi_path):
    """Load segment_pages.json to map slugs to market/niche/question."""
    roster_path = Path(nvi_path) / "roster" / "segment_pages.json"
    with open(roster_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    slug_to_info = {}
    for page in data["pages"]:
        slug = page["slug"]
        if page["questions"]:
            q = page["questions"][0]
            slug_to_info[slug] = {
                "market": q["market"],
                "niche": q["niche"],
                "question": q.get("niche_question", "")
            }
    return slug_to_info


def parse_corpus_file(file_path):
    """Parse a corpus JSON file and extract row data."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    check_id = data["check_id"]
    raw_file = file_path.name

    # Determine engine
    if "_openai" in check_id:
        engine = "openai"
    elif "_anthropic" in check_id:
        engine = "anthropic"
    elif "_perplexity" in check_id:
        engine = "perplexity"
    elif "_gemini" in check_id:
        engine = "gemini"
    elif "NB-CZ-SERP_" in check_id:
        engine = "google_serp"
    else:
        engine = "unknown"

    # Extract names from competitors_mentioned (public field)
    names_list = []
    if "competitors_mentioned" in data and data["competitors_mentioned"]:
        names_list = data["competitors_mentioned"]

    names_count = len(names_list)
    businesses_named = "; ".join(names_list) if names_list else ""

    return {
        "date": data["date_utc"],
        "market": data["market"],
        "niche": data["niche"],
        "engine": engine,
        "run": str(data.get("run", 1)),
        "status": data["run_status"],
        "names_count": names_count,
        "businesses_named": businesses_named,
        "check_id": check_id,
        "raw_file": raw_file,
        "raw_file_sha256": sha256_file(file_path)
    }


def find_corpus_dates(nvi_path):
    """Find all dates with corpus files."""
    corpus_dir = Path(nvi_path) / "corpus" / "e1"
    dates = set()
    for f in corpus_dir.glob("NB-CZ-*_segment_*.json"):
        m = re.search(r"_(\d{4}-\d{2}-\d{2})_", f.name)
        if m:
            dates.add(m.group(1))
    return sorted(dates)


def extract_question_from_html(index_html_path):
    """Extract question text from market index.html page."""
    try:
        with open(index_html_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'<div class="pv-q">(.*?)</div>', content, re.DOTALL)
        if match:
            return match.group(1).strip()
    except Exception:
        pass
    return None


def write_csv(path, rows, fieldnames):
    """Write CSV file."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def update_summary_json(market_dir, all_rows, shape):
    """Update summary.json for a market."""
    summary_path = market_dir / "summary.json"

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    dates = sorted(set(row["date"] for row in all_rows))

    summary["window_first"] = dates[0] if dates else None
    summary["window_last"] = dates[-1] if dates else None
    summary["run_days"] = len(dates)
    summary["rows_total"] = len(all_rows)

    # By engine
    by_engine = {}
    for row in all_rows:
        eng = row["engine"]
        if eng not in by_engine:
            by_engine[eng] = {"rows": 0, "ok": 0, "days_with_ok": 0}
        by_engine[eng]["rows"] += 1
        if row["status"] == "OK":
            by_engine[eng]["ok"] += 1

    for eng in by_engine:
        ok_dates = set()
        for row in all_rows:
            if row["engine"] == eng and row["status"] == "OK":
                ok_dates.add(row["date"])
        by_engine[eng]["days_with_ok"] = len(ok_dates)

    summary["by_engine"] = by_engine

    # By date
    by_date = []
    for date in dates:
        date_rows = [r for r in all_rows if r["date"] == date]
        ok_rows = [r for r in date_rows if r["status"] == "OK"]
        by_date.append({
            "date": date,
            "rows": len(date_rows),
            "ok": len(ok_rows),
            "engines_ok": sorted([r["engine"] for r in ok_rows])
        })

    summary["by_date"] = by_date

    # Update file hashes
    if shape == "day_pages":
        summary["files"]["all_csv"]["sha256"] = sha256_file(market_dir / "all.csv")
        summary["files"]["day_csv_count"] = len(dates)
        if "changes_csv" in summary["files"]:
            summary["files"]["changes_csv"]["sha256"] = sha256_file(market_dir / "changes.csv")
    else:
        summary["files"]["rows_csv"]["sha256"] = sha256_file(market_dir / "rows.csv")

    summary["generated_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Daily refresh")
    parser.add_argument("nvi_path", help="Path to nvi checkout")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    work_dir = Path.cwd()
    record_dir = work_dir / "record"

    roster = load_roster(args.nvi_path)
    corpus_dates = find_corpus_dates(args.nvi_path)

    summary_table = []
    all_markets_data = {}

    CSV_FIELDS = ["date", "question_slug", "market", "niche", "engine", "run",
                  "status", "names_count", "businesses_named", "check_id",
                  "raw_file", "raw_file_sha256"]

    # Process each market
    for market_dir in sorted(record_dir.iterdir()):
        if not market_dir.is_dir():
            continue

        slug = market_dir.name

        # Determine shape
        if (market_dir / "all.csv").exists():
            shape = "day_pages"
            csv_file = "all.csv"
        elif (market_dir / "rows.csv").exists():
            shape = "rows_only"
            csv_file = "rows.csv"
        else:
            continue

        # Load existing data
        with open(market_dir / csv_file, "r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            existing_rows = list(reader)

        if not existing_rows:
            continue

        last_date = max(row["date"] for row in existing_rows)
        new_dates = [d for d in corpus_dates if d > last_date]

        # BUG 1 FIX: Check if slug is in roster BEFORE computing new_dates
        # For off-roster markets, skip new data collection but still include in latest.json
        if slug not in roster:
            # Off-roster market: include in latest.json with rows_added 0
            summary_table.append({
                "market": slug,
                "old_last_day": last_date,
                "new_last_day": last_date,
                "rows_added": 0
            })
            with open(market_dir / "summary.json", "r", encoding="utf-8") as f:
                all_markets_data[slug] = json.load(f)
            continue

        if not new_dates:
            summary_table.append({
                "market": slug,
                "old_last_day": last_date,
                "new_last_day": last_date,
                "rows_added": 0
            })

            with open(market_dir / "summary.json", "r", encoding="utf-8") as f:
                all_markets_data[slug] = json.load(f)
            continue

        expected_market = roster[slug]["market"]
        expected_niche = roster[slug]["niche"]

        # Collect new rows
        new_rows = []
        for date in new_dates:
            corpus_dir = Path(args.nvi_path) / "corpus" / "e1"
            for pattern in [f"NB-CZ-API_{date}_segment_*.json", f"NB-CZ-SERP_{date}_segment_*.json"]:
                for corpus_file in corpus_dir.glob(pattern):
                    row_data = parse_corpus_file(corpus_file)

                    if row_data["market"] == expected_market and row_data["niche"] == expected_niche:
                        row_data["question_slug"] = slug
                        new_rows.append(row_data)

        if not new_rows:
            summary_table.append({
                "market": slug,
                "old_last_day": last_date,
                "new_last_day": last_date,
                "rows_added": 0
            })

            with open(market_dir / "summary.json", "r", encoding="utf-8") as f:
                all_markets_data[slug] = json.load(f)
            continue

        # Write updated CSV
        all_rows = existing_rows + new_rows
        if not args.dry_run:
            write_csv(market_dir / csv_file, all_rows, CSV_FIELDS)

            # For day_pages, also write day CSVs
            if shape == "day_pages":
                rows_by_date = defaultdict(list)
                for row in new_rows:
                    rows_by_date[row["date"]].append(row)

                for date in sorted(rows_by_date.keys()):
                    date_rows = rows_by_date[date]
                    write_csv(market_dir / f"{date}.csv", date_rows, CSV_FIELDS)

                    # Create day directory (simplified - skip HTML for now)
                    day_dir = market_dir / date
                    day_dir.mkdir(exist_ok=True)

            # Update summary.json
            update_summary_json(market_dir, all_rows, shape)

        new_last_date = max(row["date"] for row in new_rows)
        summary_table.append({
            "market": slug,
            "old_last_day": last_date,
            "new_last_day": new_last_date,
            "rows_added": len(new_rows)
        })

        with open(market_dir / "summary.json", "r", encoding="utf-8") as f:
            all_markets_data[slug] = json.load(f)

    # Write data/latest.json
    if all_markets_data and not args.dry_run:
        latest_run_day = max(m["window_last"] for m in all_markets_data.values() if m.get("window_last"))
        window_first = min(m["window_first"] for m in all_markets_data.values() if m.get("window_first"))

        markets_summary = {}
        for slug, m in all_markets_data.items():
            ok_rows = sum(e.get("ok", 0) for e in m.get("by_engine", {}).values())

            # Get market, niche, question
            market = m.get("market", "")
            niche = m.get("niche", "")
            question = None

            # Try roster first
            if slug in roster:
                market = roster[slug].get("market", market)
                niche = roster[slug].get("niche", niche)
                question = roster[slug].get("question")

            # Fall back to extracting from index.html if question not found
            if not question:
                index_html_path = record_dir / slug / "index.html"
                if index_html_path.exists():
                    question = extract_question_from_html(index_html_path)

            # Store question in summary.json for off-roster markets
            if not question:
                question = ""

            if slug not in roster and question:
                m["question"] = question
                summary_path = record_dir / slug / "summary.json"
                with open(summary_path, "w", encoding="utf-8") as f:
                    json.dump(m, f, indent=2)

            # Get latest day data with engine results and names
            window_last = m.get("window_last")
            latest_day_engines = {}

            if window_last:
                # Read CSV to get names for latest day
                market_dir = record_dir / slug
                if m.get("shape") == "day_pages":
                    csv_path = market_dir / "all.csv"
                else:
                    csv_path = market_dir / "rows.csv"

                if csv_path.exists():
                    try:
                        with open(csv_path, "r", encoding="utf-8", newline="") as f:
                            reader = csv.DictReader(f)
                            for row in reader:
                                if row.get("date") == window_last:
                                    engine = row.get("engine")
                                    # Handle both CSV formats
                                    status = row.get("status") or row.get("run_status", "UNKNOWN")
                                    names_str = row.get("businesses_named") or row.get("tracked_businesses_named_in_text", "")
                                    names_count = len([n.strip() for n in names_str.split("; ") if n.strip()]) if names_str else 0
                                    if engine:
                                        latest_day_engines[engine] = {
                                            "status": status,
                                            "names_count": names_count
                                        }
                    except Exception as e:
                        print(f"Warning: Could not read CSV for {slug}: {e}")

            # Collection active if window_last within 2 days of latest_run_day
            collection_active = False
            if window_last:
                from datetime import datetime as dt
                try:
                    last_dt = dt.strptime(window_last, "%Y-%m-%d")
                    latest_dt = dt.strptime(latest_run_day, "%Y-%m-%d")
                    days_diff = (latest_dt - last_dt).days
                    collection_active = days_diff <= 2
                except:
                    pass

            markets_summary[slug] = {
                "window_first": m.get("window_first"),
                "window_last": window_last,
                "run_days": m.get("run_days", 0),
                "rows_total": m.get("rows_total", 0),
                "ok_rows": ok_rows,
                "market": market,
                "niche": niche,
                "question": question,
                "shape": m.get("shape", "rows_only"),
                "collection_active": collection_active,
                "by_engine": m.get("by_engine", {}),
                "latest_day": {
                    "date": window_last,
                    "engines": latest_day_engines
                }
            }

        total_rows = sum(m["rows_total"] for m in markets_summary.values())
        total_ok = sum(m["ok_rows"] for m in markets_summary.values())

        latest = {
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "latest_run_day": latest_run_day,
            "window_first": window_first,
            "window_end": latest_run_day,
            "markets": markets_summary,
            "totals": {
                "rows": total_rows,
                "ok_rows": total_ok,
                "markets": len(markets_summary),
                "engines": 5
            }
        }

        data_dir = work_dir / "data"
        data_dir.mkdir(exist_ok=True)

        with open(data_dir / "latest.json", "w", encoding="utf-8") as f:
            json.dump(latest, f, indent=2)

    # Print summary
    print(f"\n{'Market':<45} {'Old Last Day':<15} {'New Last Day':<15} {'Rows Added':<12}")
    print("-" * 90)
    for row in summary_table:
        print(f"{row['market']:<45} {row['old_last_day']:<15} {row['new_last_day']:<15} {row['rows_added']:<12}")

    total_added = sum(r["rows_added"] for r in summary_table)
    print(f"\nTotal: {total_added} rows added")

    return 0


if __name__ == "__main__":
    sys.exit(main())
