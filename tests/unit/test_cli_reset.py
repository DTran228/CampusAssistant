import pytest
from campus_assistant.cli import main
from campus_assistant.config import Config
from campus_assistant.db import Database


def test_reset_refuses_unmarked_private_workspace(db, monkeypatch):
    profile = db.create_profile()
    monkeypatch.setattr("sys.argv", ["campus-scout", "--data-dir", str(db.config.data_dir), "demo-reset"])
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
    assert db.require_profile(profile)


def test_explicit_disposable_reset_is_repeatable(tmp_path, monkeypatch):
    directory = tmp_path / "disposable"
    monkeypatch.setattr("sys.argv", ["campus-scout", "--data-dir", str(directory), "demo-reset"])
    main()
    db = Database(Config(data_dir=directory))
    db.create_profile()
    main()
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 6
