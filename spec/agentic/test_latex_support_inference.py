from types import SimpleNamespace

from app.schemas.connector import ConnectorInfer


def test_latex_support_inference_builds_context_prompt_and_returns_latex_payload(monkeypatch):
    from app.operations.agentic.latex_support_inference import LatexSupportInference

    connector = SimpleNamespace(id="connector-1")
    document_references = [
        SimpleNamespace(id="doc-1", name="Derivatives.pdf", data={"summary": "Use the chain rule."}),
        {"id": "doc-2", "title": "Integrals", "content": "Prefer aligned equations."},
    ]
    notes_references = [
        SimpleNamespace(id="note-1", name="Formatting note", data={"content": "Use equation*."}),
    ]
    captured = {}

    class FakeConnectorInfer:
        def __init__(self, infer_connector, payload, system_prompt=None):
            captured["connector"] = infer_connector
            captured["payload"] = payload
            captured["system_prompt"] = system_prompt
            self.response = {
                "response": {
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "```latex\n\\begin{equation*}\nf'(x)=2x\n\\end{equation*}\n```",
                            }
                        }
                    ]
                }
            }
            self.errors = {}

        def execute(self):
            pass

        def valid(self):
            return True

    monkeypatch.setattr("app.operations.agentic.latex_support_inference.ConnectorInferOperation", FakeConnectorInfer)

    operation = LatexSupportInference(
        connector=connector,
        document_references=document_references,
        notes_references=notes_references,
        user_prompt="Create LaTeX for the derivative of x squared.",
    )

    operation.execute()

    assert operation.valid()
    assert operation.payload == {
        "message": "```latex\n\\begin{equation*}\nf'(x)=2x\n\\end{equation*}\n```",
        "content": "\\begin{equation*}\nf'(x)=2x\n\\end{equation*}",
    }
    assert captured["connector"] == connector
    assert isinstance(captured["payload"], ConnectorInfer)
    assert captured["payload"].prompt == "Create LaTeX for the derivative of x squared."
    assert captured["payload"].options["temperature"] == 0
    assert "Return exactly one markdown fenced code block containing only LaTeX." in captured["system_prompt"]
    assert "Document references:" in captured["system_prompt"]
    assert "Derivatives.pdf" in captured["system_prompt"]
    assert "Use the chain rule." in captured["system_prompt"]
    assert "Notes references:" in captured["system_prompt"]
    assert "Use equation*." in captured["system_prompt"]


def test_latex_support_inference_wraps_unfenced_latex_response(monkeypatch):
    from app.operations.agentic.latex_support_inference import LatexSupportInference

    class FakeConnectorInfer:
        def __init__(self, infer_connector, payload, system_prompt=None):
            self.response = {"response": {"choices": [{"message": {"content": "\\frac{a}{b}"}}]}}
            self.errors = {}

        def execute(self):
            pass

        def valid(self):
            return True

    monkeypatch.setattr("app.operations.agentic.latex_support_inference.ConnectorInferOperation", FakeConnectorInfer)

    operation = LatexSupportInference(
        connector=SimpleNamespace(id="connector-1"),
        document_references=[],
        notes_references=[],
        user_prompt="Create a fraction.",
    )

    operation.execute()

    assert operation.payload == {
        "message": "```latex\n\\frac{a}{b}\n```",
        "content": "\\frac{a}{b}",
    }


def test_latex_support_inference_requires_user_prompt():
    from app.operations.agentic.latex_support_inference import LatexSupportInference

    operation = LatexSupportInference(
        connector=SimpleNamespace(id="connector-1"),
        document_references=[],
        notes_references=[],
        user_prompt=" ",
    )

    operation.execute()

    assert not operation.valid()
    assert operation.errors == {"user_prompt": ["required"]}
