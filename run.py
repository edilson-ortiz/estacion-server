"""Lanzador para desarrollo local.

    python run.py            (equivale a: uvicorn app.main:app --reload)

En Windows, psycopg async no funciona con el ProactorEventLoop que uvicorn usa por
defecto, así que aquí se fuerza el SelectorEventLoop. En Linux (producción) se puede
seguir usando `uvicorn app.main:app` directamente.
"""
import asyncio
import os
import sys

import uvicorn

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload="--no-reload" not in sys.argv,
    )
