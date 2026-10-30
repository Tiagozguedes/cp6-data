from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import compras, eventos, relatorios
from app.database import criar_indices, db, r


@asynccontextmanager
async def lifespan(app: FastAPI):
    criar_indices()
    yield


app = FastAPI(
    title="TicketFlash API",
    description="Plataforma de ingressos com MongoDB (fonte da verdade) e Redis (cache, reservas, ranking e limite).",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(eventos.router)
app.include_router(compras.router)
app.include_router(relatorios.router)


@app.get("/", tags=["Status"])
def status():
    return {
        "api": "TicketFlash",
        "mongo": db.command("ping")["ok"] == 1,
        "redis": r.ping(),
        "docs": "/docs",
    }
