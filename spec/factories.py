import factory

from app.helpers.api_helpers import build_password_hash
from app.models.connector import Connector
from app.models.user import User


class UserFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = User
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    first_name = factory.Sequence(lambda n: f"First{n}")
    last_name = factory.Sequence(lambda n: f"Last{n}")
    password_hash = factory.LazyFunction(lambda: build_password_hash("password"))
    status = "active"
    role = "user"


class ConnectorFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Connector
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    user = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Connector {n}")
    connection_type = "local"
    local_file_path = factory.Sequence(lambda n: f"/tmp/models/model-{n}.gguf")
    api_key = None
    data = factory.Dict({})
