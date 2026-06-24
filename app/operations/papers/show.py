from app.operations.papers.access import visible_paper


class Show:
    def __init__(self, session, user, paper_id):
        self.session = session
        self.user = user
        self.paper_id = paper_id
        self.paper = None

    def execute(self):
        self.paper = visible_paper(self.session, self.paper_id, self.user)

    def found(self):
        return self.paper is not None
