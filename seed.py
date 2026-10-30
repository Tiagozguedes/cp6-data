"""Popula o MongoDB com 10 eventos, 20 usuários e 50 pedidos.

Uso:
    python seed.py          -> só popula se o banco estiver vazio
    python seed.py --reset  -> apaga tudo (MongoDB e chaves do Redis) e popula de novo
"""
import random
import sys
import unicodedata
from datetime import datetime, timedelta, timezone

from app.database import criar_indices, db, r

random.seed(42)  # dados sempre iguais a cada execução

EVENTOS = [
    {
        "nome": "Noite do Rock Paulista",
        "categoria": "show",
        "data": datetime(2026, 12, 5, 21, 0),
        "local": {"cidade": "São Paulo", "endereco": "Av. Francisco Matarazzo, 1705"},
        "atracoes": ["Os Trovões", "Banda Asfalto", "Lua Elétrica"],
        "setores": [
            {"nome": "Pista", "preco": 180.0, "capacidade": 300, "vendidos": 0},
            {"nome": "Pista Premium", "preco": 350.0, "capacidade": 100, "vendidos": 0},
            {"nome": "Camarote", "preco": 600.0, "capacidade": 40, "vendidos": 0},
        ],
        "classificacaoEtaria": 16,
    },
    {
        "nome": "Festival Sons do Cerrado",
        "categoria": "festival",
        "data": datetime(2027, 1, 16, 14, 0),
        "local": {"cidade": "Belo Horizonte", "endereco": "Av. Otacílio Negrão de Lima, 6061"},
        "atracoes": ["Viola Nova", "Trio Ipê", "Coletivo Serrano", "DJ Pequi"],
        "setores": [
            {"nome": "Passaporte 1 dia", "preco": 220.0, "capacidade": 500, "vendidos": 0},
            {"nome": "Passaporte 2 dias", "preco": 390.0, "capacidade": 300, "vendidos": 0},
        ],
        "duracaoDias": 2,
        "patrocinadores": ["Café Mineiro", "Rádio BH"],
    },
    {
        "nome": "Sinfonia das Estações",
        "categoria": "show",
        "data": datetime(2026, 11, 20, 20, 0),
        "local": {"cidade": "Rio de Janeiro", "endereco": "Praça Floriano, s/n"},
        "atracoes": ["Orquestra Jovem Carioca"],
        "setores": [
            {"nome": "Plateia", "preco": 120.0, "capacidade": 200, "vendidos": 0},
            {"nome": "Balcão", "preco": 80.0, "capacidade": 150, "vendidos": 0},
            {"nome": "Frisa", "preco": 250.0, "capacidade": 30, "vendidos": 0},
        ],
    },
    {
        "nome": "Clássico Regional — Final",
        "categoria": "esporte",
        "data": datetime(2026, 12, 13, 16, 0),
        "local": {"cidade": "Porto Alegre", "endereco": "Av. Padre Cacique, 891"},
        "atracoes": ["Atlético Guaíba", "União Pampa"],
        "setores": [
            {"nome": "Arquibancada Norte", "preco": 90.0, "capacidade": 400, "vendidos": 0},
            {"nome": "Arquibancada Sul", "preco": 90.0, "capacidade": 400, "vendidos": 0},
            {"nome": "Cadeira Central", "preco": 200.0, "capacidade": 150, "vendidos": 0},
        ],
        "modalidade": "futebol",
    },
    {
        "nome": "Risadas em Cena",
        "categoria": "standup",
        "data": datetime(2026, 11, 28, 22, 0),
        "local": {"cidade": "Curitiba", "endereco": "Rua XV de Novembro, 971"},
        "atracoes": ["Carla Piada", "Beto Improviso"],
        "setores": [{"nome": "Plateia Única", "preco": 70.0, "capacidade": 120, "vendidos": 0}],
        "classificacaoEtaria": 18,
        "duracaoMinutos": 90,
    },
    {
        "nome": "O Último Ato",
        "categoria": "teatro",
        "data": datetime(2026, 12, 2, 19, 30),
        "local": {"cidade": "São Paulo", "endereco": "Rua Major Diogo, 315"},
        "atracoes": ["Cia. Teatro Aberto"],
        "setores": [
            {"nome": "Plateia A", "preco": 110.0, "capacidade": 150, "vendidos": 0},
            {"nome": "Plateia B", "preco": 80.0, "capacidade": 100, "vendidos": 0},
        ],
        "duracaoMinutos": 120,
        "diretor": "Helena Prado",
    },
    {
        "nome": "Eletro Beach Party",
        "categoria": "festival",
        "data": datetime(2027, 2, 6, 18, 0),
        "local": {"cidade": "Rio de Janeiro", "endereco": "Av. Atlântica, s/n — Posto 2"},
        "atracoes": ["DJ Maré", "Pulso 808", "Neon Tropical"],
        "setores": [
            {"nome": "Pista", "preco": 150.0, "capacidade": 600, "vendidos": 0},
            {"nome": "Open Bar", "preco": 420.0, "capacidade": 120, "vendidos": 0},
        ],
        "patrocinadores": ["Energético Onda"],
    },
    {
        "nome": "Samba de Raiz no Parque",
        "categoria": "show",
        "data": datetime(2027, 1, 10, 17, 0),
        "local": {"cidade": "São Paulo", "endereco": "Av. Pedro Álvares Cabral, s/n"},
        "atracoes": ["Grupo Batuque Bom", "Dona Zica do Cavaco"],
        "setores": [
            {"nome": "Pista", "preco": 60.0, "capacidade": 800, "vendidos": 0},
            {"nome": "Área VIP", "preco": 180.0, "capacidade": 80, "vendidos": 0},
        ],
    },
    {
        "nome": "Final Estadual de Vôlei",
        "categoria": "esporte",
        "data": datetime(2026, 12, 19, 19, 0),
        "local": {"cidade": "Curitiba", "endereco": "Av. Presidente Kennedy, 2511"},
        "atracoes": ["Curitiba Vôlei", "Paraná Saque"],
        "setores": [
            {"nome": "Geral", "preco": 50.0, "capacidade": 250, "vendidos": 0},
            {"nome": "Cadeira Numerada", "preco": 110.0, "capacidade": 100, "vendidos": 0},
        ],
        "modalidade": "vôlei",
    },
    {
        "nome": "Indie na Serra",
        "categoria": "show",
        "data": datetime(2027, 3, 13, 20, 0),
        "local": {"cidade": "Belo Horizonte", "endereco": "Rua Sapucaí, 571"},
        "atracoes": ["Neblina", "Os Andarilhos"],
        "setores": [
            {"nome": "Pista", "preco": 95.0, "capacidade": 250, "vendidos": 0},
            {"nome": "Mezanino", "preco": 160.0, "capacidade": 60, "vendidos": 0},
        ],
        "classificacaoEtaria": 14,
    },
]

