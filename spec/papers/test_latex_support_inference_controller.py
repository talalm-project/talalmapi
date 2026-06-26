from app.helpers.api_helpers import build_jwt_header, generate_jwt
from spec.factories import ConnectorFactory, PaperFactory, PaperFileFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_latex_support_inference_returns_agent_payload(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    connector = ConnectorFactory(user=user)
    paper = PaperFactory(
        user=user,
        data={
            "connector_id": connector.id,
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
            "document_ids": [paper_file.id],
            "note_ids": ["note-1"],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "```latex\nx^2\n```",
        "content": "x^2",
    }
    assert captured["connector"] == connector
    assert [record["id"] for record in captured["document_references"]] == [paper_file.id]
    assert captured["document_references"][0]["path"] == "source/main.tex"
    assert captured["notes_references"] == [{"id": "note-1", "name": "Equation style", "content": "Use equation* blocks."}]
    assert captured["user_prompt"] == "Create a LaTeX snippet for x squared."


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
