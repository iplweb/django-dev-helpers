def test_post_to_autologin_returns_405(client, admin_user, autologin_token):
    url = f"/__autologin__/?token={autologin_token}"
    response = client.post(url)
    assert response.status_code == 405


def test_put_to_autologin_returns_405(client, admin_user, autologin_token):
    url = f"/__autologin__/?token={autologin_token}"
    response = client.put(url)
    assert response.status_code == 405


def test_delete_to_autologin_returns_405(client, admin_user, autologin_token):
    url = f"/__autologin__/?token={autologin_token}"
    response = client.delete(url)
    assert response.status_code == 405


def test_get_still_works(client, admin_user, autologin_token):
    url = f"/__autologin__/?token={autologin_token}"
    response = client.get(url)
    assert response.status_code == 302
