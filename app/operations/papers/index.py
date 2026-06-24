from sqlalchemy import select

from app.models.paper import Paper


class Index:
    def __init__(self, session, user):
        self.session = session
        self.user = user
        self.papers = []

    def execute(self):
        self.papers = (
            self.session.execute(
                select(Paper)
                .where(Paper.user_id == self.user.id)
                .order_by(Paper.created_at.desc())
            )
            .scalars()
            .all()
        )

    def to_dict(self):
        return {
            "records": [paper.to_dict() for paper in self.papers],
        }
