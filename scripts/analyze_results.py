#!/usr/bin/env python3
"""Analyze batch experiment results and produce ranked model comparison."""

import csv
import json
import sys
from pathlib import Path
from collections import defaultdict


def load_csv_results(output_dir: Path) -> dict[str, list[dict]]:
    """Load results.csv from each model subdirectory."""
    model_results = {}
    for model_dir in sorted(output_dir.iterdir()):
        csv_path = model_dir / "results.csv"
        if not csv_path.exists():
            continue
        model_name = model_dir.name
        rows = []
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for key in (
                    "der",
                    "miss_rate",
                    "fa_rate",
                    "conf_rate",
                    "cer",
                    "latency",
                ):
                    val = row.get(key, "")
                    row[key] = float(val) if val and val not in ("", "None") else None
                for key in ("spk_count_pred", "spk_count_gt"):
                    row[key] = int(row[key]) if row[key] else 0
                row["success"] = row["success"] == "True"
                row["spk_match"] = row["spk_match"] == "True"
                rows.append(row)
        model_results[model_name] = rows
    return model_results


def compute_stats(rows: list[dict]) -> dict:
    """Compute aggregate stats from result rows."""
    successful = [r for r in rows if r["success"]]
    if not successful:
        return {"n": 0, "n_success": 0}

    der_vals = [r["der"] for r in successful if r.get("der") is not None]
    spk_matches = [r["spk_match"] for r in successful]
    latencies = [r["latency"] for r in successful]

    stats = {
        "n": len(rows),
        "n_success": len(successful),
        "n_failed": len(rows) - len(successful),
        "avg_der": sum(der_vals) / len(der_vals) if der_vals else None,
        "median_der": sorted(der_vals)[len(der_vals) // 2] if der_vals else None,
        "min_der": min(der_vals) if der_vals else None,
        "max_der": max(der_vals) if der_vals else None,
        "spk_match_rate": sum(spk_matches) / len(spk_matches) if spk_matches else None,
        "avg_latency": sum(latencies) / len(latencies) if latencies else None,
    }

    by_spk = defaultdict(list)
    for r in successful:
        spk = r.get("spk_count_gt", 0)
        by_spk[spk].append(r)

    stats["by_speaker_count"] = {}
    for spk_count, spk_rows in sorted(by_spk.items()):
        spk_der = [r["der"] for r in spk_rows if r.get("der") is not None]
        spk_match = [r["spk_match"] for r in spk_rows]
        stats["by_speaker_count"][spk_count] = {
            "n": len(spk_rows),
            "avg_der": sum(spk_der) / len(spk_der) if spk_der else None,
            "spk_match_rate": sum(spk_match) / len(spk_match) if spk_match else None,
        }

    return stats


def print_report(model_results: dict):
    """Print analysis report to stdout."""
    all_stats = {}
    for model, rows in model_results.items():
        all_stats[model] = compute_stats(rows)

    if not all_stats:
        print("No results found.")
        return

    print("=" * 80)
    print("  AliMeeting Diarization Benchmark — Batch Analysis")
    print("=" * 80)

    ranked = sorted(
        all_stats.items(),
        key=lambda x: x[1].get("avg_der", 999) if x[1].get("avg_der") else 999,
    )

    print(
        f"\n{'Rank':<5} {'Model':<18} {'DER%':<8} {'SpkMatch%':<10} {'Latency':<10} {'N':<6}"
    )
    print("-" * 57)
    for i, (model, stats) in enumerate(ranked, 1):
        der = stats.get("avg_der")
        spk = stats.get("spk_match_rate")
        lat = stats.get("avg_latency")
        n = stats.get("n_success", 0)
        der_str = f"{der * 100:.1f}" if der is not None else "N/A"
        spk_str = f"{spk * 100:.1f}" if spk is not None else "N/A"
        lat_str = f"{lat:.1f}s" if lat is not None else "N/A"
        marker = " ⭐" if i <= 3 else ""
        print(
            f"  {i:<3} {model:<18} {der_str:<8} {spk_str:<10} {lat_str:<10} {n:<6}{marker}"
        )

    print("\n--- DER by Speaker Count ---")
    spk_counts = set()
    for model, stats in all_stats.items():
        for spk in stats.get("by_speaker_count", {}):
            spk_counts.add(spk)

    header = f"{'Model':<18}" + "".join(
        f"  {spk}-spk DER%  Match%" for spk in sorted(spk_counts)
    )
    print(header)
    print("-" * len(header))
    for model, stats in ranked:
        row = f"{model:<18}"
        for spk in sorted(spk_counts):
            spk_stats = stats.get("by_speaker_count", {}).get(spk, {})
            der = spk_stats.get("avg_der")
            match = spk_stats.get("spk_match_rate")
            der_str = f"{der * 100:.1f}" if der is not None else "-"
            match_str = f"{match * 100:.0f}%" if match is not None else "-"
            row += f"    {der_str:>6}     {match_str:>4}"
        print(row)

    top3 = [model for model, _ in ranked[:3]]
    print(f"\n🏆 Top 3 models for full-dataset testing: {', '.join(top3)}")
    print(
        f"   Run: python -m alimeeting_diarization_bench.run --model <model> --sampling-mode stratified --total-samples 504"
    )


def export_analysis_csv(model_results: dict, output_dir: Path):
    """Export analysis to a single comparison CSV."""
    csv_path = output_dir / "model_comparison.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "model",
                "n_total",
                "n_success",
                "avg_der",
                "median_der",
                "min_der",
                "max_der",
                "spk_match_rate",
                "avg_latency",
            ]
        )
        for model, rows in model_results.items():
            stats = compute_stats(rows)
            if stats.get("n_success", 0) > 0:
                writer.writerow(
                    [
                        model,
                        stats["n"],
                        stats["n_success"],
                        f"{stats['avg_der']:.4f}" if stats.get("avg_der") else "",
                        f"{stats['median_der']:.4f}" if stats.get("median_der") else "",
                        f"{stats['min_der']:.4f}" if stats.get("min_der") else "",
                        f"{stats['max_der']:.4f}" if stats.get("max_der") else "",
                        f"{stats['spk_match_rate']:.4f}"
                        if stats.get("spk_match_rate")
                        else "",
                        f"{stats['avg_latency']:.2f}"
                        if stats.get("avg_latency")
                        else "",
                    ]
                )
    print(f"\nComparison CSV saved to: {csv_path}")


def main():
    output_dir = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path.home() / "data" / "AliMeeting" / "batch_results_v2"
    )
    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}")
        sys.exit(1)

    model_results = load_csv_results(output_dir)
    if not model_results:
        print(f"No model results found in {output_dir}")
        sys.exit(1)

    print_report(model_results)
    export_analysis_csv(model_results, output_dir)


if __name__ == "__main__":
    main()
