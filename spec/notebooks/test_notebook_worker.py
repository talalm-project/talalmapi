from app.models.notebook_file import NotebookFile
from app.operations.notebooks.notebook_worker import NotebookWorker
from spec.factories import NotebookFileFactory


class CapturingLogger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args):
        self.messages.append(("info", message % args if args else message))

    def error(self, message, *args):
        self.messages.append(("error", message % args if args else message))

    def exception(self, message, *args):
        self.messages.append(("exception", message % args if args else message))


def test_notebook_worker_run_once_embeds_one_pending_file(app, db_session, monkeypatch):
    pending = NotebookFileFactory(status="pending", filename="pending.pdf")
    newer_pending = NotebookFileFactory(status="pending", filename="newer.pdf")
    NotebookFileFactory(status="active", filename="active.pdf")
    processed = {}
    logger = CapturingLogger()

    class FakeEmbedNotebookFile:
        payload = {}

        def __init__(self, session, settings, notebook_file):
            processed["settings"] = settings
            processed["notebook_file_id"] = notebook_file.id
            notebook_file.status = "active"
            session.commit()

        def execute(self):
            processed["executed"] = True

        def invalid(self):
            return False

    monkeypatch.setattr("app.operations.notebooks.notebook_worker.EmbedNotebookFile", FakeEmbedNotebookFile)

    worker = NotebookWorker(settings=app.state.settings, logger=logger)
    result = worker.run_once()

    assert result is True
    assert processed == {
        "settings": app.state.settings,
        "notebook_file_id": pending.id,
        "executed": True,
    }
    db_session.expire_all()
    assert db_session.get(NotebookFile, pending.id).status == "active"
    assert db_session.get(NotebookFile, newer_pending.id).status == "pending"
    assert any("Pending notebook file found" in message for _level, message in logger.messages)


def test_notebook_worker_run_once_logs_when_no_pending_files(app, db_session):
    NotebookFileFactory(status="active")
    logger = CapturingLogger()

    worker = NotebookWorker(settings=app.state.settings, logger=logger)
    result = worker.run_once()

    assert result is False
    assert ("info", "No pending notebook files found.") in logger.messages


def test_notebook_worker_run_once_logs_embedding_failure(app, db_session, monkeypatch):
    pending = NotebookFileFactory(status="pending")
    logger = CapturingLogger()

    class FakeEmbedNotebookFile:
        payload = {"embedding": ["failed"]}

        def __init__(self, session, settings, notebook_file):
            pass

        def execute(self):
            pass

        def invalid(self):
            return True

    monkeypatch.setattr("app.operations.notebooks.notebook_worker.EmbedNotebookFile", FakeEmbedNotebookFile)

    worker = NotebookWorker(settings=app.state.settings, logger=logger)
    result = worker.run_once()

    assert result is False
    assert any("Notebook file embedding failed" in message for level, message in logger.messages if level == "error")
    assert db_session.get(NotebookFile, pending.id).status == "pending"


def test_notebook_worker_run_forever_sleeps_between_iterations(app, monkeypatch):
    calls = []
    logger = CapturingLogger()

    def fake_run_once():
        calls.append("run_once")
        worker.should_stop = True

    def fake_sleep(seconds):
        calls.append(("sleep", seconds))

    worker = NotebookWorker(settings=app.state.settings, interval_seconds=5, logger=logger, sleep=fake_sleep)
    monkeypatch.setattr(worker, "run_once", fake_run_once)

    worker.run_forever()

    assert calls == ["run_once", ("sleep", 5)]
    assert ("info", "Notebook worker stopped.") in logger.messages
