"""Req. 3: mostra o plano de execução (explain) de consultas em eventos.

Uso: docker compose exec api python explain.py
"""
from app.database import criar_indices, db


def estagios(plano):
    """Percorre a árvore do winningPlan e devolve os estágios (ex.: FETCH -> IXSCAN)."""
    lista = [plano["stage"] + (f" ({plano['indexName']})" if "indexName" in plano else "")]
    if "inputStage" in plano:
        lista += estagios(plano["inputStage"])
    return lista


def mostrar(titulo, cursor):
    explain = cursor.explain()
    plano = explain["queryPlanner"]["winningPlan"]
    plano = plano.get("queryPlan", plano)  # MongoDB 7+ (SBE) aninha o plano em queryPlan
    stats = explain["executionStats"]
    print(f"\n=== {titulo} ===")
    print("Filtro:            ", explain["queryPlanner"]["parsedQuery"])
    print("Plano vencedor:    ", " -> ".join(estagios(plano)))
    print("Docs retornados:   ", stats["nReturned"])
    print("Chaves examinadas: ", stats["totalKeysExamined"])
    print("Docs examinados:   ", stats["totalDocsExamined"])
    print("Tempo (ms):        ", stats["executionTimeMillis"])


if __name__ == "__main__":
    criar_indices()
    print("Índices em eventos:", list(db.eventos.index_information().keys()))

    mostrar(
        "Consulta com índice composto (categoria + data)",
        db.eventos.find({"categoria": "show"}).sort("data", 1),
    )
    mostrar(
        "Consulta sem índice (comparação)",
        db.eventos.find({"local.cidade": "São Paulo"}),
    )
