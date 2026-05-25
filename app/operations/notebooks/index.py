from sqlalchemy import func, or_, select

from app.models.notebook import Notebook
from app.operations.notebooks.ensure_embedding_configs import EnsureEmbeddingConfigs


ITEMS_PER_PAGE = 15


class Index:
    def __init__(self, session, user, query=None, title=None, status=None, page=1):
        self.session = session
        self.user = user
        self.query = query
        self.title = title
        self.status = status
        self.page = max(page, 1)
        self.notebooks = []
        self.total_pages = 1
        self.next_page = None
        self.prev_page = None

    def execute(self):
        filters = [Notebook.user_id == self.user.id]

        if self.query:
            pattern = f"%{self.query}%"
            filters.append(or_(Notebook.title.ilike(pattern), Notebook.status.ilike(pattern)))
        if self.title:
            filters.append(Notebook.title.ilike(f"%{self.title}%"))
        if self.status:
            filters.append(Notebook.status == self.status)

        count_stmt = select(func.count()).select_from(Notebook)
        notebooks_stmt = select(Notebook).order_by(Notebook.created_at.desc())
        for entry in filters:
            count_stmt = count_stmt.where(entry)
            notebooks_stmt = notebooks_stmt.where(entry)

        total = self.session.scalar(count_stmt) or 0
        self.total_pages = max((total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE, 1)
        self.notebooks = (
            self.session.execute(
                notebooks_stmt.offset((self.page - 1) * ITEMS_PER_PAGE).limit(ITEMS_PER_PAGE)
            )
            .scalars()
            .all()
            if total > 0
            else []
        )
        EnsureEmbeddingConfigs(self.session, self.notebooks).execute()
        self.next_page = self.page + 1 if self.page < self.total_pages else None
        self.prev_page = self.page - 1 if self.page > 1 else None

    def to_dict(self):
        return {
            "records": [notebook.to_dict() for notebook in self.notebooks],
            "total_pages": self.total_pages,
            "current_page": self.page,
            "next_page": self.next_page,
            "prev_page": self.prev_page,
        }
