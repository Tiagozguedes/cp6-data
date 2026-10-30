from datetime import datetime

from bson import ObjectId
from fastapi import HTTPException


def para_object_id(valor: str) -> ObjectId:
    """Converte a string recebida na URL/corpo em ObjectId (ou responde 400)."""
    if not ObjectId.is_valid(valor):
        raise HTTPException(status_code=400, detail=f"Id inválido: {valor}")
    return ObjectId(valor)


def serializar(dado):
    """Converte documentos do MongoDB em JSON: _id -> id, ObjectId -> str, datetime -> ISO."""
    if isinstance(dado, list):
        return [serializar(item) for item in dado]
    if isinstance(dado, dict):
        return {("id" if k == "_id" else k): serializar(v) for k, v in dado.items()}
    if isinstance(dado, ObjectId):
        return str(dado)
    if isinstance(dado, datetime):
        return dado.isoformat()
    return dado
