"""Factores de calibración del pluviómetro (pulsos → mm).

Cada estación tiene una lista de factores con fecha de vigencia. Para una lectura se usa
el último factor cuya `vigente_desde` sea <= a la fecha de la lectura; si no hay ninguno,
se usa DEFAULT_FACTOR_K.

`Calibracion` permite aplicar esa regla de dos formas equivalentes:
  - en memoria, para una fecha puntual (`factor_en`)
  - dentro de SQL, como expresión CASE (`factor_sql`), para que PostgreSQL haga
    `SUM(lluvia * factor)` sin traer cada fila a Python.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import case, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.core.time import ensure_aware
from app.models import CalibracionPluviometro

DEFAULT_FACTOR_K = 0.1


@dataclass
class Calibracion:
    fechas: list[datetime] = field(default_factory=list)  # ordenadas ASC, con tz
    factores: list[float] = field(default_factory=list)

    @classmethod
    def from_rows(cls, rows: Iterable[tuple[datetime, float]]) -> Calibracion:
        cal = cls()
        for vigente_desde, factor_k in rows:
            cal.fechas.append(ensure_aware(vigente_desde))
            cal.factores.append(factor_k)
        return cal

    def factor_en(self, fecha: datetime) -> float:
        """Factor vigente para `fecha` (búsqueda binaria)."""
        idx = bisect_right(self.fechas, ensure_aware(fecha)) - 1
        return self.factores[idx] if idx >= 0 else DEFAULT_FACTOR_K

    def factor_sql(self, columna_fecha: ColumnElement) -> ColumnElement:
        """Expresión SQL con el factor vigente para cada fila según `columna_fecha`."""
        if not self.fechas:
            return literal(DEFAULT_FACTOR_K)
        # Del más reciente al más antiguo: el primer WHEN que cumple es el vigente
        whens = [
            (columna_fecha >= fecha, literal(factor))
            for fecha, factor in zip(reversed(self.fechas), reversed(self.factores), strict=True)
        ]
        return case(*whens, else_=literal(DEFAULT_FACTOR_K))


def _query(codigos: list[str]):
    return (
        select(
            CalibracionPluviometro.estacion_codigo,
            CalibracionPluviometro.vigente_desde,
            CalibracionPluviometro.factor_k,
        )
        .where(CalibracionPluviometro.estacion_codigo.in_(codigos))
        .order_by(CalibracionPluviometro.vigente_desde.asc())
    )


async def load_calibracion(db: AsyncSession, codigo: str) -> Calibracion:
    result = await db.execute(_query([codigo]))
    return Calibracion.from_rows((r.vigente_desde, r.factor_k) for r in result)


async def load_calibraciones(db: AsyncSession, codigos: Iterable[str]) -> dict[str, Calibracion]:
    """Carga las calibraciones de varias estaciones en una sola consulta."""
    codigos = list(set(codigos))
    if not codigos:
        return {}
    result = await db.execute(_query(codigos))
    por_estacion: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    for r in result:
        por_estacion[r.estacion_codigo].append((r.vigente_desde, r.factor_k))
    return {c: Calibracion.from_rows(por_estacion.get(c, [])) for c in codigos}
