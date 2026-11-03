import json
import os
import pytest
from pathlib import Path

from project.app import app, db

TEST_DB = "test.db"


@pytest.fixture
def client():
    BASE_DIR = Path(__file__).resolve().parent.parent
    app.config["TESTING"] = True
    app.config["DATABASE"] = BASE_DIR.joinpath(TEST_DB)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR.joinpath(TEST_DB)}"

    with app.app_context():
        db.create_all()  # setup
        yield app.test_client()  # tests run here
        db.drop_all()  # teardown


def login(client, username, password):
    """Login helper function"""
    return client.post(
        "/login",
        data=dict(username=username, password=password),
        follow_redirects=True,
    )


def logout(client):
    """Logout helper function"""
    return client.get("/logout", follow_redirects=True)


def test_index(client):
    response = client.get("/", content_type="html/text")
    assert response.status_code == 200


def test_database(client):
    """initial test. ensure that the database exists"""
    tester = Path("test.db").is_file()
    assert tester


def test_empty_db(client):
    """Ensure database is blank"""
    rv = client.get("/")
    assert b"No entries yet. Add some!" in rv.data


def test_login_logout(client):
    """Test login and logout using helper functions"""
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"])
    assert b"You were logged in" in rv.data
    rv = logout(client)
    assert b"You were logged out" in rv.data
    rv = login(client, app.config["USERNAME"] + "x", app.config["PASSWORD"])
    assert b"Invalid username" in rv.data
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"] + "x")
    assert b"Invalid password" in rv.data


def test_messages(client):
    """Ensure that user can post messages"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.post(
        "/add",
        data=dict(title="<Hello>", text="<strong>HTML</strong> allowed here"),
        follow_redirects=True,
    )
    assert b"No entries here so far" not in rv.data
    assert b"&lt;Hello&gt;" in rv.data
    assert b"<strong>HTML</strong> allowed here" in rv.data


# Note: no post is created here, so the delete matches 0 rows. That is not an
# error in SQL/SQLAlchemy, so status is still 1 once logged in. The first
# request (logged out) is rejected by login_required with status 0.
def test_delete_message(client):
    """Ensure the messages are being deleted"""
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 0
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 1


def test_search(client):
    """Ensure search works"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    client.post(
        "/add",
        data=dict(title="TESTSEARCH", text="searchable text"),
        follow_redirects=True,
    )
    rv = client.get("/search/", query_string={"query": "searchable"})
    # rv = client.get("/search/?query=searchable")
    assert b"TESTSEARCH" in rv.data

    rv = client.get("/search/", query_string={"query": "nomatch"})
    # rv = client.get("/search/?query=nomatch")
    assert b"TESTSEARCH" not in rv.data


def test_login_required(client):
    """Ensure deleting without logging in is blocked"""
    rv = client.get("/delete/1")
    assert rv.status_code == 401
    data = json.loads(rv.data)
    assert data["status"] == 0
    assert data["message"] == "Please log in."


def test_delete_removes_post(client):
    """Ensure a logged-in user can delete a post"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    client.post("/add", data=dict(title="DELETEME", text="x"), follow_redirects=True)
    client.get("/delete/1")
    rv = client.get("/")
    assert b"DELETEME" not in rv.data
