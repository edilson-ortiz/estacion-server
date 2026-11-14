"""Pruebas del webhook de EMQX. Usan una sesión de BD falsa: no tocan la base de datos."""
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import SensorData
from app.schemas.emqx import EmqxMessage
from app.services.ingest_service import parse_mensaje

TOKEN = "token-de-prueba"
URL = "/webhooks/emqx"

# Body real enviado por EMQX (capturado en n8n)
MENSAJE_REAL = {
    "publish_received_at": 1794616056056,
    "pub_props": {"User-Property": {}},
    "qos": 0,
    "topic": "RT10/EP061",
    "client_attrs": {},
    "clientid": "EP061",
    "peerhost": "166.114.157.77",
    "payload": "{\"id\":\"EP061\",\"t\":29.70,\"h\":78.40,\"r\":0}",
    "username": "undefined",
    "event": "message.publish",
    "metadata": {"rule_id": "WH_IAGRO_WH_D"},
    "peername": "166.114.157.77:53088",
    "timestamp": 1794616056056,
    "node": "emqx@172.17.0.2",
    "id": "000660319C8788C1F7A7027170F30002",
    "flags": {"retain": False, "dup": False},
}


class _Result:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return iter(self._values)


class FakeSession:
    """Simula AsyncSession: conoce un set de estaciones y guarda lo que se agrega."""

    def __init__(self, estaciones):
        self.estaciones = set(estaciones)
        self.added = []
        self.commits = 0

    async def execute(self, stmt):
        codigos = stmt.whereclause.right.value  # codigo IN (...)
        return _Result([c for c in codigos if c in self.estaciones])

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(settings, "EMQX_WEBHOOK_TOKEN", TOKEN)
    session = FakeSession({"EP061", "EP999"})

    async def override():
        yield session

    app.dependency_overrides[get_db] = override
    yield session
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


def post(client, body, token=TOKEN):
    headers = {"X-Webhook-Token": token} if token is not None else {}
    return client.post(URL, json=body, headers=headers)


# ---------------- Autenticación ----------------

def test_sin_token_401(client, db):
    r = post(client, MENSAJE_REAL, token=None)
    assert r.status_code == 401
    assert r.json() == {"success": False, "message": "Token de webhook inválido.", "data": None}
    assert db.added == []


def test_token_incorrecto_401(client, db):
    assert post(client, MENSAJE_REAL, token="otro").status_code == 401
    assert db.added == []


def test_webhook_sin_configurar_503(client, monkeypatch):
    monkeypatch.setattr(settings, "EMQX_WEBHOOK_TOKEN", "")
    assert post(client, MENSAJE_REAL).status_code == 503


# ---------------- Ingesta ----------------

def test_mensaje_real_se_guarda(client, db):
    r = post(client, MENSAJE_REAL)
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True
    assert body["data"] == {"recibidos": 1, "guardados": 1, "ignorados": []}
    assert db.commits == 1

    (fila,) = db.added
    assert isinstance(fila, SensorData)
    assert fila.sensor_id == "EP061"
    assert fila.temperatura == 29.70
    assert fila.humedad == 78.40
    assert fila.lluvia == 0
    # Campos que esta estación no envía → 0, igual que el cliente MQTT anterior
    assert fila.velocidad_viento == 0
    assert fila.direccion_viento == 0
    assert fila.rafaga_viento == 0
    assert fila.presion_barometrica == 0
    # Hora del broker, no la de inserción
    assert fila.fecha == datetime.fromtimestamp(1794616056.056, tz=timezone.utc)


def test_estacion_con_viento_y_presion(client, db):
    payload = {"id": "EP999", "t": "21.5", "h": 60, "r": 3, "wd": 180, "ws_avg": 4.2, "ws_gust": 9.1, "bar": 1013.2}
    r = post(client, {**MENSAJE_REAL, "clientid": "EP999", "payload": json.dumps(payload)})
    assert r.json()["data"]["guardados"] == 1
    fila = db.added[0]
    assert (fila.temperatura, fila.direccion_viento, fila.velocidad_viento, fila.rafaga_viento, fila.presion_barometrica) \
        == (21.5, 180, 4.2, 9.1, 1013.2)


def test_estacion_no_registrada_se_ignora_con_200(client, db):
    msg = {**MENSAJE_REAL, "clientid": "XX1", "payload": "{\"id\":\"XX1\",\"t\":1}"}
    r = post(client, msg)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["guardados"] == 0
    assert data["ignorados"][0]["motivo"] == "estación no registrada: XX1"
    assert db.added == [] and db.commits == 0


def test_payload_invalido_se_ignora(client, db):
    r = post(client, {**MENSAJE_REAL, "payload": "esto no es json"})
    assert r.status_code == 200
    assert r.json()["data"]["ignorados"][0]["motivo"] == "payload no es JSON válido"
    assert db.added == []


def test_lista_de_mensajes(client, db):
    otro = {**MENSAJE_REAL, "payload": "{\"id\":\"EP999\",\"t\":10}"}
    malo = {**MENSAJE_REAL, "payload": "{\"t\":10}", "clientid": None}
    r = post(client, [MENSAJE_REAL, otro, malo])
    data = r.json()["data"]
    assert (data["recibidos"], data["guardados"], len(data["ignorados"])) == (3, 2, 1)
    assert db.commits == 1  # un solo commit para todo el lote


# ---------------- Parseo ----------------

def test_payload_ya_decodificado():
    lectura = parse_mensaje(EmqxMessage(payload={"id": "EP061", "t": 1.5}))
    assert lectura.sensor_id == "EP061" and lectura.valores["temperatura"] == 1.5


def test_sin_id_en_payload_usa_clientid():
    lectura = parse_mensaje(EmqxMessage(clientid="EP061", payload="{\"t\":1}"))
    assert lectura.sensor_id == "EP061"


def test_valores_no_numericos_quedan_en_0():
    lectura = parse_mensaje(EmqxMessage(payload={"id": "EP061", "t": "abc", "h": None, "r": float("nan")}))
    assert lectura.valores["temperatura"] == 0
    assert lectura.valores["humedad"] == 0
    assert lectura.valores["lluvia"] == 0


def test_evento_distinto_de_publish():
    with pytest.raises(ValueError, match="evento no soportado"):
        parse_mensaje(EmqxMessage(event="client.connected", payload={"id": "EP061"}))
