# 8) Create a new model (example: Project)

## 8.1 Add the model
Create `app/models/project.py`:
```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
```

Import it in `app/models/__init__.py` so Alembic sees it.

## 8.2 Generate the migration
```bash
python -m app.cli db:migrate --message "add projects"
python -m app.cli db:upgrade
```

## 8.3 Add a factory for specs
```python
import factory

from app.models.project import Project


class ProjectFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Project
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    name = factory.Sequence(lambda n: f"Project {n}")
```
