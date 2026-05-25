import logging
import time

from sqlalchemy import select

from app.db import db
from app.models.notebook_file import NotebookFile
from app.operations.notebooks.embed_notebook_file import EmbedNotebookFile


LOGGER = logging.getLogger("talalm.notebook_worker")


class NotebookWorker:
    def __init__(self, settings, interval_seconds=5, logger=None, sleep=None):
        self.settings = settings
        self.interval_seconds = interval_seconds
        self.logger = logger or LOGGER
        self.sleep = sleep or time.sleep
        self.should_stop = False

    def run_forever(self):
        self.logger.info("Notebook worker started. Poll interval: %s seconds.", self.interval_seconds)
        try:
            while not self.should_stop:
                self.run_once()
                self.sleep(self.interval_seconds)
        except KeyboardInterrupt:
            self.logger.info("Notebook worker interrupted. Shutting down.")
        finally:
            self.logger.info("Notebook worker stopped.")

    def run_once(self):
        self.logger.info("Polling notebook_files for pending files.")
        session = db.session()
        try:
            notebook_file = self._next_pending_file(session)
            if notebook_file is None:
                self.logger.info("No pending notebook files found.")
                return False

            self.logger.info(
                "Pending notebook file found. id=%s notebook_id=%s filename=%s",
                notebook_file.id,
                notebook_file.notebook_id,
                notebook_file.filename,
            )
            operation = EmbedNotebookFile(session=session, settings=self.settings, notebook_file=notebook_file)
            operation.execute()
            if operation.invalid():
                self.logger.error(
                    "Notebook file embedding failed. id=%s errors=%s",
                    notebook_file.id,
                    operation.payload,
                )
                return False

            self.logger.info("Notebook file embedded successfully. id=%s", notebook_file.id)
            return True
        except Exception:
            session.rollback()
            self.logger.exception("Notebook worker loop failed unexpectedly.")
            return False
        finally:
            session.close()

    def _next_pending_file(self, session):
        statement = (
            select(NotebookFile)
            .where(NotebookFile.status == "pending")
            .order_by(NotebookFile.created_at.asc())
            .limit(1)
        )

        if session.bind is not None and session.bind.dialect.name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)

        return session.execute(statement).scalars().first()
