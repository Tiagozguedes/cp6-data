"""Conexões com MongoDB (fonte da verdade) e Redis (dados rápidos/temporários)."""
import os

import redis
from pymongo import ASCENDING, MongoClient

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

mongo = MongoClient(MONGO_URL)
db = mongo["ticketflash"]

# decode_responses=True faz o Redis devolver str em vez de bytes
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def criar_indices():
    """Requisito 3: índices criados pelo código (create_index é idempotente)."""
    # Índice único: não permite dois usuários com o mesmo e-mail
    db.usuarios.create_index("email", unique=True, name="email_unico")
    # Índice composto: atende filtro por categoria + ordenação por data
    db.eventos.create_index(
        [("categoria", ASCENDING), ("data", ASCENDING)], name="categoria_data"
    )
    # Índice simples: busca dos pedidos de um usuário
    db.pedidos.create_index("usuarioId", name="pedidos_usuario")
