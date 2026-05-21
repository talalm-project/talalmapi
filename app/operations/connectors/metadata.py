from pathlib import Path
from struct import unpack_from


DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS = 4096
DEFAULT_LOCAL_EMBEDDING_CONTEXT_WINDOW_TOKENS = 65536
DEFAULT_LOCAL_EMBEDDING_BATCH_TOKENS = 512
DEFAULT_LOCAL_EMBEDDING_SEQUENCES = 256
DEFAULT_LOCAL_OUTPUT_TOKENS = 1024
DEFAULT_EMBEDDING_CHARS_PER_TOKEN = 4
DEFAULT_EMBEDDING_CHUNK_RATIO = 0.75
DEFAULT_EMBEDDING_CHUNK_OVERLAP_RATIO = 0.1
OPENAI_DEFAULT_EMBEDDING_INPUT_TOKENS = 8191
OPENAI_EMBEDDING_INPUT_TOKENS = {
    "text-embedding-3-small": 8191,
    "text-embedding-3-large": 8191,
    "text-embedding-ada-002": 8191,
}
OPENAI_EMBEDDING_SIZES = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
}
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
    connection_type = _get_value(connector_attrs, "connection_type") or "local"

    return {
        "schema_version": 1,
        "provider": connection_type,
        "inference": _inference_metadata(connector_attrs, data, connection_type),
        "embeddings": _embeddings_metadata(connector_attrs, data, connection_type),
    }


def inference_model_options(connector):
    metadata_options = _section_value(connector, "inference", "model_options")
    if isinstance(metadata_options, dict):
        return metadata_options

    options = _data(connector).get("model_options", {})
    return options if isinstance(options, dict) else {}


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


def _inference_metadata(connector_attrs, data, connection_type):
    model_options = _dict_value(data.get("model_options"))
    context_window_tokens = _positive_int(model_options.get("n_ctx"))

    if connection_type == "local":
        context_window_tokens = context_window_tokens or DEFAULT_LOCAL_CONTEXT_WINDOW_TOKENS
        model = {
            "name": _get_value(connector_attrs, "name"),
            "local_file_path": _get_value(connector_attrs, "local_file_path"),
        }
    else:
        model = {
            "name": _get_value(connector_attrs, "name"),
            "local_file_path": None,
        }

    return {
        "model": model,
        "model_options": model_options,
        "limits": {
            "context_window_tokens": context_window_tokens,
            "max_input_tokens": context_window_tokens,
            "default_output_tokens": DEFAULT_LOCAL_OUTPUT_TOKENS if connection_type == "local" else None,
        },
    }


def _embeddings_metadata(connector_attrs, data, connection_type):
    model_options = _dict_value(data.get("embedding_model_options"))
    if connection_type == "local":
        return _local_embeddings_metadata(connector_attrs, model_options)

    return _openai_embeddings_metadata(connector_attrs, model_options)


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


def _openai_embeddings_metadata(connector_attrs, model_options):
    model_name = _get_value(connector_attrs, "embedding_name")
    max_input_tokens = OPENAI_EMBEDDING_INPUT_TOKENS.get(model_name, OPENAI_DEFAULT_EMBEDDING_INPUT_TOKENS)

    return {
        "model": {
            "name": model_name,
            "local_file_path": None,
            "embedding_size": OPENAI_EMBEDDING_SIZES.get(model_name),
        },
        "model_options": model_options,
        "limits": _embedding_limits(max_input_tokens, max_input_tokens),
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


def _get_value(source, key):
    if isinstance(source, dict):
        return source.get(key)

    return getattr(source, key, None)


def _local_embedding_size(model_path):
    if not model_path:
        return None

    try:
        return _gguf_embedding_size(Path(model_path))
    except (OSError, ValueError, TypeError):
        return None


def _gguf_embedding_size(model_path):
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
            if key.endswith(".embedding_length"):
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
