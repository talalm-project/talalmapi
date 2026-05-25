from app.models.notebook import Notebook


def visible_notebook(session, notebook_id, current_user, admin_allowed=True):
    notebook = session.get(Notebook, notebook_id)
    if notebook is None:
        return None
    if admin_allowed and current_user.role == "admin":
        return notebook
    if notebook.user_id != current_user.id:
        return None

    return notebook
