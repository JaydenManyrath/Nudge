def test_login_required_routes_redirect_when_unauthenticated(client):
    response = client.get("/review/")

    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
