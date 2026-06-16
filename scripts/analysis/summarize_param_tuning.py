#!/usr/bin/env python
"""Summarize parameter tuning summaries under an output directory."""

# Keep categorized scripts import-compatible when executed by file path.
import sys as _sys
from pathlib import Path as _Path
_SCRIPT_ROOT = _Path(__file__).resolve().parents[1]
_REPO_ROOT = _SCRIPT_ROOT.parent
for _candidate in [_REPO_ROOT, _SCRIPT_ROOT, *_SCRIPT_ROOT.iterdir()]:
    if _candidate.is_dir():
        _value = str(_candidate)
        if _value not in _sys.path:
            _sys.path.insert(0, _value)

import json
import sys
from pathlib import Path


def main() -> None:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("outputs/param_tuning")
    rows = []
    for path in sorted(root.glob("*/*/summary.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "path": str(path.parent),
                "model": summary.get("model_name"),
                "mode": summary.get("speaker_count_mode"),
                "params": json.dumps(
                    summary.get("pipeline_params", {}),
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                "der": summary.get("avg_der"),
                "miss": summary.get("avg_miss_rate"),
                "fa": summary.get("avg_fa_rate"),
                "conf": summary.get("avg_conf_rate"),
                "spk_match": summary.get("spk_match_rate"),
                "latency": summary.get("avg_latency"),
            }
        )

    rows = [row for row in rows if row["der"] is not None]
    rows.sort(key=lambda row: row["der"])

    print("model,mode,der,miss,fa,conf,spk_match,latency,params,path")
    for row in rows:
        print(
            "{model},{mode},{der:.4f},{miss:.4f},{fa:.4f},{conf:.4f},"
            "{spk_match:.4f},{latency:.2f},{params},{path}".format(**row)
        )


if __name__ == "__main__":
    main()
