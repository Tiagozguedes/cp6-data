"""Bônus: assinante do canal Pub/Sub pedidos:confirmados.

Uso: docker compose exec api python subscriber.py
"""
import json

from app.database import r

CANAL = "pedidos:confirmados"

if __name__ == "__main__":
    pubsub = r.pubsub()
    pubsub.subscribe(CANAL)
    print(f"[subscriber] Ouvindo o canal '{CANAL}'... (Ctrl+C para sair)", flush=True)

    for mensagem in pubsub.listen():
        if mensagem["type"] != "message":
            continue  # ignora a confirmação de inscrição
        pedido = json.loads(mensagem["data"])
        print(
            f"[subscriber] Pedido confirmado: id={pedido['id']} evento={pedido['eventoId']} "
            f"setor={pedido['setor']} qtd={pedido['quantidade']} total=R$ {pedido['valorTotal']:.2f}",
            flush=True,
        )
