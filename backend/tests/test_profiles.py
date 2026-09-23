"""Perfiles: la cabecera X-Profile-Id aísla los datos de cada persona."""

from __future__ import annotations

from tests.conftest import needs_db


@needs_db
def test_profile_header_isolates_data_and_delete_cascades(client):
    default_before = client.get("/api/v1/preferences").json().get("notice_period")
    created = client.post("/api/v1/profiles", json={"full_name": "Perfil de prueba"})
    assert created.status_code == 201
    profile_id = created.json()["id"]
    headers = {"X-Profile-Id": str(profile_id)}

    try:
        assert client.get("/api/v1/profiles/current", headers=headers).json()["id"] == profile_id
        # Perfil recién creado: sin CV ni postulaciones, aunque el por defecto tenga.
        assert client.get("/api/v1/resumes", headers=headers).json() == []
        assert client.get("/api/v1/applications", headers=headers).json() == []

        marker = "preaviso-de-prueba-xyz"
        saved = client.put("/api/v1/preferences", json={"notice_period": marker}, headers=headers)
        assert saved.json()["notice_period"] == marker
        # Las preferencias son del perfil: el por defecto no se entera.
        assert client.get("/api/v1/preferences").json().get("notice_period") == default_before
    finally:
        assert client.delete(f"/api/v1/profiles/{profile_id}").status_code == 204

    gone = client.get("/api/v1/resumes", headers=headers)
    assert gone.status_code == 404
    assert gone.json()["code"] == "profile_not_found"


@needs_db
def test_default_profile_cannot_be_deleted(client):
    default = next(p for p in client.get("/api/v1/profiles").json() if p["is_default"])
    assert client.delete(f"/api/v1/profiles/{default['id']}").status_code == 400
