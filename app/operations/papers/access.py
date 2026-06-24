from sqlalchemy import select

from app.models.paper import Paper


def visible_paper(session, paper_id, user):
    return session.scalar(
        select(Paper).where(
            Paper.id == paper_id,
            Paper.user_id == user.id,
        )
    )
