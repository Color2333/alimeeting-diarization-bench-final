"""CLI entry point for running diarization experiments."""

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import Paths
from .evaluation.runner import ExperimentRunner, get_model, MODEL_REGISTRY


def main():
    parser = argparse.ArgumentParser(
        description="AliMeeting Speaker Diarization Benchmark"
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        choices=list(MODEL_REGISTRY.keys()),
        help="Model to evaluate",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        nargs="+",
        default=[30],
        help="Window sizes in seconds (default: 30)",
    )
    parser.add_argument(
        "--segments-per-meeting",
        type=int,
        default=3,
        help="Number of segments per meeting per window size (default: 3)",
    )
    parser.add_argument(
        "--collar",
        type=float,
        default=0.0,
        help="DER collar in seconds (default: 0.0)",
    )
    parser.add_argument(
        "--prompt-variant",
        type=str,
        default="default",
        help="Prompt variant for LLM-based models (default: default)",
    )
    parser.add_argument(
        "--max-segments",
        type=int,
        default=None,
        help="Limit total segments (for testing)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Override output directory",
    )
    parser.add_argument(
        "--segments-manifest",
        type=Path,
        default=None,
        help=(
            "CSV manifest of explicit windows to process. Required columns: "
            "recording_id, window_size, segment_idx, offset, duration; "
            "audio_path, spk_count_gt, and speaker_count_hint are optional."
        ),
    )
    parser.add_argument(
        "--summary-name",
        type=str,
        default="summary.json",
        help="Summary filename under the model output directory (default: summary.json)",
    )
    parser.add_argument(
        "--results-name",
        type=str,
        default="results.csv",
        help="Results CSV filename under the model output directory (default: results.csv)",
    )
    parser.add_argument(
        "--force-reprocess",
        action="store_true",
        help="Recompute selected segments even when checkpoint entries already exist.",
    )
    parser.add_argument(
        "--use-gpu",
        action="store_true",
        help="Enable GPU (for local models like PyAnnote)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--sampling-mode",
        type=str,
        choices=["uniform", "stratified"],
        default="uniform",
        help="Sampling strategy: uniform or stratified (default: uniform)",
    )
    parser.add_argument(
        "--total-samples",
        type=int,
        default=120,
        help="Total samples for stratified sampling (default: 120)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for stratified sampling (default: 42)",
    )
    parser.add_argument(
        "--speaker-count-mode",
        type=str,
        choices=["oracle", "none", "bounds", "hint"],
        default="oracle",
        help=(
            "Speaker count hint strategy: oracle passes GT speaker count; "
            "none passes no count; bounds passes min/max when the model supports it; "
            "hint passes per-window speaker_count_hint from a manifest"
        ),
    )
    parser.add_argument(
        "--min-speakers",
        type=int,
        default=1,
        help="Lower speaker-count bound for --speaker-count-mode bounds",
    )
    parser.add_argument(
        "--max-speakers",
        type=int,
        default=8,
        help="Upper speaker-count bound for --speaker-count-mode bounds",
    )
    parser.add_argument(
        "--pipeline-params",
        type=str,
        default=None,
        help=(
            "JSON object with model-specific pipeline parameters, e.g. "
            "'{\"clustering\":{\"threshold\":0.55}}'"
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logger = logging.getLogger(__name__)

    paths = Paths.from_env()
    if args.output_dir:
        paths = Paths(
            manifest_dir=paths.manifest_dir,
            audio_dir=paths.audio_dir,
            output_dir=Path(args.output_dir),
        )

    logger.info("Model: %s", args.model)
    logger.info("Window sizes: %s", args.window_size)
    logger.info("Segments per meeting: %d", args.segments_per_meeting)
    logger.info("Collar: %fs", args.collar)
    logger.info("Speaker count mode: %s", args.speaker_count_mode)
    pipeline_params = None
    if args.pipeline_params:
        try:
            pipeline_params = json.loads(args.pipeline_params)
        except json.JSONDecodeError as e:
            raise SystemExit(f"Invalid --pipeline-params JSON: {e}") from e
        if not isinstance(pipeline_params, dict):
            raise SystemExit("--pipeline-params must decode to a JSON object")
        logger.info("Pipeline params: %s", pipeline_params)

    model = get_model(args.model, pipeline_params=pipeline_params)
    runner = ExperimentRunner(
        model=model,
        paths=paths,
        window_sizes=args.window_size,
        segments_per_meeting=args.segments_per_meeting,
        collar=args.collar,
        prompt_variant=args.prompt_variant,
        max_segments=args.max_segments,
        sampling_mode=args.sampling_mode,
        total_samples=args.total_samples,
        seed=args.seed,
        speaker_count_mode=args.speaker_count_mode,
        min_speakers=args.min_speakers,
        max_speakers=args.max_speakers,
        segments_manifest=args.segments_manifest,
        results_name=args.results_name,
        force_reprocess=args.force_reprocess,
    )

    summary = runner.run()

    # Save summary
    output_dir = runner.get_output_dir()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / args.summary_name
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # Print summary
    print("\n" + "=" * 60)
    print("  Experiment: %s" % summary["model_name"])
    print(
        "  Segments: %d/%d succeeded"
        % (summary["successful"], summary["total_segments"])
    )
    if summary["successful"] > 0:
        print("  DER: %.2f%%" % (summary["avg_der"] * 100))
        print("    Miss: %.2f%%" % (summary["avg_miss_rate"] * 100))
        print("    FA:   %.2f%%" % (summary["avg_fa_rate"] * 100))
        print("    Conf: %.2f%%" % (summary["avg_conf_rate"] * 100))
        if summary.get("avg_cer") is not None:
            print("  CER: %.2f%%" % (summary["avg_cer"] * 100))
        print("  Spk Match: %.1f%%" % (summary["spk_match_rate"] * 100))
        print("  Avg Latency: %.1fs" % summary["avg_latency"])
    print("=" * 60)

    logger.info("Summary saved to %s", summary_path)


if __name__ == "__main__":
    main()
