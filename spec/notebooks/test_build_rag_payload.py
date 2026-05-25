from app.operations.notebooks.build_rag_payload import BuildRagPayload
from app.schemas.connector import ConnectorInfer
from spec.factories import ConnectorFactory


def test_build_rag_payload_caps_local_context_to_model_window(db_session):
    connector = ConnectorFactory(
        connection_type="local",
        data={"model_options": {"n_ctx": 512}},
    )
    chunks = [
        {
            "text": "alpha " * 1000,
        },
        {
            "text": "beta " * 1000,
        },
    ]
    payload = ConnectorInfer(prompt="Summarize this notebook.", options={})

    operation = BuildRagPayload(payload, chunks, connector=connector, system_prompt="Answer from context only.")
    operation.execute()

    assert operation.rag_payload.options["max_tokens"] == 128
    assert len(operation.rag_payload.prompt) < 1000
    assert operation.rag_payload.prompt.startswith("Instructions:\n\nAnswer from context only.")
    assert "[truncated]" in operation.rag_payload.prompt
    assert "User question:\n\nSummarize this notebook." in operation.rag_payload.prompt


def test_build_rag_payload_preserves_smaller_requested_local_output_tokens(db_session):
    connector = ConnectorFactory(
        connection_type="local",
        data={"model_options": {"n_ctx": 512}},
    )
    payload = ConnectorInfer(prompt="Summarize", options={"max_tokens": 32})

    operation = BuildRagPayload(payload, [{"text": "context"}], connector=connector)
    operation.execute()

    assert operation.rag_payload.options["max_tokens"] == 32


def test_build_rag_payload_uses_metadata_default_context_without_explicit_n_ctx(db_session):
    connector = ConnectorFactory(
        connection_type="local",
        data={},
    )
    payload = ConnectorInfer(prompt="Summarize", options={})

    operation = BuildRagPayload(payload, [{"text": "context"}], connector=connector)
    operation.execute()

    assert operation.rag_payload.options["max_tokens"] == 1024


def test_build_rag_payload_contextualizes_recent_chat_for_local_rag(db_session):
    connector = ConnectorFactory(
        connection_type="local",
        data={"model_options": {"n_ctx": 512}},
    )
    payload = ConnectorInfer(
        input=[
            {"role": "user", "content": "Previous question"},
            {"role": "assistant", "content": "Previous answer " * 1000},
            {"role": "user", "content": "Current question"},
        ],
        options={},
    )

    operation = BuildRagPayload(payload, [{"text": "Current context"}], connector=connector)
    operation.execute()

    assert operation.rag_payload.input is None
    assert "Conversation context policy:" in operation.rag_payload.prompt
    assert "resolve follow-up references like 'this'" in operation.rag_payload.prompt
    assert "Conversation context:" in operation.rag_payload.prompt
    assert "User: Previous question" in operation.rag_payload.prompt
    assert "Assistant: Previous answer" in operation.rag_payload.prompt
    assert "Notebook context:\n\n[1] Current context" in operation.rag_payload.prompt
    assert "User question:\n\nCurrent question" in operation.rag_payload.prompt
