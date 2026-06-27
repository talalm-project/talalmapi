from app.helpers.api_helpers import build_jwt_header, generate_jwt
from spec.factories import ConnectorFactory, NotebookFactory, NotebookFileFactory, NotebookNoteFactory, PaperFactory, PaperFileFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_latex_support_inference_returns_agent_payload(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper_connector = ConnectorFactory(user=user)
    request_connector = ConnectorFactory(user=user)
    paper = PaperFactory(
        user=user,
        data={
            "connector_id": paper_connector.id,
            "notes": [
                {"id": "note-1", "name": "Equation style", "content": "Use equation* blocks."},
                {"id": "note-2", "name": "Unused", "content": "Do not include this note."},
            ],
        },
    )
    paper_file = PaperFileFactory(paper=paper, path="source/main.tex")
    captured = {}

    class FakeLatexSupportInference:
        def __init__(self, connector, document_references, notes_references, user_prompt):
            captured["connector"] = connector
            captured["document_references"] = document_references
            captured["notes_references"] = notes_references
            captured["user_prompt"] = user_prompt
            self.payload = {
                "message": "```latex\nx^2\n```",
                "content": "x^2",
            }
            self.errors = {}

        def execute(self):
            pass

        def valid(self):
            return True

    monkeypatch.setattr(
        "app.operations.papers.latex_support_inference.AgentLatexSupportInference",
        FakeLatexSupportInference,
    )

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={
            "user_prompt": "Create a LaTeX snippet for x squared.",
            "connector_id": request_connector.id,
            "document_ids": [paper_file.id],
            "note_ids": ["note-1"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "```latex\nx^2\n```",
        "content": "x^2",
    }
    assert captured["connector"].id == request_connector.id
    assert [record["id"] for record in captured["document_references"]] == [paper_file.id]
    assert captured["document_references"][0]["path"] == "source/main.tex"
    assert captured["notes_references"] == [{"id": "note-1", "name": "Equation style", "content": "Use equation* blocks."}]
    assert captured["user_prompt"] == "Create a LaTeX snippet for x squared."


def test_latex_support_inference_accepts_notebook_references(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    paper = PaperFactory(user=user)
    notebook = NotebookFactory(user=user, connector=connector)
    notebook_file = NotebookFileFactory(
        notebook=notebook,
        name="Gradient Notes",
        filename="gradient.pdf",
        status="active",
        data={"summary": "Use vector notation."},
    )
    notebook_note = NotebookNoteFactory(
        notebook=notebook,
        name="Formatting",
        data={"content": "Use align blocks."},
    )
    captured = {}

    class FakeLatexSupportInference:
        def __init__(self, connector, document_references, notes_references, user_prompt):
            captured["connector"] = connector
            captured["document_references"] = document_references
            captured["notes_references"] = notes_references
            captured["user_prompt"] = user_prompt
            self.payload = {
                "message": "```latex\n\\nabla f\n```",
                "content": "\\nabla f",
            }
            self.errors = {}

        def execute(self):
            pass

        def valid(self):
            return True

    monkeypatch.setattr(
        "app.operations.papers.latex_support_inference.AgentLatexSupportInference",
        FakeLatexSupportInference,
    )

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={
            "user_prompt": "Create a gradient expression.",
            "connector_id": connector.id,
            "notebook_id": notebook.id,
            "notebook_file_ids": [notebook_file.id],
            "notebook_note_ids": [notebook_note.id],
        },
    )

    assert response.status_code == 200
    assert response.json()["content"] == "\\nabla f"
    assert captured["connector"].id == connector.id
    assert [record["id"] for record in captured["document_references"]] == [notebook_file.id]
    assert captured["document_references"][0]["filename"] == "gradient.pdf"
    assert captured["notes_references"] == [notebook_note.to_dict()]
    assert captured["user_prompt"] == "Create a gradient expression."


def test_latex_support_inference_hides_other_users_paper(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory()

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={"user_prompt": "Create LaTeX.", "document_ids": [], "note_ids": []},
    )

    assert response.status_code == 404


def test_latex_support_inference_rejects_invalid_selected_ids(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    paper = PaperFactory(
        user=user,
        data={
            "connector_id": connector.id,
            "notes": [{"id": "note-1", "content": "Use align."}],
        },
    )

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={
            "user_prompt": "Create LaTeX.",
            "document_ids": ["missing-document"],
            "note_ids": ["missing-note"],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "document_ids": ["invalid"],
        "note_ids": ["invalid"],
    }


def test_latex_support_inference_rejects_invalid_notebook_references(client, app, db_session):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    paper = PaperFactory(user=user)
    notebook = NotebookFactory(user=user, connector=connector)
    other_notebook = NotebookFactory(connector=ConnectorFactory())
    other_file = NotebookFileFactory(notebook=other_notebook)
    other_note = NotebookNoteFactory(notebook=other_notebook)

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={
            "user_prompt": "Create LaTeX.",
            "connector_id": connector.id,
            "notebook_id": notebook.id,
            "notebook_file_ids": [other_file.id],
            "notebook_note_ids": [other_note.id],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "notebook_file_ids": ["invalid"],
        "notebook_note_ids": ["invalid"],
    }


def test_latex_support_inference_returns_input_validation_errors(client, app, db_session):
    user = UserFactory(role="user")
    ConnectorFactory(user=user)
    paper = PaperFactory(user=user, data={})

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={
            "user_prompt": " ",
            "connector_id": " ",
            "document_ids": ["", 123],
            "note_ids": ["", 123],
            "notebook_id": 123,
            "notebook_file_ids": ["", 123],
            "notebook_note_ids": ["", 123],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "connector_id": ["invalid"],
        "user_prompt": ["required"],
        "document_ids": ["invalid"],
        "note_ids": ["invalid"],
        "notebook_id": ["invalid"],
        "notebook_file_ids": ["invalid"],
        "notebook_note_ids": ["invalid"],
    }


def test_latex_support_inference_does_not_call_agent_when_validation_fails(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user, data={})

    def fail_if_called(*args, **kwargs):
        raise AssertionError("agent inference should not run when validation fails")

    monkeypatch.setattr(
        "app.operations.papers.latex_support_inference.AgentLatexSupportInference",
        fail_if_called,
    )

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={
            "user_prompt": " ",
            "connector_id": " ",
            "document_ids": [],
            "note_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "connector_id": ["invalid"],
        "user_prompt": ["required"],
    }


def test_latex_support_inference_rejects_other_users_connector(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user, data={})
    other_connector = ConnectorFactory()

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={
            "user_prompt": "Create LaTeX.",
            "connector_id": other_connector.id,
            "document_ids": [],
            "note_ids": [],
        },
    )

    assert response.status_code == 422
    assert response.json()["connector_id"] == ["not found"]


def test_latex_support_inference_requires_connector(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user, data={})

    response = client.post(
        f"/papers/{paper.id}/latex_support_inference",
        headers=_headers(app, user),
        json={"user_prompt": "Create LaTeX.", "document_ids": [], "note_ids": []},
    )

    assert response.status_code == 422
    assert response.json()["connector"] == ["required"]
