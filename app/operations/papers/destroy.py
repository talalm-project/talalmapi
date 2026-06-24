from botocore.exceptions import ClientError
from sqlalchemy import select

from app.models.compile_job import CompileJob
from app.models.paper_file import PaperFile
from app.operations.papers.access import visible_paper
from app.storage import delete_file


class Destroy:
    def __init__(self, session, user, settings, paper_id):
        self.session = session
        self.user = user
        self.settings = settings
        self.paper_id = paper_id
        self.paper = None
        self.storage_errors = []

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        paper_files = self.session.execute(
            select(PaperFile).where(PaperFile.paper_id == self.paper.id)
        ).scalars().all()
        compile_jobs = self.session.execute(
            select(CompileJob).where(CompileJob.paper_id == self.paper.id)
        ).scalars().all()

        storage_keys = [paper_file.storage_key for paper_file in paper_files]
        for compile_job in compile_jobs:
            storage_keys.extend([compile_job.output_pdf_key, compile_job.log_key])

        for storage_key in {key for key in storage_keys if key}:
            self._delete_storage_key(storage_key)

        for paper_file in paper_files:
            self.session.delete(paper_file)
        for compile_job in compile_jobs:
            self.session.delete(compile_job)
        self.session.delete(self.paper)
        self.session.commit()

    def found(self):
        return self.paper is not None

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
