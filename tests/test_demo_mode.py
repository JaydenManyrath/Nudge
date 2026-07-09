def test_demo_login_disabled_by_default(client):
    response = client.get("/auth/demo/manager")
    assert response.status_code == 404


def test_demo_login_manager_stays_disabled_when_env_set(client, monkeypatch):
    monkeypatch.setenv("NUDGE_DEMO_MODE", "true")
    response = client.get("/auth/demo/manager")
    assert response.status_code == 404


def test_demo_login_employee_stays_disabled_when_env_set(client, monkeypatch):
    monkeypatch.setenv("NUDGE_DEMO_MODE", "true")
    response = client.get("/auth/demo/employee")
    assert response.status_code == 404


def test_demo_login_unknown_role_404(client, monkeypatch):
    monkeypatch.setenv("NUDGE_DEMO_MODE", "true")
    assert client.get("/auth/demo/admin").status_code == 404


def test_login_page_does_not_show_demo_buttons_when_env_set(client, monkeypatch):
    monkeypatch.setenv("NUDGE_DEMO_MODE", "true")
    body = client.get("/auth/login").get_data(as_text=True)
    assert "Try it instantly" not in body
    assert "Enter as Manager" not in body
    assert "Enter as Employee" not in body
