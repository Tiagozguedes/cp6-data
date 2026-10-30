"""Req. 8 (demonstração): dispara 11 reservas seguidas para o mesmo usuário.
As 10 primeiras são aceitas (201) e a 11ª recebe 429.

Uso: docker compose exec api python demo_limite.py
"""
import json
import urllib.error
import urllib.request

API = "http://localhost:8000"


def chamar(metodo, caminho, corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        API + caminho, data=dados, method=metodo, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as erro:
        return erro.code, json.loads(erro.read())


if __name__ == "__main__":
    _, usuarios = chamar("GET", "/usuarios")
    _, eventos = chamar("GET", "/eventos")
    usuario, evento = usuarios[-1], eventos[0]
    corpo = {
        "usuarioId": usuario["id"],
        "eventoId": evento["id"],
        "setor": evento["setores"][0]["nome"],
        "quantidade": 1,
    }
    print(f"Usuário: {usuario['nome']} | Evento: {evento['nome']}\n")
    for i in range(1, 12):
        status, resposta = chamar("POST", "/reservas", corpo)
        detalhe = resposta.get("reservaId") or resposta.get("detail")
        print(f"Reserva {i:2d} -> HTTP {status}  {detalhe}")
