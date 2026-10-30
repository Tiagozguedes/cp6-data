"""Relatórios com Aggregation Pipeline (Req. 4): todo o cálculo é feito no MongoDB."""
from fastapi import APIRouter, HTTPException

from app.database import db
from app.utils import para_object_id, serializar

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


@router.get("/faturamento")
def faturamento_por_evento():
    pipeline = [
        {"$match": {"status": "confirmado"}},
        {
            "$group": {
                "_id": "$eventoId",
                "faturamento": {"$sum": "$valorTotal"},
                "pedidos": {"$sum": 1},
                "ingressos": {"$sum": "$quantidade"},
            }
        },
        {
            "$lookup": {
                "from": "eventos",
                "localField": "_id",
                "foreignField": "_id",
                "as": "evento",
            }
        },
        {"$unwind": "$evento"},
        {
            "$project": {
                "_id": 0,
                "eventoId": "$_id",
                "evento": "$evento.nome",
                "faturamento": {"$round": ["$faturamento", 2]},
                "pedidos": 1,
                "ingressos": 1,
            }
        },
        {"$sort": {"faturamento": -1}},
    ]
    return serializar(list(db.pedidos.aggregate(pipeline)))


@router.get("/ocupacao/{evento_id}")
def ocupacao_por_setor(evento_id: str):
    oid = para_object_id(evento_id)
    pipeline = [
        {"$match": {"_id": oid}},
        {"$unwind": "$setores"},  # um documento por setor
        {
            "$project": {
                "_id": 0,
                "evento": "$nome",
                "setor": "$setores.nome",
                "capacidade": "$setores.capacidade",
                "vendidos": "$setores.vendidos",
                "disponiveis": {"$subtract": ["$setores.capacidade", "$setores.vendidos"]},
                "percentualVendido": {
                    "$round": [
                        {
                            "$multiply": [
                                {"$divide": ["$setores.vendidos", "$setores.capacidade"]},
                                100,
                            ]
                        },
                        2,
                    ]
                },
            }
        },
        {"$sort": {"percentualVendido": -1}},
    ]
    resultado = list(db.eventos.aggregate(pipeline))
    if not resultado:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return serializar(resultado)
