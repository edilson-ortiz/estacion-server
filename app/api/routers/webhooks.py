"""Webhooks entrantes de otros sistemas (no los usa la app móvil)."""
import hmac

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.schemas.emqx import EmqxMessage
from app.schemas.response import ResponseDTO
from app.services.ingest_service import IngestService

router = APIRouter()


async def verify_emqx_token(x_webhook_token: str | None = Header(default=None)) -> None:
    expected = settings.EMQX_WEBHOOK_TOKEN
    if not expected:
        raise HTTPException(status_code=503, detail="Webhook de EMQX no configurado.")
    if not x_webhook_token or not hmac.compare_digest(x_webhook_token, expected):
        raise HTTPException(status_code=401, detail="Token de webhook inválido.")


@router.post("/emqx", response_model=ResponseDTO[dict], dependencies=[Depends(verify_emqx_token)])
async def emqx_webhook(
    body: EmqxMessage | list[EmqxMessage] = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Recibe mensajes de EMQX (regla `SELECT * FROM "RT10/#"` + acción HTTP) y los guarda
    en datos_sensores. Acepta un mensaje o una lista de mensajes.

    Responde 200 aunque algún mensaje se ignore (payload inválido, estación no registrada):
    son errores permanentes y reintentarlos no sirve. Los ignorados se registran en el log.
    """
    mensajes = body if isinstance(body, list) else [body]
    resultado = await IngestService.ingest_emqx(db, mensajes)
    return ResponseDTO(
        success=resultado.guardados > 0 or not resultado.ignorados,
        message=f"{resultado.guardados} de {resultado.recibidos} lecturas guardadas",
        data=resultado.as_dict(),
    )
