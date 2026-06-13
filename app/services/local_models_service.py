from pathlib import Path

import yaml

from app.operations.connectors.metadata import (
    DEFAULT_LLAMA_CPP_CONTEXT_WINDOW_TOKENS,
    DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS,
    _local_model_context_window,
)


ALLOWED_LOCAL_MODEL_TYPES = {"inference", "embedding", "embeddings"}


class LocalModelsService:
    def __init__(self, manifest_path):
        self.manifest_path = Path(manifest_path)

    def list(self):
        if not self.manifest_path.exists():
            return []

        with self.manifest_path.open("r", encoding="utf-8") as handle:
            records = yaml.safe_load(handle) or []

        if not isinstance(records, list):
            return []

        return [self._record_payload(record) for record in records if isinstance(record, dict)]

    def _record_payload(self, record):
        model_type = record.get("type") if record.get("type") in ALLOWED_LOCAL_MODEL_TYPES else None
        payload = {
            "name": record.get("name"),
            "type": model_type,
            "path": record.get("path"),
            "context_window_min": None,
            "context_window_max": None,
            "context_window_recommended": None,
        }

        if model_type == "inference":
            context_window = self._context_window_for_path(record.get("path"))
            max_context_window = context_window or DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS
            recommended = min(max_context_window, DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS)
            payload.update(
                {
                    "context_window_min": DEFAULT_LLAMA_CPP_CONTEXT_WINDOW_TOKENS,
                    "context_window_max": max_context_window,
                    "context_window_recommended": recommended,
                }
            )

        return payload

    def _context_window_for_path(self, model_path):
        if not model_path:
            return None

        path = Path(model_path)
        candidates = [path]
        if not path.is_absolute():
            candidates.append(self.manifest_path.parent / path)

        for candidate in candidates:
            context_window = _local_model_context_window(candidate)
            if context_window:
                return context_window

        return None
