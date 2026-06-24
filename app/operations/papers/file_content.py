from io import BytesIO
from pathlib import PurePosixPath
from types import SimpleNamespace

from botocore.exceptions import ClientError

from app.models.user import utcnow
from app.operations.papers.show_file import ShowFile
from app.operations.validator import Validator
from app.storage import get_file, store_file_at_key


EDITABLE_EXTENSIONS = {".bib", ".cls", ".md", ".sty", ".tex", ".txt"}


def editable_paper_file(paper_file):
    return PurePosixPath(paper_file.path or paper_file.filename or "").suffix.lower() in EDITABLE_EXTENSIONS


class ReadFileContent:
    def __init__(self, session, user, settings, paper_id, paper_file_id):
        self.session = session
        self.user = user
        self.settings = settings
        self.paper_id = paper_id
        self.paper_file_id = paper_file_id
        self.paper_file = None
        self.content = None
        self.editable = False
        self.error_message = None
        self._show_file = ShowFile(session=session, user=user, paper_id=paper_id, paper_file_id=paper_file_id)

    def execute(self):
        self._show_file.execute()
        if not self._show_file.found():
            return

        self.paper_file = self._show_file.paper_file
        self.editable = editable_paper_file(self.paper_file)
        if not self.editable:
            self.error_message = "This file type cannot be edited."
            return

        try:
            response = get_file(self.settings, self.paper_file.storage_key)
            content_bytes = response["Body"].read()
            self.content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            self.editable = False
            self.error_message = "This file type cannot be edited."
        except (ClientError, OSError) as error:
            self.error_message = f"Unable to load file content: {error}"

    def found(self):
        return self._show_file.found()

    def storage_error(self):
        return self.found() and self.editable and self.content is None and self.error_message is not None

    def to_dict(self):
        return {
            "file": self.paper_file.to_dict(),
            "editable": self.editable,
            "content": self.content,
            "message": self.error_message,
        }


class SaveFileContent(Validator):
    def __init__(self, session, user, settings, paper_id, paper_file_id, content=None, last_known_updated_at=None):
        super().__init__()
        self.session = session
        self.user = user
        self.settings = settings
        self.paper_id = paper_id
        self.paper_file_id = paper_file_id
        self.content = content
        self.last_known_updated_at = last_known_updated_at
        self.paper_file = None
        self.error_message = None
        self.conflict_message = None
        self.payload = {
            "content": [],
            "file": [],
        }
        self._show_file = ShowFile(session=session, user=user, paper_id=paper_id, paper_file_id=paper_file_id)

    def execute(self):
        self._show_file.execute()
        if not self._show_file.found():
            return

        self.paper_file = self._show_file.paper_file
        if self._conflicted():
            self.conflict_message = "This file was changed elsewhere. Please reload before saving."
            return

        self._validate()
        if self.invalid():
            return

        body = self.content.encode("utf-8")
        upload = SimpleNamespace(
            filename=self.paper_file.filename,
            content_type=self.paper_file.content_type or "text/plain",
            file=BytesIO(body),
        )
        try:
            store_file_at_key(upload, self.settings, self.paper_file.storage_key, filename=self.paper_file.filename)
        except (ClientError, OSError) as error:
            self.error_message = f"Unable to save file content: {error}"
            return

        self.paper_file.size = len(body)
        self.paper_file.updated_at = utcnow()
        self.session.commit()
        self.session.refresh(self.paper_file)

    def found(self):
        return self._show_file.found()

    def to_dict(self):
        return {
            "file": self.paper_file.to_dict(),
            "editable": True,
            "content": self.content,
            "message": None,
        }

    def storage_error(self):
        return self.error_message is not None

    def conflicted(self):
        return self.conflict_message is not None

    def _validate(self):
        if not editable_paper_file(self.paper_file):
            self.payload["file"].append("not editable")

        if self.content is None:
            self.payload["content"].append("required")
        else:
            byte_size = len(self.content.encode("utf-8"))
            max_size = int(getattr(self.settings, "STORAGE_MAX_CONTENT_LENGTH_MB", 100) or 100) * 1024 * 1024
            if byte_size > max(max_size, 0):
                self.payload["content"].append("too large")

        self.count_errors()

    def _conflicted(self):
        if not self.last_known_updated_at:
            return False

        return self.paper_file.updated_at.isoformat() != self.last_known_updated_at
