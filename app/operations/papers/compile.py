from sqlalchemy import select

from app.models.compile_job import CompileJob
from app.models.paper_file import PaperFile
from app.operations.papers.access import visible_paper
from app.operations.validator import Validator
from app.services.paper_compile_service import PaperCompileService


class CreateCompileJob(Validator):
    def __init__(self, session, user, settings, paper_id):
        super().__init__()
        self.session = session
        self.user = user
        self.settings = settings
        self.paper_id = paper_id
        self.paper = None
        self.compile_job = None
        self.payload = {
            "files": [],
        }

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        file_count = self.session.scalar(select(PaperFile.id).where(PaperFile.paper_id == self.paper.id).limit(1))
        if file_count is None:
            self.payload["files"].append("required")
            self.count_errors()
            return

        self.compile_job = PaperCompileService(self.settings).create_compile_job(self.session, self.paper)

    def found(self):
        return self.paper is not None


class ShowCompileJob:
    def __init__(self, session, user, paper_id, job_id):
        self.session = session
        self.user = user
        self.paper_id = paper_id
        self.job_id = job_id
        self.paper = None
        self.compile_job = None

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        self.compile_job = self.session.scalar(
            select(CompileJob).where(
                CompileJob.id == self.job_id,
                CompileJob.paper_id == self.paper.id,
            )
        )

    def found(self):
        return self.paper is not None and self.compile_job is not None


class IndexCompileJobs:
    def __init__(self, session, user, paper_id):
        self.session = session
        self.user = user
        self.paper_id = paper_id
        self.paper = None
        self.compile_jobs = []

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        self.compile_jobs = (
            self.session.execute(
                select(CompileJob)
                .where(CompileJob.paper_id == self.paper.id)
                .order_by(CompileJob.created_at.desc())
                .limit(10)
            )
            .scalars()
            .all()
        )

    def found(self):
        return self.paper is not None

    def to_dict(self):
        return {"records": [compile_job.to_dict() for compile_job in self.compile_jobs]}
