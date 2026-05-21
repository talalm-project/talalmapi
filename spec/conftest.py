import os
import pytest
from fastapi.testclient import TestClient

from app import create_app
from app.db import Base, db
from app.helpers.api_helpers import build_jwt_header, generate_jwt
from spec.factories import ConnectorFactory, NotebookFactory, UserFactory


@pytest.fixture()
def app():
    os.environ["APP_ENV"] = "test"
    application = create_app("spec.settings.TestConfig")
    Base.metadata.create_all(bind=db.engine)
    yield application
    Base.metadata.drop_all(bind=db.engine)


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def db_session(app):
    session = db.session()
    ConnectorFactory._meta.sqlalchemy_session = session
    NotebookFactory._meta.sqlalchemy_session = session
    UserFactory._meta.sqlalchemy_session = session
    yield session
    session.close()
    ConnectorFactory._meta.sqlalchemy_session = None
    NotebookFactory._meta.sqlalchemy_session = None
    UserFactory._meta.sqlalchemy_session = None


@pytest.fixture()
def auth_headers(app, db_session):
    user = UserFactory(status="active", role="admin")
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)


@pytest.fixture()
def user_auth_headers(app, db_session):
    user = UserFactory(status="active", role="user")
    token = generate_jwt(user.to_dict(), app.state.settings.SECRET_KEY)
    return build_jwt_header(token)
