from app.models.paper_file import PaperFile
from app.operations.papers.access import visible_paper
from app.storage import delete_file


class DestroyFile:
    def __init__(self, session, user, settings, paper_id, paper_file_id):
        self.session = session
        self.user = user
        self.settings = settings
        self.paper_id = paper_id
        self.paper_file_id = paper_file_id
        self.paper = None
        self.paper_file = None
        self.paper_found = False
        self.paper_file_found = False

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)
        self.paper_found = self.paper is not None
        if self.paper is None:
            return

        self.paper_file = self.session.get(PaperFile, self.paper_file_id)
        self.paper_file_found = self.paper_file is not None and self.paper_file.paper_id == self.paper.id
        if not self.paper_file_found:
            return

        delete_file(self.settings, self.paper_file.storage_key)
        self.session.delete(self.paper_file)
        self.session.commit()

    def found(self):
        return self.paper_found and self.paper_file_found
