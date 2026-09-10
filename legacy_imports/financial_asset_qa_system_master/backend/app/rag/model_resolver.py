"""Resolve local HuggingFace snapshot paths for offline model loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Optional


def configure_offline_model_env() -> None:
    """Force Transformers/HF Hub to operate in offline mode."""

    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    os.environ.setdefault("HF_DATASETS_OFFLINE", "1")


def resolve_local_snapshot(model_name: str) -> Optional[str]:
    """Resolve a cached HuggingFace snapshot directory for a repo id."""

    repo_folder = f"models--{model_name.replace('/', '--')}"
    for root in _candidate_cache_roots():
        model_root = root / repo_folder
        if not model_root.exists():
            continue

        ref_path = model_root / "refs" / "main"
        if ref_path.exists():
            try:
                ref_name = ref_path.read_text(encoding="utf-8").strip()
                snapshot_dir = model_root / "snapshots" / ref_name
                if snapshot_dir.exists():
                    return str(snapshot_dir)
            except Exception:
                pass

        snapshots_dir = model_root / "snapshots"
        if not snapshots_dir.exists():
            continue

        snapshots = sorted(
            (path for path in snapshots_dir.iterdir() if path.is_dir()),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if snapshots:
            return str(snapshots[0])

    return None


def _candidate_cache_roots() -> Iterable[Path]:
    seen = set()

    env_values = [
        os.environ.get("HF_HOME"),
        os.environ.get("TRANSFORMERS_CACHE"),
        os.environ.get("HUGGINGFACE_HUB_CACHE"),
    ]
    for value in env_values:
        if not value:
            continue
        base = Path(value)
        candidates = [base / "hub", base]
        for candidate in candidates:
            if candidate.exists() and candidate not in seen:
                seen.add(candidate)
                yield candidate

    defaults = [
        Path("D:/HuggingFace_Cache/hub"),
        Path.home() / ".cache" / "huggingface" / "hub",
        Path.home() / ".cache" / "torch" / "sentence_transformers",
    ]
    for candidate in defaults:
        if candidate.exists() and candidate not in seen:
            seen.add(candidate)
            yield candidate
