from types import SimpleNamespace

from app.helpers.api_helpers import build_jwt_header, generate_jwt
from app.models.compile_job import CompileJob
from app.services.paper_compile_service import PaperCompileService
from spec.factories import CompileJobFactory, PaperFactory, PaperFileFactory, UserFactory


def _headers(app, user):
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


def test_create_compile_job_returns_pending_job(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    PaperFileFactory(paper=paper, path="source/main.tex")
    compiled = {}

    def fake_compile_job(self, job_id):
        compiled["job_id"] = job_id

    monkeypatch.setattr(PaperCompileService, "compile_job", fake_compile_job)

    response = client.post(f"/papers/{paper.id}/compile", headers=_headers(app, user))

    assert response.status_code == 201
    payload = response.json()
    assert payload["paper_id"] == paper.id
    assert payload["status"] == "pending"
    assert payload["compiler"] == "pdflatex"
    assert compiled == {"job_id": payload["id"]}


def test_create_compile_job_requires_files(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)

    response = client.post(f"/papers/{paper.id}/compile", headers=_headers(app, user))

    assert response.status_code == 422
    assert response.json()["files"] == ["required"]


def test_compile_service_marks_job_success_and_uploads_outputs(app, db_session, monkeypatch, tmp_path):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user, data={"main_file": "main.tex", "compiler": "pdflatex"})
    PaperFileFactory(paper=paper, path="source/main.tex", storage_key="papers/paper/source/main.tex")
    job = CompileJobFactory(paper=paper)
    app.state.settings.LATEX_TMP_ROOT = str(tmp_path)
    uploaded = {}

    class Body:
        def read(self):
            return b"\\documentclass{article}\\begin{document}Hi\\end{document}"

    def fake_get_file(settings, key):
        return {"Body": Body(), "ContentType": "application/x-tex"}

    def fake_run(command, cwd, capture_output, text, timeout, shell):
        build_dir = cwd / "build"
        build_dir.mkdir(parents=True, exist_ok=True)
        (build_dir / "main.pdf").write_bytes(b"%PDF-1.4")
        return SimpleNamespace(returncode=0, stdout="Latexmk success", stderr="")

    def fake_store_file_at_key(upload, settings, key, filename=None):
        uploaded[key] = upload.file.read()
        return {
            "key": key,
            "filename": filename,
            "content_type": upload.content_type,
            "byte_size": None,
            "url": "http://localhost/object",
        }

    monkeypatch.setattr("app.services.paper_compile_service.get_file", fake_get_file)
    monkeypatch.setattr("app.services.paper_compile_service.subprocess.run", fake_run)
    monkeypatch.setattr("app.services.paper_compile_service.store_file_at_key", fake_store_file_at_key)

    PaperCompileService(app.state.settings).compile_job(job.id)

    db_session.expire_all()
    compile_job = db_session.get(CompileJob, job.id)
    db_session.refresh(paper)
    assert compile_job.status == "success"
    assert compile_job.output_pdf_key == f"papers/{paper.id}/builds/{job.id}/output.pdf"
    assert compile_job.log_key == f"papers/{paper.id}/builds/{job.id}/compile.log"
    assert "Latexmk success" in compile_job.logs
    assert uploaded[compile_job.output_pdf_key] == b"%PDF-1.4"
    assert paper.data["latest_compile_job_id"] == job.id
    assert paper.data["latest_pdf_key"] == compile_job.output_pdf_key


def test_compile_service_marks_job_failed_when_main_file_missing(app, db_session, monkeypatch, tmp_path):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user, data={"main_file": "main.tex"})
    PaperFileFactory(paper=paper, path="source/other.tex")
    job = CompileJobFactory(paper=paper)
    app.state.settings.LATEX_TMP_ROOT = str(tmp_path)

    class Body:
        def read(self):
            return b"Other file"

    monkeypatch.setattr(
        "app.services.paper_compile_service.get_file",
        lambda settings, key: {"Body": Body(), "ContentType": "application/x-tex"},
    )

    PaperCompileService(app.state.settings).compile_job(job.id)

    db_session.expire_all()
    compile_job = db_session.get(CompileJob, job.id)
    assert compile_job.status == "failed"
    assert compile_job.error_message == "Main file not found: main.tex"
    assert "Main file not found" in compile_job.logs


def test_show_compile_job_and_index(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    first = CompileJobFactory(paper=paper, status="failed")
    second = CompileJobFactory(paper=paper, status="success")

    show_response = client.get(f"/papers/{paper.id}/compile-jobs/{first.id}", headers=_headers(app, user))
    index_response = client.get(f"/papers/{paper.id}/compile-jobs", headers=_headers(app, user))

    assert show_response.status_code == 200
    assert show_response.json()["id"] == first.id
    assert index_response.status_code == 200
    assert [record["id"] for record in index_response.json()["records"]] == [second.id, first.id]


def test_compile_job_pdf_streams_successful_pdf(client, app, db_session, monkeypatch):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    job = CompileJobFactory(
        paper=paper,
        status="success",
        output_pdf_key=f"papers/{paper.id}/builds/job/output.pdf",
    )

    class Body:
        def __iter__(self):
            yield b"%PDF-1.4"

    captured = {}

    def fake_get_file(settings, key):
        captured["key"] = key
        return {"Body": Body(), "ContentType": "application/pdf"}

    monkeypatch.setattr("app.controllers.papers_controller.get_file", fake_get_file)

    response = client.get(f"/papers/{paper.id}/compile-jobs/{job.id}/pdf", headers=_headers(app, user))

    assert response.status_code == 200
    assert response.content == b"%PDF-1.4"
    assert captured == {"key": f"papers/{paper.id}/builds/job/output.pdf"}


def test_compile_job_pdf_returns_not_found_for_failed_job(client, app, db_session):
    user = UserFactory(role="user")
    paper = PaperFactory(user=user)
    job = CompileJobFactory(paper=paper, status="failed")

    response = client.get(f"/papers/{paper.id}/compile-jobs/{job.id}/pdf", headers=_headers(app, user))

    assert response.status_code == 404
