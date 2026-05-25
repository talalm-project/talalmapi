import hashlib
from pathlib import Path

from app.models.notebook_file import NotebookFile, generate_object_key
from app.operations.notebooks.access import visible_notebook
from app.operations.validator import Validator
from app.storage import store_file_at_key


SUPPORTED_NOTEBOOK_FILE_EXTENSIONS = {".docx", ".xlsx", ".txt", ".pdf", ".pptx"}


class CreateFile(Validator):
    def __init__(self, session, user, settings, notebook_id, name=None, file=None):
        super().__init__()
        self.session = session
        self.user = user
        self.settings = settings
        self.notebook_id = notebook_id
        self.name = name
        self.file = file
        self.notebook = None
        self.notebook_file = None
        self.payload = {
            "name": [],
            "file": [],
        }

    def execute(self):
        self.notebook = visible_notebook(self.session, self.notebook_id, self.user)
        if self.notebook is None:
            return

        self._validate()
        if self.invalid():
            return

        byte_size, checksum = _file_details(self.file)
        object_key = generate_object_key()
        stored_file = store_file_at_key(self.file, self.settings, object_key, filename=self.file.filename)

        self.notebook_file = NotebookFile(
            notebook_id=self.notebook.id,
            name=self.name.strip(),
            filename=stored_file["filename"],
            content_type=stored_file["content_type"],
            byte_size=byte_size,
            object_key=stored_file["key"],
            checksum=checksum,
            data={"url": stored_file["url"]},
        )
        self.session.add(self.notebook_file)
        self.session.commit()
        self.session.refresh(self.notebook_file)

    def found(self):
        return self.notebook is not None

    def _validate(self):
        if self.name is None or not self.name.strip():
            self.payload["name"].append("required")

        extension = Path(self.file.filename or "").suffix.lower()
        if extension not in SUPPORTED_NOTEBOOK_FILE_EXTENSIONS:
            self.payload["file"].append("unsupported file type")

        self.count_errors()


def _file_details(file):
    file.file.seek(0)
    digest = hashlib.sha256()
    byte_size = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        byte_size += len(chunk)
        digest.update(chunk)

    file.file.seek(0)
    return byte_size, digest.hexdigest()
