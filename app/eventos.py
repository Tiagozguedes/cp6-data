"""CRUD de eventos (Req. 2), cache-aside (Req. 5 e 9) e ranking (Req. 7)."""
import json

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Response

from app.database import db, r
from app.schemas import EventoIn, EventoUpdate
from app.utils import para_object_id, serializar

router = APIRouter(prefix="/eventos", tags=["Eventos"])

CACHE_TTL = 60  # segundos
RANKING_KEY = "ranking:eventos"


def chave_cache(evento_id: str) -> str:
    return f"evento:{evento_id}"


def invalidar_cache(evento_id: str):
    """Req. 9: apaga a chave do Redis; a próxima leitura vai ao banco e repopula."""
    r.delete(chave_cache(evento_id))


@router.post("", status_code=201)
def criar_evento(evento: EventoIn):
    doc = evento.model_dump()
    resultado = db.eventos.insert_one(doc)
    doc["_id"] = resultado.inserted_id
    return serializar(doc)


@router.get("")
def listar_eventos(categoria: str | None = None, cidade: str | None = None):
    # Os filtros são aplicados na consulta ao MongoDB, não em Python
    filtro = {}
    if categoria:
        filtro["categoria"] = categoria
    if cidade:
        filtro["local.cidade"] = cidade
    eventos = db.eventos.find(filtro).sort("data", 1)
    return serializar(list(eventos))


# Precisa ser declarada antes de /{evento_id}, senão "ranking" seria lido como id
@router.get("/ranking")
def ranking_mais_vistos():
    """Req. 7: top 5 do Sorted Set (maior pontuação primeiro)."""
    top = r.zrevrange(RANKING_KEY, 0, 4, withscores=True)
    ids = [ObjectId(evento_id) for evento_id, _ in top]
    nomes = {
        str(e["_id"]): e["nome"]
        for e in db.eventos.find({"_id": {"$in": ids}}, {"nome": 1})
    }
    return [
        {
            "posicao": posicao,
            "eventoId": evento_id,
            "nome": nomes.get(evento_id),
            "visualizacoes": int(pontos),
        }
        for posicao, (evento_id, pontos) in enumerate(top, start=1)
    ]


@router.get("/{evento_id}")
def buscar_evento(evento_id: str):
    """Req. 5: cache-aside. Consulta o Redis primeiro; se não houver, busca no MongoDB."""
    oid = para_object_id(evento_id)
    chave = chave_cache(evento_id)

    em_cache = r.get(chave)
    if em_cache:
        r.zincrby(RANKING_KEY, 1, evento_id)
        return {"origem": "cache", "ttlRestante": r.ttl(chave), "evento": json.loads(em_cache)}

    doc = db.eventos.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    evento = serializar(doc)
    r.set(chave, json.dumps(evento), ex=CACHE_TTL)
    r.zincrby(RANKING_KEY, 1, evento_id)
    return {"origem": "banco", "ttlRestante": CACHE_TTL, "evento": evento}


@router.put("/{evento_id}")
def atualizar_evento(evento_id: str, dados: EventoUpdate):
    oid = para_object_id(evento_id)
    campos = dados.model_dump(exclude_unset=True)
    if not campos:
        raise HTTPException(status_code=400, detail="Nenhum campo informado")

    resultado = db.eventos.update_one({"_id": oid}, {"$set": campos})
    if resultado.matched_count == 0:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    invalidar_cache(evento_id)
    return {"mensagem": "Evento atualizado", "cacheInvalidado": chave_cache(evento_id)}


@router.delete("/{evento_id}", status_code=204)
def remover_evento(evento_id: str):
    oid = para_object_id(evento_id)
    resultado = db.eventos.delete_one({"_id": oid})
    if resultado.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    invalidar_cache(evento_id)
    r.zrem(RANKING_KEY, evento_id)  # evento removido sai do ranking
    return Response(status_code=204)