NOMES = [
    "Ana Souza", "Bruno Lima", "Carla Mendes", "Diego Alves", "Elisa Rocha",
    "Felipe Costa", "Gabriela Nunes", "Henrique Dias", "Isabela Martins", "João Pereira",
    "Karina Lopes", "Lucas Ribeiro", "Mariana Teixeira", "Nicolas Barros", "Olivia Freitas",
    "Paulo Cardoso", "Rafaela Gomes", "Samuel Moreira", "Tatiane Araújo", "Vitor Azevedo",
]
CIDADES = ["São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Porto Alegre"]
STATUS = ["confirmado"] * 7 + ["pendente"] * 2 + ["cancelado"]  # ~70% confirmados


def limpar():
    db.eventos.drop()
    db.usuarios.drop()
    db.pedidos.drop()
    for padrao in ("evento:*", "reserva:*", "limite:*"):
        for chave in r.scan_iter(padrao):
            r.delete(chave)
    r.delete("ranking:eventos")


def popular():
    agora = datetime.now(timezone.utc)

    eventos = [dict(e, setores=[dict(s) for s in e["setores"]]) for e in EVENTOS]
    db.eventos.insert_many(eventos)  # insert_many preenche o _id de cada dict

    usuarios = []
    for i, nome in enumerate(NOMES):
        sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
        login = sem_acento.lower().replace(" ", ".")
        usuarios.append({
            "nome": nome,
            "email": f"{login}{i}@email.com",
            "cidade": random.choice(CIDADES),
            "dataCadastro": agora - timedelta(days=random.randint(10, 400)),
        })
    db.usuarios.insert_many(usuarios)

    pedidos = []
    for _ in range(50):
        evento = random.choice(eventos)
        setor = random.choice(evento["setores"])
        quantidade = random.randint(1, 4)
        status = random.choice(STATUS)
        if status == "confirmado":
            setor["vendidos"] += quantidade  # mantém "vendidos" coerente com os pedidos
        pedidos.append({
            "usuarioId": random.choice(usuarios)["_id"],
            "eventoId": evento["_id"],
            "setor": setor["nome"],
            "quantidade": quantidade,
            "valorTotal": round(setor["preco"] * quantidade, 2),
            "status": status,
            "criadoEm": agora - timedelta(days=random.randint(0, 30), minutes=random.randint(0, 1440)),
        })
    db.pedidos.insert_many(pedidos)

    for evento in eventos:
        db.eventos.update_one({"_id": evento["_id"]}, {"$set": {"setores": evento["setores"]}})


def main():
    reset = "--reset" in sys.argv
    criar_indices()

    if db.eventos.count_documents({}) > 0 and not reset:
        print("[seed] Banco já populado. Use 'python seed.py --reset' para recriar.")
        return

    limpar()
    popular()
    criar_indices()  # drop() remove os índices; recria
    print(
        f"[seed] OK: {db.eventos.count_documents({})} eventos, "
        f"{db.usuarios.count_documents({})} usuários, "
        f"{db.pedidos.count_documents({})} pedidos."
    )


if __name__ == "__main__":
    main()
