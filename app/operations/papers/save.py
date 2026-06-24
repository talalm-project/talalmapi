from copy import deepcopy

from app.models.paper import Paper
from app.operations.validator import Validator


DEFAULT_PAPER_DATA = {
    "main_file": "main.tex",
    "compiler": "pdflatex",
    "builder": "latexmk",
    "output_dir": "build",
    "phase": "phase_1",
}


class Save(Validator):
    def __init__(self, session, user, name=None, data=None, paper=None):
        super().__init__()
        self.session = session
        self.user = user
        self.name = name
        self.data = data
        self.paper = paper
        self.payload = {
            "name": [],
        }

    def execute(self):
        self._validate()

        if self.invalid():
            return

        if self.paper is None:
            self.paper = Paper(
                user_id=self.user.id,
                name=self.name.strip(),
                data=deepcopy(DEFAULT_PAPER_DATA),
            )
            self.session.add(self.paper)
        else:
            self.paper.name = self.name.strip()
            if self.data is not None:
                self.paper.data = self.data

        self.session.commit()
        self.session.refresh(self.paper)

    def _validate(self):
        if self.name is None or not self.name.strip():
            self.payload["name"].append("required")

        self.count_errors()
