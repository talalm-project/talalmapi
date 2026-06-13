import os
from pathlib import Path
from struct import unpack_from


DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS = 4096
DEFAULT_LLAMA_CPP_CONTEXT_WINDOW_TOKENS = 512
DEFAULT_LOCAL_EMBEDDING_CONTEXT_WINDOW_TOKENS = 65536
DEFAULT_LOCAL_EMBEDDING_BATCH_TOKENS = 512
DEFAULT_LOCAL_EMBEDDING_SEQUENCES = 256
DEFAULT_LOCAL_OUTPUT_TOKENS = 1024
DEFAULT_LOCAL_BATCH_TOKENS = 1024
DEFAULT_LOCAL_NO_PERF = True
DEFAULT_LOCAL_VERBOSE = False
DEFAULT_EMBEDDING_CHARS_PER_TOKEN = 4
DEFAULT_EMBEDDING_CHUNK_RATIO = 0.75
DEFAULT_EMBEDDING_CHUNK_OVERLAP_RATIO = 0.1
GGUF_TYPE_UINT8 = 0
GGUF_TYPE_INT8 = 1
GGUF_TYPE_UINT16 = 2
GGUF_TYPE_INT16 = 3
GGUF_TYPE_UINT32 = 4
GGUF_TYPE_INT32 = 5
GGUF_TYPE_FLOAT32 = 6
GGUF_TYPE_BOOL = 7
GGUF_TYPE_STRING = 8
GGUF_TYPE_ARRAY = 9
GGUF_TYPE_UINT64 = 10
GGUF_TYPE_INT64 = 11
GGUF_TYPE_FLOAT64 = 12
GGUF_SCALAR_SIZES = {
    GGUF_TYPE_UINT8: 1,
    GGUF_TYPE_INT8: 1,
    GGUF_TYPE_UINT16: 2,
    GGUF_TYPE_INT16: 2,
    GGUF_TYPE_UINT32: 4,
    GGUF_TYPE_INT32: 4,
    GGUF_TYPE_FLOAT32: 4,
    GGUF_TYPE_BOOL: 1,
    GGUF_TYPE_UINT64: 8,
    GGUF_TYPE_INT64: 8,
    GGUF_TYPE_FLOAT64: 8,
}


def build_connector_data(connector_attrs, data=None):
    normalized_data = dict(data or {})
    normalized_data["metadata"] = build_connector_metadata(connector_attrs, normalized_data)
    return normalized_data


def build_connector_metadata(connector_attrs, data=None):
    data = data or {}

    return {
        "schema_version": 1,
        "provider": "local",
        "inference": _inference_metadata(connector_attrs, data),
        "embeddings": _embeddings_metadata(connector_attrs, data),
    }


def inference_model_options(connector):
    connector_data = _data(connector)
    metadata_options = _section_value(connector, "inference", "model_options")
    if isinstance(metadata_options, dict):
        top_level_options = connector_data.get("model_options", {})
        top_level_options = top_level_options if isinstance(top_level_options, dict) else {}
        metadata_options = _with_runtime_context_override(metadata_options, top_level_options)
        return _with_local_inference_context(connector, metadata_options)

    options = connector_data.get("model_options", {})
    options = options if isinstance(options, dict) else {}
    return _with_local_inference_context(connector, options)


def inference_context_window_tokens(connector):
    value = _section_value(connector, "inference", "limits", "context_window_tokens")
    if isinstance(value, int) and value > 0:
        return value

    value = inference_model_options(connector).get("n_ctx")
    if isinstance(value, int) and value > 0:
        return value

    return _local_inference_context_window(_get_value(connector, "local_file_path"), {}) or DEFAULT_LLAMA_CPP_CONTEXT_WINDOW_TOKENS


def inference_model_name(connector):
    return _model_value(connector, "inference", "name") or _get_value(connector, "name")


def inference_local_file_path(connector):
    return _model_value(connector, "inference", "local_file_path") or _get_value(connector, "local_file_path")


def embedding_model_options(connector):
    metadata_options = _section_value(connector, "embeddings", "model_options")
    if isinstance(metadata_options, dict):
        return metadata_options

    options = _data(connector).get("embedding_model_options", {})
    return options if isinstance(options, dict) else {}


