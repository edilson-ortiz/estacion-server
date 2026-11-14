"""Ingesta de lecturas de estaciones que llegan por webhook desde EMQX.

Reemplaza al cliente MQTT (paho) que escuchaba el broker e insertaba en datos_sensores.
Se mantiene el mismo mapeo de campos y la misma normalización (faltante → 0) para que
los datos queden iguales a los que ya hay y la app no note diferencia.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utcnow
from app.models import Estacion, SensorData
from app.schemas.emqx import EmqxMessage

logger = logging.getLogger(__name__)

# Clave en el JSON de la estación → columna en datos_sensores
CAMPOS_PAYLOAD = {
    "t": "temperatura",
    "h": "humedad",
    "r": "lluvia",               # pulsos crudos; se convierte a mm al leer (calibracion.py)
    "wd": "direccion_viento",
    "ws_avg": "velocidad_viento",
    "ws_gust": "rafaga_viento",
    "bar": "presion_barometrica",
}

# Igual que el cliente MQTT anterior: si la estación no envía un valor, se guarda 0
VALOR_FALTANTE = 0.0


@dataclass
class Lectura:
    sensor_id: str
    fecha: datetime
    valores: dict[str, float] = field(default_factory=dict)


@dataclass
class ResultadoIngesta:
    recibidos: int = 0
    guardados: int = 0
    ignorados: list[dict[str, Any]] = field(default_factory=list)

    def ignorar(self, mensaje: EmqxMessage, motivo: str) -> None:
        self.ignorados.append({"id": mensaje.id, "clientid": mensaje.clientid, "motivo": motivo})
        logger.warning("Webhook EMQX: mensaje ignorado (%s) id=%s clientid=%s topic=%s",
                       motivo, mensaje.id, mensaje.clientid, mensaje.topic)

    def as_dict(self) -> dict[str, Any]:
        return {"recibidos": self.recibidos, "guardados": self.guardados, "ignorados": self.ignorados}


def _to_float(valor: Any) -> float | None:
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return None
    return numero if math.isfinite(numero) else None


def _fecha_mensaje(mensaje: EmqxMessage) -> datetime:
    """Hora en que el broker recibió el mensaje (más exacta que la hora de inserción)."""
    ms = mensaje.publish_received_at or mensaje.timestamp
    if ms:
        try:
            return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            pass
    return utcnow()


def parse_mensaje(mensaje: EmqxMessage) -> Lectura:
    """Convierte un mensaje de EMQX en una Lectura. Lanza ValueError si no es válido."""
    if mensaje.event and mensaje.event != "message.publish":
        raise ValueError(f"evento no soportado: {mensaje.event}")

    payload = mensaje.payload
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ValueError("payload no es JSON válido") from exc
    if not isinstance(payload, dict):
        raise ValueError("payload vacío o con formato inesperado")

    sensor_id = payload.get("id") or mensaje.clientid
    if not sensor_id or not isinstance(sensor_id, str):
        raise ValueError("payload sin id de estación")

    valores = {}
    for clave, columna in CAMPOS_PAYLOAD.items():
        numero = _to_float(payload.get(clave))
        valores[columna] = VALOR_FALTANTE if numero is None else numero

    return Lectura(sensor_id=sensor_id.strip(), fecha=_fecha_mensaje(mensaje), valores=valores)


class IngestService:

    @staticmethod
    async def ingest_emqx(db: AsyncSession, mensajes: list[EmqxMessage]) -> ResultadoIngesta:
        resultado = ResultadoIngesta(recibidos=len(mensajes))

        lecturas: list[tuple[EmqxMessage, Lectura]] = []
        for mensaje in mensajes:
            try:
                lecturas.append((mensaje, parse_mensaje(mensaje)))
            except ValueError as exc:
                resultado.ignorar(mensaje, str(exc))

        if not lecturas:
            return resultado

        # Solo estaciones registradas (datos_sensores.sensor_id es FK a estacion.codigo)
        codigos = {lectura.sensor_id for _, lectura in lecturas}
        existentes = set(
            (await db.execute(select(Estacion.codigo).where(Estacion.codigo.in_(codigos)))).scalars()
        )

        for mensaje, lectura in lecturas:
            if lectura.sensor_id not in existentes:
                resultado.ignorar(mensaje, f"estación no registrada: {lectura.sensor_id}")
                continue
            db.add(SensorData(sensor_id=lectura.sensor_id, fecha=lectura.fecha, **lectura.valores))
            resultado.guardados += 1

        if resultado.guardados:
            await db.commit()
        return resultado
