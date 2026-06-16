"""
Core experiment runner for AliMeeting diarization benchmark.

Orchestrates the full benchmark pipeline:
- Load data and generate segments
- Iterate over segments with checkpointing
- Slice audio → call model → compute metrics
- Save checkpoints and produce summary
"""

import csv
import inspect
import logging
import os
import time
from dataclasses import dataclass, asdict
from dataclasses import field
from pathlib import Path
from typing import List, Dict, Optional

from ..config import Paths, APIKeys
from ..data.manifests import (
    load_manifests,
    generate_segments,
    generate_stratified_segments,
)
from ..data.audio import slice_and_save_temp
from ..data.ground_truth import build_gt_der_segments, build_gt_text
from ..metrics.der import calc_der
from ..metrics.cer import calc_cer
from ..utils.checkpoint import load_checkpoint, save_checkpoint, checkpoint_key
from ..models.base import BaseModel, DiarizationResult
from ..models import (
    FunASRModel,
    ParaformerV2Model,
    OmniPlusModel,
    ASRFlashModel,
    GPT4oAudioModel,
    PyAnnoteModel,
    PyAnnoteCommunityModel,
    DiariZenModel,
    SortformerModel,
)

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """Result for a single segment evaluation."""

    key: str  # checkpoint key
    recording_id: str
    window_size: int
    segment_idx: int
    model_name: str
    success: bool
    der: Optional[float] = None
    miss_rate: Optional[float] = None
    fa_rate: Optional[float] = None
    conf_rate: Optional[float] = None
    cer: Optional[float] = None
    latency: float = 0.0
    spk_count_pred: int = 0
    spk_count_gt: int = 0
    speaker_count_hint: Optional[int] = None
    spk_match: bool = False
    pred_segments: List[Dict] = field(default_factory=list)
    gt_segments: List[Dict] = field(default_factory=list)
    pred_text: str = ""
    gt_text: str = ""
    error: Optional[str] = None


# Model factory registry
MODEL_REGISTRY = {
    "fun_asr": FunASRModel,
    "paraformer_v2": ParaformerV2Model,
    "omni_plus": OmniPlusModel,
    "asr_flash": ASRFlashModel,
    "gpt4o_audio": GPT4oAudioModel,
    "pyannote": PyAnnoteModel,
    "pyannote_community": PyAnnoteCommunityModel,
    "diarizen": DiariZenModel,
    "sortformer": SortformerModel,
}


def get_model(name: str, **kwargs) -> BaseModel:
    """
    Get model instance by name.

    Args:
        name: Model name (must be in MODEL_REGISTRY)
        **kwargs: Arguments passed to model constructor

    Returns:
        BaseModel instance

    Raises:
        ValueError: If model name is not registered
    """
    cls = MODEL_REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            "Unknown model: %s. Available: %s",
            name,
            list(MODEL_REGISTRY.keys()),
        )
    if kwargs:
        signature = inspect.signature(cls)
        kwargs = {
            key: value
            for key, value in kwargs.items()
            if key in signature.parameters and value is not None
        }
    return cls(**kwargs)


