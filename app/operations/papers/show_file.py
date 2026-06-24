from sqlalchemy import select

from app.models.paper_file import PaperFile
from app.operations.papers.access import visible_paper


class ShowFile:
    def __init__(self, session, user, paper_id, paper_file_id):
        self.session = session
        self.user = user
        self.paper_id = paper_id
        self.paper_file_id = paper_file_id
        self.paper = None
        self.paper_file = None

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        self.paper_file = self.session.scalar(
            select(PaperFile).where(
                PaperFile.id == self.paper_file_id,
                PaperFile.paper_id == self.paper.id,
            )
        )

    def found(self):
        return self.paper is not None and self.paper_file is not None