def embedding_model_name(connector):
    return _model_value(connector, "embeddings", "name") or _get_value(connector, "embedding_name")


def embedding_local_file_path(connector):
    return _model_value(connector, "embeddings", "local_file_path") or _get_value(connector, "embedding_local_file_path")


def embedding_size(connector):
    value = _model_value(connector, "embeddings", "embedding_size")
    return value if isinstance(value, int) and value > 0 else None


def inference_default_output_tokens(connector, fallback=DEFAULT_LOCAL_OUTPUT_TOKENS):
    value = _section_value(connector, "inference", "limits", "default_output_tokens")
    return value if isinstance(value, int) and value > 0 else fallback


def embedding_chunk_options(connector, default_chunk_size, default_chunk_overlap):
    chunking = _section_value(connector, "embeddings", "chunking")
    if not isinstance(chunking, dict):
        return default_chunk_size, default_chunk_overlap

    chunk_size = chunking.get("chunk_size")
    chunk_overlap = chunking.get("chunk_overlap")
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        chunk_size = default_chunk_size
    if not isinstance(chunk_overlap, int) or chunk_overlap < 0 or chunk_overlap >= chunk_size:
        chunk_overlap = default_chunk_overlap

    return chunk_size, chunk_overlap


def embedding_max_input_tokens(connector):
    value = _section_value(connector, "embeddings", "limits", "max_input_tokens")
    return value if isinstance(value, int) and value > 0 else None


def _inference_metadata(connector_attrs, data):
    model_options = _dict_value(data.get("model_options"))

    context_window_tokens = _local_inference_context_window(_get_value(connector_attrs, "local_file_path"), model_options)
    model_options = {**model_options, "n_ctx": context_window_tokens}
    model = {
        "name": _get_value(connector_attrs, "name"),
        "local_file_path": _get_value(connector_attrs, "local_file_path"),
    }

    return {
        "model": model,
        "model_options": model_options,
        "limits": {
            "context_window_tokens": context_window_tokens,
            "max_input_tokens": context_window_tokens,
            "default_output_tokens": DEFAULT_LOCAL_OUTPUT_TOKENS,
        },
    }


def _embeddings_metadata(connector_attrs, data):
    model_options = _dict_value(data.get("embedding_model_options"))
    return _local_embeddings_metadata(connector_attrs, model_options)


