from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models.connector import Connector
from app.models.notebook import Notebook
from app.models.notebook_file import NotebookFile
from app.operations.notebooks.ensure_embedding_configs import EnsureEmbeddingConfigs


QUEUED_FILE_STATUSES = {"pending", "uploading", "processing"}
ATTENTION_FILE_LIMIT = 8


class Show:
    def __init__(self, session, user):
        self.session = session
        self.user = user
        self.connectors = []
        self.notebooks = []
        self.notebook_files = []
        self.files_by_notebook_id = {}
        self.files_counts = {}
        self.payload = {}

    def execute(self):
        self.connectors = self._connectors()
        self.notebooks = self._notebooks()
        EnsureEmbeddingConfigs(self.session, self.notebooks).execute()
        self.notebook_files = self._notebook_files()
        self.files_by_notebook_id = self._group_files_by_notebook()
        self.files_counts = self._files_counts()
        self.payload = self._payload()

    def _connectors(self):
        return (
            self.session.execute(
                select(Connector)
                .where(Connector.user_id == self.user.id)
                .order_by(Connector.created_at.desc())
            )
            .scalars()
            .all()
        )

    def _notebooks(self):
        return (
            self.session.execute(
                select(Notebook)
                .where(Notebook.user_id == self.user.id)
                .options(selectinload(Notebook.connector))
                .order_by(Notebook.created_at.desc())
            )
            .scalars()
            .all()
        )

    def _notebook_files(self):
        notebook_ids = [notebook.id for notebook in self.notebooks]
        if not notebook_ids:
            return []

        return (
            self.session.execute(
                select(NotebookFile)
                .where(NotebookFile.notebook_id.in_(notebook_ids))
                .order_by(NotebookFile.created_at.desc())
            )
            .scalars()
            .all()
        )

    def _group_files_by_notebook(self):
        records = {}
        for notebook_file in self.notebook_files:
            records.setdefault(notebook_file.notebook_id, []).append(notebook_file)
        return records

    def _files_counts(self):
        notebook_ids = [notebook.id for notebook in self.notebooks]
        if not notebook_ids:
            return {}

        rows = self.session.execute(
            select(NotebookFile.notebook_id, func.count(NotebookFile.id))
            .where(NotebookFile.notebook_id.in_(notebook_ids))
            .group_by(NotebookFile.notebook_id)
        ).all()
        return {notebook_id: count for notebook_id, count in rows}

    def _payload(self):
        summary = self._summary()
        return {
            "summary": summary,
            "notebooks": self._notebook_rows(),
            "connectors": self._connector_rows(),
            "attention_files": self._attention_files(),
        }

    def _summary(self):
        active_files_count = _status_count(self.notebook_files, "active")
        queued_files_count = len([file for file in self.notebook_files if file.status in QUEUED_FILE_STATUSES])
        failed_files_count = _status_count(self.notebook_files, "failed")
        notebooks_without_files_count = len(
            [notebook for notebook in self.notebooks if self.files_counts.get(notebook.id, 0) == 0]
        )

        return {
            "notebooks_count": len(self.notebooks),
            "active_notebooks_count": len(
                [
                    notebook
                    for notebook in self.notebooks
                    if _notebook_health(notebook, self.files_by_notebook_id.get(notebook.id, [])) == "active"
                ]
            ),
            "connectors_count": len(self.connectors),
            "local_connectors_count": len(self.connectors),
            "active_files_count": active_files_count,
            "queued_files_count": queued_files_count,
            "failed_files_count": failed_files_count,
            "notebooks_without_files_count": notebooks_without_files_count,
            "total_file_bytes": sum(file.byte_size or 0 for file in self.notebook_files),
            "needs_attention_count": queued_files_count + failed_files_count + notebooks_without_files_count,
        }

    def _notebook_rows(self):
        return [
            {
                "notebook": notebook.to_dict(files_count=self.files_counts.get(notebook.id, 0)),
                "connector": notebook.connector.to_dict() if notebook.connector is not None else None,
                "health": _notebook_health(notebook, self.files_by_notebook_id.get(notebook.id, [])),
                "file_summary": _file_summary(self.files_by_notebook_id.get(notebook.id, [])),
            }
            for notebook in self.notebooks
        ]

    def _connector_rows(self):
        return [
            {
                "connector": connector.to_dict(),
                "notebooks_count": len([notebook for notebook in self.notebooks if notebook.connector_id == connector.id]),
            }
            for connector in self.connectors
        ]

    def _attention_files(self):
        files = [file for file in self.notebook_files if file.status == "failed" or file.status in QUEUED_FILE_STATUSES]
        files = sorted(files, key=_attention_file_sort_key)[:ATTENTION_FILE_LIMIT]
        notebooks_by_id = {notebook.id: notebook for notebook in self.notebooks}
        return [
            {
                **file.to_dict(),
                "notebook": notebooks_by_id[file.notebook_id].to_dict(
                    files_count=self.files_counts.get(file.notebook_id, 0)
                )
                if file.notebook_id in notebooks_by_id
                else None,
            }
            for file in files
        ]


def _status_count(records, status):
    return len([record for record in records if record.status == status])


def _file_summary(files):
    return {
        "active": _status_count(files, "active"),
        "queued": len([file for file in files if file.status in QUEUED_FILE_STATUSES]),
        "failed": _status_count(files, "failed"),
        "total": len(files),
    }


def _notebook_health(notebook, files):
    if notebook.status == "failed" or _status_count(files, "failed") > 0:
        return "failed"

    if notebook.status == "processing" or any(file.status in QUEUED_FILE_STATUSES for file in files):
        return "processing"

    if notebook.status == "active" and files and all(file.status == "active" for file in files):
        return "active"

    if notebook.status == "active" and not files:
        return "pending"

    return notebook.status or "pending"


def _attention_file_sort_key(file):
    priority = 0 if file.status == "failed" else 1
    created_at = file.created_at.timestamp() if file.created_at is not None else 0
    return (priority, -created_at)
