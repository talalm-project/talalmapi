import json
from pathlib import Path
from threading import Lock


class CachedLlamaModel:
    def __init__(self, llm):
        self.llm = llm
        self.lock = Lock()


class LlamaModelCache:
    def __init__(self):
        self._models = {}
        self._lock = Lock()

    def get(self, llama_class, model_path, model_options):
        key = self._cache_key(llama_class, model_path, model_options)
        cached = self._models.get(key)
        if cached is not None:
            return cached

        with self._lock:
            cached = self._models.get(key)
            if cached is not None:
                return cached

            llm = llama_class(model_path=model_path, **model_options)
            cached = CachedLlamaModel(llm)
            self._models[key] = cached
            return cached

    def clear(self):
        with self._lock:
            self._models.clear()

    def _cache_key(self, llama_class, model_path, model_options):
        normalized_path = str(Path(model_path).expanduser().resolve(strict=False))
        normalized_options = json.dumps(model_options, sort_keys=True, default=str)
        return (llama_class, normalized_path, normalized_options)


llama_model_cache = LlamaModelCache()
