import os
import pytest
import mongomock
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_PLUGIN_PATH", "/opt/anaconda3/lib/python3.13/site-packages/PyQt6/Qt6/plugins")


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
