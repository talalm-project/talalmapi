from pathlib import PurePosixPath

from botocore.exceptions import ClientError
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app.models.paper_file import PaperFile
from app.operations.papers.access import visible_paper
from app.operations.validator import Validator
from app.storage import delete_file


class DestroyFolder(Validator):
    def __init__(self, session, user, settings, paper_id, path):
        super().__init__()
        self.session = session
        self.user = user
        self.settings = settings
        self.paper_id = paper_id
        self.path = path
        self.paper = None
        self.paper_files = []
        self.deleted_count = 0
        self.storage_errors = []
        self.payload = {"path": []}

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        normalized_path = _normalized_folder_path(self.path)
        if normalized_path is None:
            self.payload["path"].append("invalid")
            self.count_errors()
            return

        self.paper_files = (
            self.session.execute(
                select(PaperFile).where(
                    PaperFile.paper_id == self.paper.id,
                    PaperFile.path.like(f"{normalized_path}/%"),
                )
            )
            .scalars()
            .all()
        )
        if not self.paper_files:
            return

        for paper_file in self.paper_files:
            self._delete_storage_key(paper_file.storage_key)

        if self.storage_errors:
            return

        for paper_file in self.paper_files:
            self.session.delete(paper_file)
        self.deleted_count = len(self.paper_files)
        self.session.commit()

    def found(self):
        return self.paper is not None and bool(self.paper_files)

    def _delete_storage_key(self, storage_key):
        try:
            delete_file(self.settings, storage_key)
        except ClientError as error:
            error_code = error.response.get("Error", {}).get("Code")
            status_code = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if error_code in {"NoSuchKey", "404", "NotFound"} or status_code == 404:
                return
            self.storage_errors.append(str(error))
        except OSError as error:
            self.storage_errors.append(str(error))


def _normalized_folder_path(path):
    candidate = str(path or "").strip().replace("\\", "/").strip("/")
    if not candidate:
        return None

    parsed = PurePosixPath(candidate)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        return None

    parts = [secure_filename(part) for part in parsed.parts]
    if any(not part for part in parts):
        return None

    return "/".join(parts)
