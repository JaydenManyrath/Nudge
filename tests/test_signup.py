import models


def test_signup_creates_employee_and_logs_in(client):
    response = client.post(
        "/auth/signup",
        data={"name": "New Person", "email": "new@example.com", "password": "secret123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard/employee")

    # logged in as an employee: own dashboard works, manager pages are blocked
    assert client.get("/dashboard/employee").status_code == 200
    assert client.get("/dashboard/manager").status_code == 403

    with models.get_db() as db:
        row = db.execute(
            "SELECT role FROM users WHERE email = ?", ("new@example.com",)
        ).fetchone()
    assert row is not None
    assert row["role"] == "employee"


def test_signup_rejects_duplicate_email(client):
    client.post(
        "/auth/signup",
        data={"name": "A", "email": "dup@example.com", "password": "secret123"},
    )
    response = client.post(
        "/auth/signup",
        data={"name": "B", "email": "dup@example.com", "password": "secret123"},
    )
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_signup_rejects_short_password(client):
    response = client.post(
        "/auth/signup",
        data={"name": "Short", "email": "short@example.com", "password": "123"},
    )
    assert response.status_code == 400
    assert b"at least 6" in response.data


def test_signed_up_user_can_log_in(client):
    client.post(
        "/auth/signup",
        data={"name": "Log Me", "email": "loginme@example.com", "password": "mypassword"},
    )
    client.get("/auth/logout")
    response = client.post(
        "/auth/login",
        data={"email": "loginme@example.com", "password": "mypassword"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard/employee")
