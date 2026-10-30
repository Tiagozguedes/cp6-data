"""Fluxo de compra (Req. 10): reserva temporária (Req. 6), limite (Req. 8) e Pub/Sub (bônus)."""
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.database import db, r
from app.eventos import invalidar_cache
from app.schemas import ConfirmacaoIn, ReservaIn
from app.utils import para_object_id, serializar

router = APIRouter(tags=["Compra"])

RESERVA_TTL = 600        # 10 minutos
LIMITE_RESERVAS = 10     # reservas por usuário...
JANELA_LIMITE = 60       # ...a cada 60 segundos
CANAL_PEDIDOS = "pedidos:confirmados"


def verificar_limite(usuario_id: str):
    """Req. 8: contador com INCR; a primeira requisição da janela define o EXPIRE de 60 s."""
    chave = f"limite:reservas:{usuario_id}"
    total = r.incr(chave)
    if total == 1:
        r.expire(chave, JANELA_LIMITE)
    if total > LIMITE_RESERVAS:
        raise HTTPException(
            status_code=429,
            detail={
                "erro": f"Limite de {LIMITE_RESERVAS} reservas por minuto atingido",
                "tenteNovamenteEmSegundos": r.ttl(chave),
            },
        )


@router.post("/reservas", status_code=201)
def criar_reserva(dados: ReservaIn):
    # 1) limite de requisições (Redis)
    verificar_limite(dados.usuarioId)

    usuario_oid = para_object_id(dados.usuarioId)
    evento_oid = para_object_id(dados.eventoId)

    if not db.usuarios.find_one({"_id": usuario_oid}, {"_id": 1}):
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # 2) confere no MongoDB se o setor tem vagas ("setores.$" traz só o setor encontrado)
    evento = db.eventos.find_one(
        {"_id": evento_oid, "setores.nome": dados.setor}, {"nome": 1, "setores.$": 1}
    )
    if not evento:
        raise HTTPException(status_code=404, detail="Evento ou setor não encontrado")

    setor = evento["setores"][0]
    disponiveis = setor["capacidade"] - setor["vendidos"]
    if disponiveis < dados.quantidade:
        raise HTTPException(
            status_code=409, detail=f"Setor sem vagas suficientes (disponíveis: {disponiveis})"
        )

    # 3) cria a reserva no Redis com SET NX EX: só grava se a chave não existir e expira sozinha
    reserva_id = uuid.uuid4().hex
    chave = f"reserva:{reserva_id}"
    reserva = {
        "reservaId": reserva_id,
        "usuarioId": dados.usuarioId,
        "eventoId": dados.eventoId,
        "evento": evento["nome"],
        "setor": dados.setor,
        "quantidade": dados.quantidade,
        "precoUnitario": setor["preco"],
        "criadaEm": datetime.now(timezone.utc).isoformat(),
    }
    if not r.set(chave, json.dumps(reserva), nx=True, ex=RESERVA_TTL):
        raise HTTPException(status_code=409, detail="Reserva já existente")

    return {**reserva, "chaveRedis": chave, "expiraEmSegundos": RESERVA_TTL}


@router.post("/pedidos/confirmar", status_code=201)
def confirmar_pedido(dados: ConfirmacaoIn):
    chave = f"reserva:{dados.reservaId}"

    # GETDEL lê e apaga a reserva numa única operação atômica:
    # duas confirmações simultâneas da mesma reserva não geram dois pedidos.
    bruto = r.getdel(chave)
    if bruto is None:
        raise HTTPException(
            status_code=410, detail="Reserva expirada ou inexistente. Nada foi gravado."
        )
    reserva = json.loads(bruto)

    evento_oid = para_object_id(reserva["eventoId"])
    setor_nome = reserva["setor"]
    quantidade = reserva["quantidade"]

    evento = db.eventos.find_one(
        {"_id": evento_oid, "setores.nome": setor_nome}, {"setores.$": 1}
    )
    if not evento:
        raise HTTPException(status_code=404, detail="Evento ou setor não encontrado")
    capacidade = evento["setores"][0]["capacidade"]

    # $inc atômico e condicional: o filtro só casa se vendidos + quantidade <= capacidade.
    # Se outro pedido esgotar o setor antes, modified_count == 0 e nada é incrementado.
    resultado = db.eventos.update_one(
        {
            "_id": evento_oid,
            "setores": {
                "$elemMatch": {"nome": setor_nome, "vendidos": {"$lte": capacidade - quantidade}}
            },
        },
        {"$inc": {"setores.$.vendidos": quantidade}},
    )
    if resultado.modified_count == 0:
        raise HTTPException(status_code=409, detail="Capacidade do setor esgotada")

    pedido = {
        "usuarioId": para_object_id(reserva["usuarioId"]),
        "eventoId": evento_oid,
        "setor": setor_nome,
        "quantidade": quantidade,
        "valorTotal": round(reserva["precoUnitario"] * quantidade, 2),
        "status": "confirmado",
        "criadoEm": datetime.now(timezone.utc),
    }
    pedido["_id"] = db.pedidos.insert_one(pedido).inserted_id

    # "vendidos" mudou: o cache do evento ficou desatualizado
    invalidar_cache(reserva["eventoId"])

    # Bônus: avisa os assinantes do canal pedidos:confirmados
    pedido_json = serializar(pedido)
    r.publish(CANAL_PEDIDOS, json.dumps(pedido_json))

    return pedido_json


@router.get("/pedidos")
def listar_pedidos(usuarioId: str | None = None):
    filtro = {"usuarioId": para_object_id(usuarioId)} if usuarioId else {}
    return serializar(list(db.pedidos.find(filtro).sort("criadoEm", -1)))


@router.get("/usuarios")
def listar_usuarios():
    return serializar(list(db.usuarios.find().sort("nome", 1)))
