import os
import sys
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import create_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["GROQ_API_KEY"] = ""
os.environ["DATABASE_URL"] = ""

from app import db  # noqa: E402
from app.services import llm  # noqa: E402


class NoLLM(llm.ModelRouter):
    def available(self):
        return False

    def guard(self, text):
        return None


@pytest.fixture(autouse=True)
def isolated():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    db.set_engine(engine)
    llm.set_router(NoLLM())
    yield
    llm.set_router(None)


@pytest.fixture
def graph():
    from langgraph.checkpoint.memory import InMemorySaver

    from app.graph import journey

    g = journey.build_graph(InMemorySaver())
    journey.set_graph(g)
    yield g
    journey.set_graph(None)
