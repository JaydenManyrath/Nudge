def test_demo_login_disabled_by_default(client):
    response = client.get("/auth/demo/manager")
    assert response.status_code == 404


def test_demo_login_manager_when_enabled(client, monkeypatch):
    monkeypatch.setenv("NUDGE_DEMO_MODE", "true")
    response = client.get("/auth/demo/manager", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard/manager")
    # session is now an authenticated manager
    assert client.get("/dashboard/manager").status_code == 200


def test_demo_login_employee_when_enabled(client, monkeypatch):
    monkeypatch.setenv("NUDGE_DEMO_MODE", "true")
    response = client.get("/auth/demo/employee", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard/employee")


def test_demo_login_unknown_role_404(client, monkeypatch):
    monkeypatch.setenv("NUDGE_DEMO_MODE", "true")
    assert client.get("/auth/demo/admin").status_code == 404


def test_login_page_shows_demo_buttons_when_enabled(client, monkeypatch):
    monkeypatch.setenv("NUDGE_DEMO_MODE", "true")
    body = client.get("/auth/login").get_data(as_text=True)
    assert "Enter as Manager" in body
    assert "Enter as Employee" in body