class ExperimentRunner:
    """
    Orchestrates the full benchmark pipeline.

    - Loads manifests and generates segments
    - Iterates over segments, skipping completed ones (checkpoint)
    - For each segment: slices audio → calls model → computes metrics → saves checkpoint
    - Produces summary with averages
    - Supports resumability via checkpoint
    """

    def __init__(
        self,
        model: BaseModel,
        paths: Optional[Paths] = None,
        api_keys: Optional[APIKeys] = None,
        window_sizes: List[int] = None,
        segments_per_meeting: int = 3,
        collar: float = 0.0,
        prompt_variant: str = "default",
        max_segments: Optional[int] = None,
        sampling_mode: str = "uniform",
        total_samples: int = 120,
        seed: int = 42,
        speaker_count_mode: str = "oracle",
        min_speakers: int = 1,
        max_speakers: int = 8,
        segments_manifest: Optional[Path] = None,
        results_name: str = "results.csv",
        force_reprocess: bool = False,
    ):
        """
        Initialize the experiment runner.

        Args:
            model: BaseModel instance to evaluate
            paths: Path configuration (uses env defaults if None)
            api_keys: API key configuration (uses env defaults if None)
            window_sizes: List of window sizes to test (default: [30])
            segments_per_meeting: Number of segments per recording (default: 3)
            collar: Collar in seconds for DER calculation (default: 0.0)
            prompt_variant: Prompt variant for model (default: "default")
            max_segments: Limit total segments for testing (default: None = all)
            sampling_mode: Sampling strategy - "uniform" or "stratified" (default: "uniform")
            total_samples: Total samples for stratified mode (default: 120)
            seed: Random seed for stratified sampling (default: 42)
            speaker_count_mode: Speaker count hint strategy - "oracle", "none", "bounds", or "hint"
            min_speakers: Lower bound used when speaker_count_mode="bounds"
            max_speakers: Upper bound used when speaker_count_mode="bounds"
        """
        self.model = model
        self.paths = paths or Paths.from_env()
        self.api_keys = api_keys or APIKeys.from_env()
        self.window_sizes = window_sizes or [30]
        self.segments_per_meeting = segments_per_meeting
        self.collar = collar
        self.prompt_variant = prompt_variant
        self.max_segments = max_segments
        self.sampling_mode = sampling_mode
        self.total_samples = total_samples
        self.seed = seed
        self.speaker_count_mode = speaker_count_mode
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self.segments_manifest = Path(segments_manifest) if segments_manifest else None
        self.results_name = results_name
        self.force_reprocess = force_reprocess

        if self.speaker_count_mode not in {"oracle", "none", "bounds", "hint"}:
            raise ValueError(
                "speaker_count_mode must be one of: oracle, none, bounds, hint"
            )

        logger.info(
            "ExperimentRunner initialized: model=%s, window_sizes=%s, collar=%s, sampling_mode=%s, speaker_count_mode=%s",
            self.model.name,
            self.window_sizes,
            self.collar,
            self.sampling_mode,
            self.speaker_count_mode,
        )

    def run(self) -> Dict:
        """
        Run the full experiment.

        Returns:
            Dict with summary statistics and all results
        """
        logger.info("Starting experiment run...")

        # Step 1: Load manifests
        recordings, supervisions = load_manifests(self.paths.manifest_dir)

        # Step 2: Generate segments based on sampling mode or explicit manifest
        if self.segments_manifest is not None:
            segments = self._load_segments_manifest(self.segments_manifest, recordings)
        elif self.sampling_mode == "stratified":
            # Use stratified sampling with fixed window size
            segments = generate_stratified_segments(
                recordings,
                supervisions,
                window_size=self.window_sizes[0] if self.window_sizes else 30,
                total_samples=self.total_samples,
                seed=self.seed,
            )
        else:
            # Use uniform sampling (existing behavior)
            segments = generate_segments(
                recordings,
                self.window_sizes,
                self.segments_per_meeting,
            )

        # Step 3: Limit segments if specified
        if self.max_segments is not None:
            segments = segments[: self.max_segments]
            logger.info("Limited to %d segments", len(segments))

        total_segments = len(segments)
        logger.info("Total segments to process: %d", total_segments)

        # Step 4: Load checkpoint
        model_output_dir = self.get_output_dir()
        checkpoint_data = load_checkpoint(model_output_dir)
        skipped = sum(
            1
            for seg in segments
            if not self.force_reprocess
            and checkpoint_key(
                seg["recording_id"],
                seg["window_size"],
                seg["segment_idx"],
                self.model.name,
                self._checkpoint_variant(),
            )
            in checkpoint_data
        )
        logger.info("Skipped %d completed segments from checkpoint", skipped)

        # Step 5: Iterate and process segments
        results: List[ExperimentResult] = []

        for i, seg in enumerate(segments):
            rec_id = seg["recording_id"]
            ws = seg["window_size"]
            seg_idx = seg["segment_idx"]

            # Check if already completed
            key = checkpoint_key(
                rec_id,
                ws,
                seg_idx,
                self.model.name,
                self._checkpoint_variant(),
            )

            if key in checkpoint_data and not self.force_reprocess:
                logger.debug("Skipping completed: %s", key)
                # Load from checkpoint
                cp_entry = checkpoint_data[key]
                result = ExperimentResult(**cp_entry)
                results.append(result)
                continue

            # Process segment
            logger.info(
                "[%d/%d] %s ws=%d seg=%d -processing...",
                i + 1,
                total_segments,
                rec_id,
                ws,
                seg_idx,
            )

            result = self._process_segment(seg, supervisions)
            results.append(result)

            # Save checkpoint
            checkpoint_data[key] = asdict(result)
            save_checkpoint(model_output_dir, checkpoint_data)

            # Log progress
            if result.success:
                logger.info(
                    "[%d/%d] %s ws=%d seg=%d DER=%.1f%% latency=%.1fs",
                    i + 1,
                    total_segments,
                    rec_id,
                    ws,
                    seg_idx,
                    result.der * 100 if result.der else 0,
                    result.latency,
                )
            else:
                logger.warning(
                    "[%d/%d] %s ws=%d seg=%d FAILED: %s",
                    i + 1,
                    total_segments,
                    rec_id,
                    ws,
                    seg_idx,
                    result.error,
                )

        # Step 6: Summarize
        summary = self._summarize(results)
        logger.info("Experiment complete: %s", summary["summary_line"])

        # Step 7: Export results to CSV
        self._export_csv(results, model_output_dir / self.results_name)
        logger.info("Results exported to %s", model_output_dir / self.results_name)

        return summary

    def _load_segments_manifest(self, path: Path, recordings: List[Dict]) -> List[Dict]:
        """
        Load an explicit segment manifest.

        Required columns: recording_id, window_size, segment_idx, offset, duration.
        Optional columns: audio_path, spk_count_gt, speaker_count_hint, or
        spk_count_hint. If audio_path is omitted, it is resolved from the
        AliMeeting recording manifest.
        """
        if not path.exists():
            raise FileNotFoundError(f"segments manifest not found: {path}")

        audio_by_recording = {
            str(recording["id"]): recording["sources"][0]["source"]
            for recording in recordings
            if recording.get("sources")
        }
        required = {"recording_id", "window_size", "segment_idx", "offset", "duration"}
        segments: List[Dict] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = sorted(required - set(reader.fieldnames or []))
            if missing:
                raise ValueError(f"segments manifest missing required columns: {missing}")
            for row_idx, row in enumerate(reader, start=2):
                rec_id = str(row["recording_id"])
                audio_path = row.get("audio_path") or audio_by_recording.get(rec_id)
                if not audio_path:
                    raise ValueError(f"row {row_idx}: audio_path missing and recording_id cannot be resolved: {rec_id}")
                segment = {
                    "recording_id": rec_id,
                    "audio_path": audio_path,
                    "window_size": int(float(row["window_size"])),
                    "segment_idx": int(float(row["segment_idx"])),
                    "offset": float(row["offset"]),
                    "duration": float(row["duration"]),
                }
                if row.get("spk_count_gt") not in (None, ""):
                    segment["spk_count_gt"] = int(float(row["spk_count_gt"]))
                speaker_count_hint = row.get("speaker_count_hint") or row.get(
                    "spk_count_hint"
                )
                if speaker_count_hint not in (None, ""):
                    segment["speaker_count_hint"] = int(float(speaker_count_hint))
                segments.append(segment)
        logger.info("Loaded %d explicit segments from %s", len(segments), path)
        return segments

    def get_output_dir(self) -> Path:
        return self.paths.output_dir / self.model.name / self._checkpoint_variant()

    def _checkpoint_variant(self) -> str:
        parts = [self.prompt_variant or "default", f"spk_{self.speaker_count_mode}"]
        if self.speaker_count_mode == "bounds":
            parts.append(f"{self.min_speakers}-{self.max_speakers}")
        if getattr(self.model, "params_tag", ""):
            parts.append(self.model.params_tag)
        return "__".join(parts)

    def _build_predict_kwargs(
        self,
        spk_count_gt: int,
        gt_text: str,
        speaker_count_hint: Optional[int] = None,
    ) -> Dict:
        kwargs = {
            "speaker_count": None,
            "prompt_variant": self.prompt_variant,
            "transcript_reference": gt_text,
        }

        if self.speaker_count_mode == "oracle":
            kwargs["speaker_count"] = spk_count_gt
            return kwargs

        if self.speaker_count_mode == "hint":
            if speaker_count_hint and speaker_count_hint > 0:
                kwargs["speaker_count"] = speaker_count_hint
            return kwargs

        if self.speaker_count_mode == "bounds" and getattr(
            self.model, "supports_speaker_bounds", False
        ):
            kwargs["speaker_count_min"] = self.min_speakers
            kwargs["speaker_count_max"] = self.max_speakers

        return kwargs

    def _process_segment(
        self,
        seg: Dict,
        supervisions: Dict[str, List[Dict]],
    ) -> ExperimentResult:
        """
        Process a single segment.

        Args:
            seg: Segment dict with recording_id, audio_path, offset, duration, etc.
            supervisions: Dict mapping recording_id to list of supervision dicts

        Returns:
            ExperimentResult with all metrics populated
        """
        rec_id = seg["recording_id"]
        ws = seg["window_size"]
        seg_idx = seg["segment_idx"]
        audio_path = seg["audio_path"]
        offset = seg["offset"]
        duration = seg["duration"]

        # Compute checkpoint key
        key = checkpoint_key(
            rec_id,
            ws,
            seg_idx,
            self.model.name,
            self._checkpoint_variant(),
        )

        temp_audio_path = None
        start_time = time.time()

        try:
            # Slice audio
            temp_audio_path = slice_and_save_temp(audio_path, offset, duration)
            logger.debug("Sliced audio to temp file: %s", temp_audio_path)

            # Get GT supervisions for this recording
            sups = supervisions.get(rec_id, [])
            if not sups:
                return ExperimentResult(
                    key=key,
                    recording_id=rec_id,
                    window_size=ws,
                    segment_idx=seg_idx,
                    model_name=self.model.name,
                    success=False,
                    error="No ground truth supervisions found",
                )

            # Build GT DER segments
            gt_der_segments = build_gt_der_segments(sups, offset, duration)

            # Build GT text
            gt_text = build_gt_text(sups, offset, duration)

            # Get speaker count from GT
            spk_count_gt = len(set(s["speaker"] for s in gt_der_segments))

            # Call model.predict()
            speaker_count_hint = seg.get("speaker_count_hint")
            predict_kwargs = self._build_predict_kwargs(
                spk_count_gt,
                gt_text,
                speaker_count_hint=speaker_count_hint,
            )
            result = self.model.predict(temp_audio_path, **predict_kwargs)

            latency = time.time() - start_time

            if not result.success:
                return ExperimentResult(
                    key=key,
                    recording_id=rec_id,
                    window_size=ws,
                    segment_idx=seg_idx,
                    model_name=self.model.name,
                    success=False,
                    latency=latency,
                spk_count_gt=spk_count_gt,
                speaker_count_hint=speaker_count_hint,
                spk_count_pred=result.spk_count,
                gt_segments=gt_der_segments,
                gt_text=gt_text,
                error=result.error,
            )

            # Convert result.segments to DER format
            pred_der_segments = self.model.segments_to_der_format(result)

            # Calculate DER
            der_result = calc_der(
                gt_der_segments,
                pred_der_segments,
                session_id=rec_id,
                collar=self.collar,
            )

            # Calculate CER
            cer_result = calc_cer(gt_text, result.text)

            # Check speaker match
            spk_match = result.spk_count == spk_count_gt

            return ExperimentResult(
                key=key,
                recording_id=rec_id,
                window_size=ws,
                segment_idx=seg_idx,
                model_name=self.model.name,
                success=True,
                der=der_result["der"] if der_result else None,
                miss_rate=der_result["miss_rate"] if der_result else None,
                fa_rate=der_result["fa_rate"] if der_result else None,
                conf_rate=der_result["conf_rate"] if der_result else None,
                cer=cer_result["wer"] if cer_result else None,
                latency=latency,
                spk_count_pred=result.spk_count,
                spk_count_gt=spk_count_gt,
                speaker_count_hint=speaker_count_hint,
                spk_match=spk_match,
                pred_segments=pred_der_segments,
                gt_segments=gt_der_segments,
                pred_text=result.text,
                gt_text=gt_text,
            )

        except Exception as e:
            latency = time.time() - start_time
            logger.exception("Error processing segment %s", key)
            return ExperimentResult(
                key=key,
                recording_id=rec_id,
                window_size=ws,
                segment_idx=seg_idx,
                model_name=self.model.name,
                success=False,
                latency=latency,
                error=str(e),
            )

        finally:
            # Clean up temp audio file
            if temp_audio_path and os.path.exists(temp_audio_path):
                try:
                    os.remove(temp_audio_path)
                    logger.debug("Cleaned up temp file: %s", temp_audio_path)
                except Exception as e:
                    logger.warning(
                        "Failed to clean up temp file %s: %s", temp_audio_path, e
                    )

    def _summarize(self, results: List[ExperimentResult]) -> Dict:
        """
        Compute aggregate statistics.

        Args:
            results: List of ExperimentResult objects

        Returns:
            Dict with summary statistics
        """
        if not results:
            return {
                "model_name": self.model.name,
                "pipeline_params": getattr(self.model, "pipeline_params", {}),
                "speaker_count_mode": self.speaker_count_mode,
                "min_speakers": self.min_speakers,
                "max_speakers": self.max_speakers,
                "sampling_mode": self.sampling_mode,
                "segments_manifest": str(self.segments_manifest) if self.segments_manifest else None,
                "results_name": self.results_name,
                "force_reprocess": self.force_reprocess,
                "total_segments": 0,
                "successful": 0,
                "failed": 0,
                "avg_der": None,
                "avg_miss_rate": None,
                "avg_fa_rate": None,
                "avg_conf_rate": None,
                "avg_cer": None,
                "avg_latency": None,
                "spk_match_rate": None,
                "results": [],
                "summary_line": "No results to summarize",
            }

        successful_results = [r for r in results if r.success]
        failed_results = [r for r in results if not r.success]

        # Calculate averages for successful results
        def avg(values: List[float]) -> Optional[float]:
            if not values:
                return None
            return sum(values) / len(values)

        der_values = [r.der for r in successful_results if r.der is not None]
        miss_rate_values = [
            r.miss_rate for r in successful_results if r.miss_rate is not None
        ]
        fa_rate_values = [
            r.fa_rate for r in successful_results if r.fa_rate is not None
        ]
        conf_rate_values = [
            r.conf_rate for r in successful_results if r.conf_rate is not None
        ]
        cer_values = [r.cer for r in successful_results if r.cer is not None]
        latency_values = [r.latency for r in successful_results]
        spk_match_values = [r.spk_match for r in successful_results]

        summary = {
            "model_name": self.model.name,
            "pipeline_params": getattr(self.model, "pipeline_params", {}),
            "speaker_count_mode": self.speaker_count_mode,
            "min_speakers": self.min_speakers,
            "max_speakers": self.max_speakers,
            "sampling_mode": self.sampling_mode,
            "segments_manifest": str(self.segments_manifest) if self.segments_manifest else None,
            "results_name": self.results_name,
            "force_reprocess": self.force_reprocess,
            "total_segments": len(results),
            "successful": len(successful_results),
            "failed": len(failed_results),
            "avg_der": round(avg(der_values), 4) if der_values else None,
            "avg_miss_rate": round(avg(miss_rate_values), 4)
            if miss_rate_values
            else None,
            "avg_fa_rate": round(avg(fa_rate_values), 4) if fa_rate_values else None,
            "avg_conf_rate": round(avg(conf_rate_values), 4)
            if conf_rate_values
            else None,
            "avg_cer": round(avg(cer_values), 4) if cer_values else None,
            "avg_latency": round(avg(latency_values), 2) if latency_values else None,
            "spk_match_rate": round(avg(spk_match_values), 4)
            if spk_match_values
            else None,
            "results": [asdict(r) for r in results],
        }

        # Create summary line
        summary["summary_line"] = (
            "Model %s: %d/%d successful, "
            "avg DER=%.1f%%, avg CER=%.1f%%, "
            "spk_match=%.1f%%, avg latency=%.1fs"
        ) % (
            self.model.name,
            len(successful_results),
            len(results),
            (summary["avg_der"] or 0) * 100,
            (summary["avg_cer"] or 0) * 100,
            (summary["spk_match_rate"] or 0) * 100,
            summary["avg_latency"] or 0,
        )

        logger.info(
            "Summary: %d segments, %d successful, %d failed, avg DER=%.1f%%, avg CER=%.1f%%",
            len(results),
            len(successful_results),
            len(failed_results),
            (summary["avg_der"] or 0) * 100,
            (summary["avg_cer"] or 0) * 100,
        )

        return summary

    def _export_csv(self, results: List[ExperimentResult], csv_path: Path) -> None:
        """
        Export results to CSV file.

        Args:
            results: List of ExperimentResult objects
            csv_path: Path to write CSV results
        """
        csv_path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "recording_id",
            "window_size",
            "segment_idx",
            "model_name",
            "success",
            "der",
            "miss_rate",
            "fa_rate",
            "conf_rate",
            "cer",
            "latency",
            "spk_count_pred",
            "spk_count_gt",
            "speaker_count_hint",
            "spk_match",
            "error",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                row = {
                    "recording_id": result.recording_id,
                    "window_size": result.window_size,
                    "segment_idx": result.segment_idx,
                    "model_name": result.model_name,
                    "success": result.success,
                    "der": result.der,
                    "miss_rate": result.miss_rate,
                    "fa_rate": result.fa_rate,
                    "conf_rate": result.conf_rate,
                    "cer": result.cer,
                    "latency": result.latency,
                    "spk_count_pred": result.spk_count_pred,
                    "spk_count_gt": result.spk_count_gt,
                    "speaker_count_hint": result.speaker_count_hint,
                    "spk_match": result.spk_match,
                    "error": result.error,
                }
                writer.writerow(row)

        logger.info(
            "CSV export complete: %d rows written to %s", len(results), csv_path
        )
