"""Mensaje que EMQX envía por webhook (acción HTTP de una regla con `SELECT * FROM "..."`).

Solo se declaran los campos que se usan; el resto se ignora.
"""
from typing import Any

from pydantic import BaseModel, ConfigDict


class EmqxMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None                 # id del mensaje en EMQX (no es el de la estación)
    event: str | None = None              # "message.publish"
    clientid: str | None = None           # normalmente el código de la estación, ej "EP061"
    topic: str | None = None              # ej "RT10/EP061"
    payload: str | dict[str, Any] | None = None  # JSON de la estación (string o ya decodificado)
    publish_received_at: int | None = None  # epoch en ms (hora del broker)
    timestamp: int | None = None            # epoch en ms
