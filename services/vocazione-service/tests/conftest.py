import pytest
from fastapi.testclient import TestClient

from src.app import app


@pytest.fixture
def client():
    # A non-context-managed TestClient: the lifespan hook (catalog
    # self-registration) deliberately does NOT fire, so no test ever touches a
    # database. This Widget has no JWT guard and no data route, so — unlike the
    # reuse/demographic services — there is no token machinery to set up here.
    return TestClient(app)
