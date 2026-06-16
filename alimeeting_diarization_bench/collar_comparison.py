"""CLI entry point for collar comparison: python -m alimeeting_diarization_bench.collar_comparison"""

import argparse
import logging
from pathlib import Path

from .config import Paths
from .evaluation.collar_comparison import compare_collars


def main():
    parser = argparse.ArgumentParser(description="Collar comparison for DER evaluation")
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Path to checkpoint.json (default: auto-detect from output_dir/model_name)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="fun_asr",
        help="Model name to find checkpoint (default: fun_asr)",
    )
    parser.add_argument(
        "--collars",
        type=float,
        nargs="+",
        default=[0.0, 0.25, 0.5],
        help="Collar values in seconds (default: 0.0 0.25 0.5)",
    )
    parser.add_argument(
        "--manifest-dir",
        type=str,
        default=None,
        help="Override manifest directory",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    paths = Paths.from_env()
    manifest_dir = Path(args.manifest_dir) if args.manifest_dir else paths.manifest_dir

    if args.checkpoint:
        checkpoint_path = Path(args.checkpoint)
    else:
        checkpoint_path = paths.output_dir / args.model / "checkpoint.json"

    if not checkpoint_path.exists():
        print("ERROR: Checkpoint not found: %s" % checkpoint_path)
        print("Run an experiment first, or specify --checkpoint path.")
        return

    results = compare_collars(checkpoint_path, manifest_dir, args.collars)

    print("\n" + "=" * 70)
    print("  Collar Comparison: %s" % checkpoint_path.parent.name)
    print(
        "  %s %s %s %s %s %s"
        % (
            "Collar".rjust(8),
            "DER".rjust(8),
            "Miss".rjust(8),
            "FA".rjust(8),
            "Conf".rjust(8),
            "N".rjust(5),
        )
    )
    print("-" * 70)
    for collar, data in sorted(results.items()):
        n = data["n_segments"]
        if n > 0:
            print(
                "  %7.2fs %8.2f%% %8.2f%% %8.2f%% %8.2f%% %5d"
                % (
                    collar,
                    data["avg_der"] * 100,
                    data["avg_miss"] * 100,
                    data["avg_fa"] * 100,
                    data["avg_conf"] * 100,
                    n,
                )
            )
    print("=" * 70)


if __name__ == "__main__":
    main()
