import pytest
import mongomock
from pathlib import Path


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def mongo_client():
    client = mongomock.MongoClient()
    yield client
    client.close()


@pytest.fixture
def db(mongo_client):
    return mongo_client["image_mover_test"]
