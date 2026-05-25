from struct import pack

from app.operations.connectors.metadata import build_connector_metadata


def test_build_local_connector_metadata_reads_embedding_size_from_gguf(tmp_path):
    model_path = tmp_path / "embedding.gguf"
    _write_gguf_metadata(model_path, {"qwen3.embedding_length": 1024})

    metadata = build_connector_metadata(
        {
            "name": "Local Llama",
            "connection_type": "local",
            "local_file_path": "/tmp/llama.gguf",
            "embedding_name": "Qwen Embedding",
            "embedding_local_file_path": str(model_path),
        },
        {},
    )

    assert metadata["embeddings"]["model"]["embedding_size"] == 1024


def test_build_local_connector_metadata_sets_inference_n_ctx_from_gguf_context_length(tmp_path):
    model_path = tmp_path / "llama.gguf"
    _write_gguf_metadata(model_path, {"qwen3.context_length": 2048})

    metadata = build_connector_metadata(
        {
            "name": "Local Llama",
            "connection_type": "local",
            "local_file_path": str(model_path),
        },
        {},
    )

    assert metadata["inference"]["limits"]["context_window_tokens"] == 2048
    assert metadata["inference"]["model_options"]["n_ctx"] == 2048


def test_build_local_connector_metadata_caps_large_gguf_context_length(tmp_path):
    model_path = tmp_path / "llama.gguf"
    _write_gguf_metadata(model_path, {"qwen3.context_length": 32768})

    metadata = build_connector_metadata(
        {
            "name": "Local Llama",
            "connection_type": "local",
            "local_file_path": str(model_path),
        },
        {},
    )

    assert metadata["inference"]["limits"]["context_window_tokens"] == 4096
    assert metadata["inference"]["model_options"]["n_ctx"] == 4096


def test_build_local_connector_metadata_keeps_explicit_n_ctx(tmp_path):
    model_path = tmp_path / "llama.gguf"
    _write_gguf_metadata(model_path, {"qwen3.context_length": 32768})

    metadata = build_connector_metadata(
        {
            "name": "Local Llama",
            "connection_type": "local",
            "local_file_path": str(model_path),
        },
        {"model_options": {"n_ctx": 1024}},
    )

    assert metadata["inference"]["limits"]["context_window_tokens"] == 1024
    assert metadata["inference"]["model_options"]["n_ctx"] == 1024


def test_build_local_connector_metadata_uses_null_embedding_size_when_gguf_is_unavailable():
    metadata = build_connector_metadata(
        {
            "name": "Local Llama",
            "connection_type": "local",
            "local_file_path": "/tmp/llama.gguf",
            "embedding_name": "Qwen Embedding",
            "embedding_local_file_path": "/tmp/missing.gguf",
        },
        {},
    )

    assert metadata["embeddings"]["model"]["embedding_size"] is None
    assert metadata["inference"]["model_options"]["n_ctx"] == 4096


def test_build_openai_connector_metadata_includes_embedding_size():
    metadata = build_connector_metadata(
        {
            "name": "gpt-4.1",
            "connection_type": "openai",
            "embedding_name": "text-embedding-3-large",
        },
        {},
    )

    assert metadata["embeddings"]["model"]["embedding_size"] == 3072


def _write_gguf_metadata(path, records):
    data = bytearray()
    data.extend(b"GGUF")
    data.extend(pack("<I", 3))
    data.extend(pack("<Q", 0))
    data.extend(pack("<Q", len(records)))
    for key, value in records.items():
        encoded_key = key.encode("utf-8")
        data.extend(pack("<Q", len(encoded_key)))
        data.extend(encoded_key)
        data.extend(pack("<I", 4))
        data.extend(pack("<I", value))
    path.write_bytes(data)
