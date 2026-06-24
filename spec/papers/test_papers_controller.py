from app.helpers.api_helpers import build_jwt_header, generate_jwt
from app.models.compile_job import CompileJob
from app.models.paper import Paper
from app.models.paper_file import PaperFile
from app.operations.papers.save import DEFAULT_PAPER_DATA
from spec.factories import CompileJobFactory, PaperFactory, PaperFileFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_list_papers_returns_current_users_papers(client, app, db_session):
    user = UserFactory(role="user")
    first = PaperFactory(user=user, name="First Paper")
    second = PaperFactory(user=user, name="Second Paper")
    PaperFactory(name="Other Paper")

    response = client.get("/papers", headers=_headers(app, user))

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["records"]] == [second.id, first.id]


def test_create_paper_initializes_phase_one_defaults(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post(
        "/papers",
        headers=_headers(app, user),
        json={"name": "Transformer Notes"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["name"] == "Transformer Notes"
    assert payload["data"] == DEFAULT_PAPER_DATA

    paper = db_session.get(Paper, payload["id"])
    assert paper.name == "Transformer Notes"
    assert paper.user_id == user.id
    assert paper.data == DEFAULT_PAPER_DATA


def test_create_paper_requires_name(client, app, db_session):
    user = UserFactory(role="user")

    response = client.post("/papers", headers=_headers(app, user), json={"name": "   "})

    assert response.status_code == 422
    assert response.json()["name"] == ["required"]


def test_show_paper_returns_paper(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user, name="Readable Paper")

    response = client.get(f"/papers/{paper.id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json()["id"] == paper.id
    assert response.json()["name"] == "Readable Paper"


def test_show_paper_hides_other_users_paper(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(name="Other Paper")

    response = client.get(f"/papers/{paper.id}", headers=_headers(app, user))

    assert response.status_code == 404


def test_show_paper_returns_not_found_for_missing_record(client, app, db_session):
    user = UserFactory(role="user")

    response = client.get("/papers/missing-paper", headers=_headers(app, user))

    assert response.status_code == 404
    assert response.json() == {"message": "not found"}


def test_delete_paper_removes_paper_records_and_storage(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    paper_file = PaperFileFactory(paper=paper, storage_key=f"papers/{paper.id}/source/main.tex")
    compile_job = CompileJobFactory(
        paper=paper,
        output_pdf_key=f"papers/{paper.id}/builds/job/output.pdf",
        log_key=f"papers/{paper.id}/builds/job/compile.log",
    )
    paper_id = paper.id
    paper_file_id = paper_file.id
    compile_job_id = compile_job.id
    deleted_keys = []

    monkeypatch.setattr(
        "app.operations.papers.destroy.delete_file",
        lambda settings, key: deleted_keys.append(key),
    )

    response = client.delete(f"/papers/{paper_id}", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert sorted(deleted_keys) == sorted([
        paper_file.storage_key,
        compile_job.output_pdf_key,
        compile_job.log_key,
    ])
    db_session.expire_all()
    assert db_session.get(Paper, paper_id) is None
    assert db_session.get(PaperFile, paper_file_id) is None
    assert db_session.get(CompileJob, compile_job_id) is None


def test_delete_paper_hides_other_users_paper(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory()
    deleted_keys = []
    monkeypatch.setattr(
        "app.operations.papers.destroy.delete_file",
        lambda settings, key: deleted_keys.append(key),
    )

    response = client.delete(f"/papers/{paper.id}", headers=_headers(app, user))

    assert response.status_code == 404
    assert deleted_keys == []
    assert db_session.get(Paper, paper.id) is not None
