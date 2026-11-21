"""Benutzerhandbuch: nur nach Anmeldung, aber für jede Rolle."""

import pytest

from coop_manager.users.domain import ACCOUNTING, ACCOUNTING_READONLY, ADMIN


def test_handbook_needs_login(client):
    assert client.get("/api/help").status_code == 401


@pytest.mark.parametrize("role", [ACCOUNTING, ACCOUNTING_READONLY, ADMIN])
def test_every_role_may_read_the_handbook(client, register, login, role):
    register("erika", role)
    login("erika")

    response = client.get("/api/help")

    assert response.status_code == 200
    html = response.json()["html"]
    assert '<nav class="toc">' in html
    assert 'id="k-1"' in html
