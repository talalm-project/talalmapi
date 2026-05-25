import factory

from app.helpers.api_helpers import build_password_hash
from app.models.connector import Connector
from app.models.embedding_config import EmbeddingConfig
from app.models.notebook import Notebook
from app.models.notebook_file import NotebookFile
from app.models.notebook_vector import NotebookVector
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
    code = factory.Sequence(lambda n: f"connector-{n}")
    name = factory.Sequence(lambda n: f"Connector {n}")
    connection_type = "local"
    local_file_path = factory.Sequence(lambda n: f"/tmp/models/model-{n}.gguf")
    embedding_local_file_path = factory.Sequence(lambda n: f"/tmp/models/embedding-{n}.gguf")
    embedding_name = factory.Sequence(lambda n: f"Embedding {n}")
    api_key = None
    data = factory.LazyAttribute(
        lambda connector: {
            "metadata": {
                "provider": connector.connection_type,
                "embeddings": {
                    "model": {
                        "name": connector.embedding_name,
                        "local_file_path": connector.embedding_local_file_path if connector.connection_type == "local" else None,
                        "embedding_size": _factory_embedding_size(connector.embedding_name),
                    },
                    "model_options": {},
                },
            }
        }
    )


class EmbeddingConfigFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = EmbeddingConfig
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    connector = factory.SubFactory(ConnectorFactory)
    provider = factory.SelfAttribute("connector.connection_type")
    model_name = factory.Sequence(lambda n: f"Embedding Model {n}")
    model_path = factory.Sequence(lambda n: f"/tmp/models/embedding-{n}.gguf")
    dimensions = 3
    distance_metric = "cosine"
    options = factory.Dict({})
    config_hash = factory.Sequence(lambda n: f"embedding-config-{n}")


class NotebookFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Notebook
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    connector = factory.SubFactory(ConnectorFactory)
    embedding_config = factory.LazyAttribute(lambda notebook: EmbeddingConfigFactory(connector=notebook.connector))
    user = factory.SelfAttribute("connector.user")
    title = factory.Sequence(lambda n: f"Notebook {n}")
    data = factory.Dict({})
    status = "active"


class NotebookFileFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = NotebookFile
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    notebook = factory.SubFactory(NotebookFactory)
    name = factory.Sequence(lambda n: f"Notebook File {n}")
    filename = factory.Sequence(lambda n: f"notebook-file-{n}.pdf")
    content_type = "application/pdf"
    byte_size = 1024
    checksum = factory.Sequence(lambda n: f"checksum-{n}")
    status = "pending"
    error_message = None
    data = factory.Dict({})


class NotebookVectorFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = NotebookVector
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"

    embedding_config = factory.SubFactory(EmbeddingConfigFactory)
    notebook = factory.LazyAttribute(
        lambda vector: NotebookFactory(
            user=vector.embedding_config.connector.user,
            connector=vector.embedding_config.connector,
        )
    )
    notebook_file = None
    chunk_index = factory.Sequence(lambda n: n)
    text = factory.Sequence(lambda n: f"Notebook vector chunk {n}")
    embedding = factory.LazyAttribute(lambda vector: [float(vector.chunk_index), 1.0, 0.0])
    metadata_ = factory.Dict({})


def _factory_embedding_size(embedding_name):
    if embedding_name is None:
        return None
    if embedding_name == "text-embedding-3-small":
        return 1536
    if embedding_name == "text-embedding-3-large":
        return 3072
    return 3
