from sqlalchemy import select

from app.models.paper_file import PaperFile
from app.operations.papers.access import visible_paper


class IndexFiles:
    def __init__(self, session, user, paper_id):
        self.session = session
        self.user = user
        self.paper_id = paper_id
        self.paper = None
        self.paper_files = []

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        if self.paper is None:
            return

        self.paper_files = (
            self.session.execute(
                select(PaperFile)
                .where(PaperFile.paper_id == self.paper.id)
                .order_by(PaperFile.created_at.desc())
            )
            .scalars()
            .all()
        )

    def found(self):
        return self.paper is not None

    def to_dict(self):
        return {"records": [paper_file.to_dict() for paper_file in self.paper_files]}
