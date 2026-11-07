import pytest
from campus_assistant.config import Config
from campus_assistant.db import Database


@pytest.fixture
def db(tmp_path):
    return Database(Config(data_dir=tmp_path, fixed_now="2026-10-26T16:00:00+00:00"))