def _local_embeddings_metadata(connector_attrs, model_options):
    context_window_tokens = (
        _positive_int(model_options.get("n_ctx"))
        or _positive_int(model_options.get("context_window_tokens"))
        or DEFAULT_LOCAL_EMBEDDING_CONTEXT_WINDOW_TOKENS
    )
    batch_tokens = _positive_int(model_options.get("n_batch")) or DEFAULT_LOCAL_EMBEDDING_BATCH_TOKENS
    sequence_count = _positive_int(model_options.get("n_seq_max")) or DEFAULT_LOCAL_EMBEDDING_SEQUENCES
    sequence_tokens = max(context_window_tokens // sequence_count, 1)
    max_input_tokens = min(context_window_tokens, batch_tokens, sequence_tokens)

    return {
        "model": {
            "name": _get_value(connector_attrs, "embedding_name"),
            "local_file_path": _get_value(connector_attrs, "embedding_local_file_path"),
            "embedding_size": _local_embedding_size(_get_value(connector_attrs, "embedding_local_file_path")),
        },
        "model_options": model_options,
        "limits": _embedding_limits(context_window_tokens, max_input_tokens),
        "chunking": _embedding_chunking(max_input_tokens),
    }


def _embedding_limits(context_window_tokens, max_input_tokens):
    max_content_tokens = max(max_input_tokens - 1, 1)
    ideal_chunk_tokens = max(int(max_content_tokens * DEFAULT_EMBEDDING_CHUNK_RATIO), 1)
    return {
        "context_window_tokens": context_window_tokens,
        "max_input_tokens": max_input_tokens,
        "max_content_tokens": max_content_tokens,
        "ideal_chunk_tokens": ideal_chunk_tokens,
    }


def _embedding_chunking(max_input_tokens):
    max_content_tokens = max(max_input_tokens - 1, 1)
    ideal_chunk_tokens = max(int(max_content_tokens * DEFAULT_EMBEDDING_CHUNK_RATIO), 1)
    chunk_size = max(ideal_chunk_tokens * DEFAULT_EMBEDDING_CHARS_PER_TOKEN, 1)
    chunk_overlap = max(int(chunk_size * DEFAULT_EMBEDDING_CHUNK_OVERLAP_RATIO), 0)
    return {
        "strategy": "text-with-token-safety",
        "unit": "characters",
        "chunk_size": chunk_size,
        "chunk_overlap": chunk_overlap,
    }


def _section_value(connector, section, *keys):
    metadata = _data(connector).get("metadata", {})
    if not isinstance(metadata, dict):
        return None

    value = metadata.get(section)
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _model_value(connector, section, key):
    return _section_value(connector, section, "model", key)


def _data(connector):
    data = _get_value(connector, "data") or {}
    return data if isinstance(data, dict) else {}


def _dict_value(value):
    return value if isinstance(value, dict) else {}


def _positive_int(value):
    return value if isinstance(value, int) and value > 0 else None


def _with_local_inference_context(connector, options):
    normalized_options = dict(options)
    normalized_options = _with_local_runtime_defaults(normalized_options)
    if _positive_int(normalized_options.get("n_ctx")):
        return normalized_options

    normalized_options["n_ctx"] = _local_inference_context_window(_get_value(connector, "local_file_path"), normalized_options)
    return normalized_options


def _with_local_runtime_defaults(options):
    normalized_options = dict(options)
    cpu_count = os.cpu_count() or 1
    n_threads = _env_positive_int("LLAMA_CPP_N_THREADS") or _physical_cpu_count(cpu_count)
    n_threads_batch = _env_positive_int("LLAMA_CPP_N_THREADS_BATCH") or cpu_count
    n_batch = _env_positive_int("LLAMA_CPP_N_BATCH") or DEFAULT_LOCAL_BATCH_TOKENS

    normalized_options.setdefault("n_threads", n_threads)
    normalized_options.setdefault("n_threads_batch", n_threads_batch)
    normalized_options.setdefault("n_batch", n_batch)
    normalized_options.setdefault("no_perf", _env_bool("LLAMA_CPP_NO_PERF", DEFAULT_LOCAL_NO_PERF))
    normalized_options.setdefault("verbose", _env_bool("LLAMA_CPP_VERBOSE", DEFAULT_LOCAL_VERBOSE))
    return normalized_options


def _with_runtime_context_override(metadata_options, top_level_options):
    env_n_ctx = _env_positive_int("LLAMA_CPP_N_CTX")
    if env_n_ctx:
        return {**metadata_options, "n_ctx": env_n_ctx}

    if _positive_int(top_level_options.get("n_ctx")) or _positive_int(top_level_options.get("context_window_tokens")):
        return metadata_options

    metadata_n_ctx = _positive_int(metadata_options.get("n_ctx"))
    if metadata_n_ctx and metadata_n_ctx > DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS:
        return {**metadata_options, "n_ctx": DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS}

    return metadata_options


def _physical_cpu_count(fallback):
    cpuinfo = Path("/proc/cpuinfo")
    if not cpuinfo.exists():
        return fallback

    cores = set()
    physical_id = None
    core_id = None
    try:
        for line in cpuinfo.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                if physical_id is not None and core_id is not None:
                    cores.add((physical_id, core_id))
                physical_id = None
                core_id = None
                continue

            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "physical id":
                physical_id = value
            elif key == "core id":
                core_id = value
    except OSError:
        return fallback

    if physical_id is not None and core_id is not None:
        cores.add((physical_id, core_id))

    return len(cores) or fallback


def _env_positive_int(name):
    try:
        value = int(os.getenv(name, ""))
    except ValueError:
        return None

    return value if value > 0 else None


def _env_bool(name, default):
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_value(source, key):
    if isinstance(source, dict):
        return source.get(key)

    return getattr(source, key, None)


def _local_embedding_size(model_path):
    if not model_path:
        return None

    try:
        return _gguf_metadata_value(Path(model_path), ".embedding_length")
    except (OSError, ValueError, TypeError):
        return None


def _local_inference_context_window(model_path, model_options):
    configured_context = _positive_int(model_options.get("n_ctx")) or _positive_int(model_options.get("context_window_tokens"))
    if configured_context:
        return configured_context

    model_context = _local_model_context_window(model_path)
    if model_context:
        return min(model_context, DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS)

    return DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS


def _local_model_context_window(model_path):
    if not model_path:
        return None

    try:
        return _gguf_metadata_value(Path(model_path), ".context_length")
    except (OSError, ValueError, TypeError):
        return None


def _gguf_metadata_value(model_path, key_suffix):
    if not model_path.exists() or not model_path.is_file():
        return None

    with model_path.open("rb") as handle:
        header = handle.read(24)
        if len(header) < 24 or header[:4] != b"GGUF":
            return None

        _, tensor_count, metadata_count = unpack_from("<IQQ", header, 4)
        del tensor_count

        for _ in range(metadata_count):
            key = _read_gguf_string(handle)
            value_type = _read_gguf_uint32(handle)
            if key.endswith(key_suffix):
                return _read_gguf_integer_value(handle, value_type)

            _skip_gguf_value(handle, value_type)

    return None


def _read_gguf_string(handle):
    size = _read_gguf_uint64(handle)
    value = handle.read(size)
    if len(value) != size:
        raise ValueError("invalid gguf string")

    return value.decode("utf-8", errors="replace")


def _read_gguf_uint32(handle):
    value = handle.read(4)
    if len(value) != 4:
        raise ValueError("invalid gguf uint32")

    return unpack_from("<I", value)[0]


def _read_gguf_uint64(handle):
    value = handle.read(8)
    if len(value) != 8:
        raise ValueError("invalid gguf uint64")

    return unpack_from("<Q", value)[0]


def _read_gguf_integer_value(handle, value_type):
    if value_type in {GGUF_TYPE_UINT8, GGUF_TYPE_INT8}:
        value = handle.read(1)
        if len(value) != 1:
            raise ValueError("invalid gguf integer")
        return value[0]

    if value_type in {GGUF_TYPE_UINT16, GGUF_TYPE_INT16}:
        value = handle.read(2)
        if len(value) != 2:
            raise ValueError("invalid gguf integer")
        return unpack_from("<H" if value_type == GGUF_TYPE_UINT16 else "<h", value)[0]

    if value_type in {GGUF_TYPE_UINT32, GGUF_TYPE_INT32}:
        value = handle.read(4)
        if len(value) != 4:
            raise ValueError("invalid gguf integer")
        return unpack_from("<I" if value_type == GGUF_TYPE_UINT32 else "<i", value)[0]

    if value_type in {GGUF_TYPE_UINT64, GGUF_TYPE_INT64}:
        value = handle.read(8)
        if len(value) != 8:
            raise ValueError("invalid gguf integer")
        return unpack_from("<Q" if value_type == GGUF_TYPE_UINT64 else "<q", value)[0]

    _skip_gguf_value(handle, value_type)
    return None


def _skip_gguf_value(handle, value_type):
    if value_type == GGUF_TYPE_STRING:
        handle.seek(_read_gguf_uint64(handle), 1)
        return

    if value_type == GGUF_TYPE_ARRAY:
        item_type = _read_gguf_uint32(handle)
        item_count = _read_gguf_uint64(handle)
        if item_type == GGUF_TYPE_STRING:
            for _ in range(item_count):
                handle.seek(_read_gguf_uint64(handle), 1)
            return

        item_size = GGUF_SCALAR_SIZES.get(item_type)
        if item_size is None:
            raise ValueError("unsupported gguf array type")
        handle.seek(item_size * item_count, 1)
        return

    value_size = GGUF_SCALAR_SIZES.get(value_type)
    if value_size is None:
        raise ValueError("unsupported gguf value type")
    handle.seek(value_size, 1)
