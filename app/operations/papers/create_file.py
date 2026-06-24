from pathlib import PurePosixPath

from sqlalchemy import select
from werkzeug.utils import secure_filename

from app.models.paper_file import PaperFile
from app.operations.papers.access import visible_paper
from app.operations.validator import Validator
from app.storage import store_file_at_key


SOURCE_EXTENSIONS = {".bib", ".cls", ".sty", ".tex"}
ASSET_EXTENSIONS = {".gif", ".jpeg", ".jpg", ".pdf", ".png", ".svg", ".webp"}
DEFAULT_MAX_FILE_BYTE_SIZE = 100 * 1024 * 1024


class CreateFile(Validator):
    def __init__(self, session, user, settings, paper_id, file=None, path=None):
        super().__init__()
        self.session = session
        self.user = user
        self.settings = settings
        self.paper_id = paper_id
        self.file = file
        self.path = path
        self.paper = None
        self.paper_file = None
        self.normalized_path = None
        self.filename = None
        self.payload = {
            "file": [],
            "path": [],
        }

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        byte_size = _file_size(self.file)
        self._validate(byte_size)
        if self.invalid():
            return

        storage_key = f"papers/{self.paper.id}/{self.normalized_path}"
        stored_file = store_file_at_key(self.file, self.settings, storage_key, filename=self.filename)
        self.paper_file = PaperFile(
            paper_id=self.paper.id,
            path=self.normalized_path,
            filename=stored_file["filename"],
            content_type=stored_file["content_type"],
            size=byte_size,
            storage_key=stored_file["key"],
        )
        self.session.add(self.paper_file)
        self.session.commit()
        self.session.refresh(self.paper_file)

    def found(self):
        return self.paper is not None

    def _validate(self, byte_size):
        if self.file is None:
            self.payload["file"].append("required")
            self.count_errors()
            return

        self.filename = secure_filename(self.file.filename or "") or "file"
        self.normalized_path = _normalized_project_path(self.path, self.filename)
        if self.normalized_path is None:
            self.payload["path"].append("invalid")

        max_size = int(getattr(self.settings, "STORAGE_MAX_CONTENT_LENGTH_MB", 100) or 100) * 1024 * 1024
        if byte_size > max(max_size, 0):
            self.payload["file"].append("too large")

        if self.normalized_path is not None and self._path_taken():
            self.payload["path"].append("already taken")

        self.count_errors()

    def _path_taken(self):
        return self.session.scalar(
            select(PaperFile.id).where(
                PaperFile.paper_id == self.paper.id,
                PaperFile.path == self.normalized_path,
            )
        ) is not None


def _file_size(file):
    if file is None:
        return 0

    file.file.seek(0)
    byte_size = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        byte_size += len(chunk)

    file.file.seek(0)
    return byte_size


def _normalized_project_path(path, filename):
    candidate = str(path or "").strip().replace("\\", "/")
    if not candidate:
        extension = PurePosixPath(filename).suffix.lower()
        root = "assets" if extension in ASSET_EXTENSIONS else "source"
        candidate = f"{root}/{filename}"

    parsed = PurePosixPath(candidate)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        return None

    parts = [secure_filename(part) for part in parsed.parts]
    if any(not part for part in parts):
        return None

    if len(parts) == 1:
        extension = PurePosixPath(parts[0]).suffix.lower()
        root = "assets" if extension in ASSET_EXTENSIONS else "source"
        parts.insert(0, root)

    return "/".join(parts)
