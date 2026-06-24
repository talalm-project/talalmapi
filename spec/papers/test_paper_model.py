from app.models.paper import Paper
from spec.factories import PaperFactory, UserFactory


def test_paper_factory_creates_paper(db_session):
    paper = PaperFactory(name="Attention Is All You Need", data={"venue": "NeurIPS"})

    assert paper.id is not None
    assert paper.name == "Attention Is All You Need"
    assert paper.data == {"venue": "NeurIPS"}
    assert paper.user_id == paper.user.id
    assert paper.created_at is not None
    assert paper.updated_at is not None


def test_paper_defaults(db_session):
    user = UserFactory()
    paper = Paper(name="Defaulted Paper", user=user)

    db_session.add(paper)
    db_session.commit()

    assert paper.data == {}


def test_paper_to_dict_returns_public_fields(db_session):
    paper = PaperFactory(name="Research Paper", data={"authors": ["Ada"]})

    assert paper.to_dict() == {
        "id": paper.id,
        "user_id": paper.user_id,
        "name": "Research Paper",
        "data": {"authors": ["Ada"]},
    }
