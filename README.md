# TicketFlash — MongoDB + Redis com Python

Checkpoint 3 — Mastering Relational and Non-Relational Database (2TDSPG) — Prof. Vergílio Santos

API REST da plataforma de ingressos **TicketFlash**, feita com **FastAPI**, usando o **MongoDB** como fonte da verdade (eventos, usuários e pedidos) e o **Redis** para cache, reservas temporárias, ranking, limite de requisições e Pub/Sub.

## Integrantes

| RM | Nome |
|----|------|
| 564731 | Tiago Guedes da Costa |

## Tecnologias

- Python 3.12 + FastAPI + Uvicorn
- MongoDB 7 com `pymongo`
- Redis 7 com `redis-py`
- Docker Compose (serviços `api`, `mongo` e `redis`)

## Como executar

Pré-requisito: Docker Desktop aberto.

```bash
docker compose up --build
```

Pronto. Ao subir, a `api` roda o `seed.py` (que só popula se o banco estiver vazio) e depois inicia o servidor.

- API: http://localhost:8000
- Documentação interativa (Swagger): http://localhost:8000/docs

Comandos úteis (em outro terminal, com o ambiente rodando):

```bash
# Recriar os dados do zero (10 eventos, 20 usuários, 50 pedidos) e limpar as chaves do Redis
docker compose exec api python seed.py --reset

# Ver o plano de execução (explain) — Req. 3
docker compose exec api python explain.py

# Assinante do Pub/Sub (bônus) — deixe aberto e confirme um pedido
docker compose exec api python subscriber.py

# Disparar 11 reservas seguidas e ver o 429 — Req. 8
docker compose exec api python demo_limite.py

# Abrir o Redis para mostrar chaves e TTL
docker compose exec redis redis-cli
#   KEYS *
#   TTL reserva:<reservaId>
#   ZREVRANGE ranking:eventos 0 4 WITHSCORES
```

Para parar: `docker compose down` (os dados do MongoDB ficam no volume `mongo_data`; use `docker compose down -v` para apagá-los).

## Estrutura do projeto

```
├── app/
│   ├── main.py         # cria a aplicação FastAPI e os índices na inicialização
│   ├── database.py     # conexões MongoDB/Redis e criação dos índices (Req. 3)
│   ├── schemas.py      # validação das entradas (Pydantic)
│   ├── utils.py        # conversão ObjectId/datetime -> JSON
│   ├── eventos.py      # CRUD (Req. 2), cache (Req. 5), ranking (Req. 7), invalidação (Req. 9)
│   ├── compras.py      # reservas (Req. 6), limite (Req. 8), compra (Req. 10), Pub/Sub (bônus)
│   └── relatorios.py   # agregações (Req. 4)
├── seed.py             # popula o MongoDB
├── explain.py          # mostra o explain() das consultas
├── subscriber.py       # assinante do canal pedidos:confirmados (bônus)
├── demo_limite.py      # demonstra o 429
├── requests.http       # coleção com todas as requisições
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Endpoints

| Método | Rota | Descrição | Req. |
|--------|------|-----------|------|
| GET | `/` | Status da API, MongoDB e Redis | — |
| POST | `/eventos` | Cria evento (`insert_one`) | 2 |
| GET | `/eventos?categoria=&cidade=` | Lista eventos com filtros aplicados no `find` | 2 |
| GET | `/eventos/{id}` | Busca por id (Redis → MongoDB), indica `"origem"` e soma 1 no ranking | 2, 5, 7 |
| PUT | `/eventos/{id}` | Atualiza (`update_one` + `$set`) e apaga o cache | 2, 9 |
| DELETE | `/eventos/{id}` | Remove (`delete_one`) e apaga o cache | 2, 9 |
| GET | `/eventos/ranking` | Top 5 eventos mais vistos (Sorted Set) | 7 |
| GET | `/usuarios` | Lista usuários (para obter ids) | — |
| POST | `/reservas` | Limite → checa vagas no MongoDB → `SET NX EX 600` | 6, 8, 10 |
| POST | `/pedidos/confirmar` | Confirma reserva: grava pedido, `$inc` condicional, publica no Pub/Sub; 410 se expirou | 10, bônus |
| GET | `/pedidos?usuarioId=` | Pedidos de um usuário | 3 |
| GET | `/relatorios/faturamento` | Faturamento por evento (pedidos confirmados) | 4 |
| GET | `/relatorios/ocupacao/{id}` | % vendido de cada setor de um evento | 4 |

Todas as requisições estão em [requests.http](requests.http) (extensão *REST Client* do VS Code, ou importável no Insomnia/Postman).

Exemplos de corpo:

```json
// POST /reservas
{ "usuarioId": "<id>", "eventoId": "<id>", "setor": "Pista", "quantidade": 2 }

// POST /pedidos/confirmar
{ "reservaId": "<reservaId devolvido pela reserva>" }
```

## Parte 1 — MongoDB

### Req. 1 — Modelagem e justificativa

Banco `ticketflash`, com três coleções:

**`eventos`**
```json
{
  "_id": ObjectId,
  "nome": "Noite do Rock Paulista",
  "categoria": "show",
  "data": ISODate("2026-12-05T21:00:00"),
  "local": { "cidade": "São Paulo", "endereco": "Av. Francisco Matarazzo, 1705" },
  "atracoes": ["Os Trovões", "Banda Asfalto"],
  "setores": [
    { "nome": "Pista", "preco": 180.0, "capacidade": 300, "vendidos": 12 },
    { "nome": "Camarote", "preco": 600.0, "capacidade": 40, "vendidos": 3 }
  ],
  "classificacaoEtaria": 16
}
```

**`usuarios`**
```json
{ "_id": ObjectId, "nome": "Ana Souza", "email": "ana.souza0@email.com", "cidade": "Curitiba", "dataCadastro": ISODate }
```

**`pedidos`**
```json
{
  "_id": ObjectId,
  "usuarioId": ObjectId,   // referência a usuarios
  "eventoId": ObjectId,    // referência a eventos
  "setor": "Pista", "quantidade": 2, "valorTotal": 360.0,
  "status": "confirmado",  // confirmado | pendente | cancelado
  "criadoEm": ISODate
}
```

**Por que embutir ou referenciar:**

| Dado | Escolha | Justificativa |
|------|---------|---------------|
| `local` dentro de `eventos` | **Embutido** (subdocumento) | Relação 1:1 e sempre lido junto com o evento. Não existe consulta de "local" isolado; embutir evita uma consulta extra. O filtro por cidade usa a notação de ponto (`local.cidade`). |
| `atracoes` dentro de `eventos` | **Embutido** (array) | Lista pequena e limitada, que só faz sentido dentro do evento e é exibida junto com ele. |
| `setores` dentro de `eventos` | **Embutido** (array de subdocumentos) | Cada evento tem poucos setores (2 a 5), que não existem fora do evento. Com os setores no mesmo documento, a página do evento é lida em **uma única consulta** (e cacheada inteira no Redis), e o incremento de `vendidos` é **atômico**: o MongoDB garante atomicidade por documento, então o `update_one` com `$inc` e a condição de capacidade no filtro acontecem numa só operação, sem transação. |
| Campos opcionais (`classificacaoEtaria`, `modalidade`, `duracaoMinutos`, `patrocinadores`...) | **Esquema flexível** | Cada tipo de evento tem informações diferentes. No MongoDB cada documento pode ter seus próprios campos, sem colunas nulas ou tabelas extras. A API aceita esses campos extras (`extra="allow"` no Pydantic). |
| `usuarios` | **Coleção própria** | O usuário existe independentemente dos pedidos, é atualizado sozinho (nome, cidade) e precisa de e-mail único. |
| `pedidos` → `usuarioId` e `eventoId` | **Referência** | Um usuário e um evento podem ter um número ilimitado de pedidos; embuti-los causaria crescimento sem limite dos documentos (limite de 16 MB) e duplicação de dados. Pedidos também são consultados sozinhos (por usuário, por status) e agregados em relatórios; quando o nome do evento é necessário, ele é obtido com `$lookup`. |
| `setor` e `valorTotal` no pedido | **Cópia do valor** (snapshot) | O pedido guarda o nome do setor e o valor pago no momento da compra. Se o preço do setor mudar depois, o histórico do pedido continua correto. |

### Req. 2 — CRUD de eventos

Implementado em [app/eventos.py](app/eventos.py) com `insert_one`, `find` (com filtro `categoria` e `local.cidade` montado na própria consulta e ordenação por data), `find_one`, `update_one` (`$set` só dos campos enviados) e `delete_one`.

### Req. 3 — Índices

Criados pelo código em `criar_indices()` ([app/database.py](app/database.py)), chamado na inicialização da API e no seed:

| Coleção | Índice | Tipo | Uso |
|---------|--------|------|-----|
| `usuarios` | `{ email: 1 }` (`email_unico`) | Único | Impede e-mail duplicado |
| `eventos` | `{ categoria: 1, data: 1 }` (`categoria_data`) | Composto | `GET /eventos?categoria=...` (filtra por categoria e ordena por data) |
| `pedidos` | `{ usuarioId: 1 }` (`pedidos_usuario`) | Simples | `GET /pedidos?usuarioId=...` |

**Saída do `explain()`** — consulta `db.eventos.find({"categoria": "show"}).sort("data", 1)` (`docker compose exec api python explain.py`):

```
Índices em eventos: ['_id_', 'categoria_data']

=== Consulta com índice composto (categoria + data) ===
Filtro:             {'categoria': {'$eq': 'show'}}
Plano vencedor:     FETCH -> IXSCAN (categoria_data)
Docs retornados:    4
Chaves examinadas:  4
Docs examinados:    4
Tempo (ms):         0

=== Consulta sem índice (comparação) ===
Filtro:             {'local.cidade': {'$eq': 'São Paulo'}}
Plano vencedor:     COLLSCAN
Docs retornados:    3
Chaves examinadas:  0
Docs examinados:    10
Tempo (ms):         0
```

`winningPlan` completo retornado pelo `explain()`:

```json
{
  "stage": "FETCH",
  "inputStage": {
    "stage": "IXSCAN",
    "keyPattern": { "categoria": 1, "data": 1 },
    "indexName": "categoria_data",
    "isMultiKey": false,
    "isUnique": false,
    "direction": "forward",
    "indexBounds": {
      "categoria": ["[\"show\", \"show\"]"],
      "data": ["[MinKey, MaxKey]"]
    }
  }
}
```

**Leitura do plano:** o estágio é **IXSCAN** no índice `categoria_data`, e não COLLSCAN. O `indexBounds` mostra que o MongoDB percorreu só a faixa `categoria = "show"` do índice, e como a segunda chave é `data`, os resultados já saem ordenados (não há estágio `SORT` em memória). Foram examinadas 4 chaves e 4 documentos para devolver 4: nenhum documento foi lido à toa. Na consulta de comparação, por um campo sem índice (`local.cidade`), o plano é **COLLSCAN**: os 10 documentos da coleção foram lidos para devolver 3.

### Req. 4 — Agregações

Em [app/relatorios.py](app/relatorios.py); todo o cálculo é feito pelo MongoDB (nenhum laço em Python):

- **`GET /relatorios/faturamento`**: `$match` (status confirmado) → `$group` por `eventoId` (soma de `valorTotal`, nº de pedidos e de ingressos) → `$lookup` em `eventos` → `$unwind` → `$project` (nome do evento) → `$sort` pelo faturamento decrescente.
- **`GET /relatorios/ocupacao/{id}`**: `$match` do evento → `$unwind` de `setores` (um documento por setor) → `$project` calculando `disponiveis` (`$subtract`) e `percentualVendido` (`$divide` × 100 com `$round`) → `$sort`.

Exemplo de resposta (ocupação):

```json
[{ "evento": "Risadas em Cena", "setor": "Plateia Única", "capacidade": 120, "vendidos": 10, "disponiveis": 110, "percentualVendido": 8.33 }]
```

## Parte 2 — Redis

| Chave | Estrutura | Uso | TTL |
|-------|-----------|-----|-----|
| `evento:{id}` | String (JSON) | Cache do evento (Req. 5) | 60 s |
| `reserva:{reservaId}` | String (JSON) com `SET NX EX` | Reserva temporária (Req. 6) | 600 s |
| `ranking:eventos` | Sorted Set | Eventos mais vistos (Req. 7) | — |
| `limite:reservas:{usuarioId}` | String com `INCR` + `EXPIRE` | Limite de reservas (Req. 8) | 60 s |
| `pedidos:confirmados` | Canal Pub/Sub | Aviso de pedido confirmado (bônus) | — |

- **Req. 5 — Cache:** `GET /eventos/{id}` faz `GET evento:{id}`. Se existir, responde com `"origem": "cache"`. Se não, busca no MongoDB, grava com `SET evento:{id} <json> EX 60` e responde `"origem": "banco"`. A resposta também traz `ttlRestante`.
- **Req. 6 — Reserva:** `SET reserva:{id} <json> NX EX 600`. O `NX` garante que uma reserva nunca sobrescreve outra; o `EX 600` faz a chave sumir sozinha após 10 minutos se o pedido não for confirmado.
- **Req. 7 — Ranking:** cada `GET /eventos/{id}` (vindo do cache ou do banco) executa `ZINCRBY ranking:eventos 1 {id}`. `GET /eventos/ranking` usa `ZREVRANGE ranking:eventos 0 4 WITHSCORES` (top 5) e busca os nomes no MongoDB. Ao remover um evento, ele sai do ranking (`ZREM`).
- **Req. 8 — Limite:** em cada `POST /reservas`, `INCR limite:reservas:{usuarioId}`. Quando o valor é 1 (primeira reserva da janela), aplica `EXPIRE 60`. Se passar de 10, a API responde **429** com o tempo restante para liberar.

## Parte 3 — Integração

### Req. 9 — Cache-aside com invalidação

Em `PUT /eventos/{id}` e `DELETE /eventos/{id}`, depois de alterar o MongoDB, a API executa `DEL evento:{id}`. A próxima leitura não encontra a chave, vai ao banco (`"origem": "banco"`) e repopula o cache. O cache também é invalidado quando um pedido é confirmado, porque o `vendidos` do setor muda.

### Req. 10 — Fluxo de compra

1. **`POST /reservas`**: verifica o limite (Req. 8) → confere no MongoDB se o setor existe e tem vagas (`capacidade - vendidos >= quantidade`, senão **409**) → cria a reserva no Redis com `SET NX EX 600`.
2. **`POST /pedidos/confirmar`**:
   - Lê e apaga a reserva com **`GETDEL`** (uma operação atômica). Se ela não existir (expirou ou já foi usada), responde **410 Gone** e nada é gravado. Usar `GETDEL` em vez de `GET` + `DEL` impede que duas confirmações simultâneas da mesma reserva gerem dois pedidos.
   - Incrementa `vendidos` com um **`$inc` condicional e atômico**:
     ```python
     db.eventos.update_one(
         {"_id": evento_id,
          "setores": {"$elemMatch": {"nome": setor, "vendidos": {"$lte": capacidade - quantidade}}}},
         {"$inc": {"setores.$.vendidos": quantidade}},
     )
     ```
     A condição de capacidade está no próprio filtro: se outro pedido tiver esgotado o setor, o filtro não casa, `modified_count` é 0, nada é incrementado e a API responde **409**. Assim `vendidos` nunca ultrapassa `capacidade`.
   - Grava o pedido em `pedidos` com status `confirmado`, invalida o cache do evento e publica o pedido no canal `pedidos:confirmados`.

### Bônus — Pub/Sub

A cada pedido confirmado, a API executa `PUBLISH pedidos:confirmados <json do pedido>`. O script [subscriber.py](subscriber.py) assina o canal e registra cada mensagem no console:

```
[subscriber] Ouvindo o canal 'pedidos:confirmados'... (Ctrl+C para sair)
[subscriber] Pedido confirmado: id=6ae3df25... evento=6ae3defd... setor=Plateia Única qtd=2 total=R$ 140.00
```

## Roteiro do vídeo (comandos)

1. `docker compose up --build`
2. `GET /eventos/{id}` duas vezes → `"origem": "banco"` e depois `"origem": "cache"`.
3. `PUT /eventos/{id}` → `GET /eventos/{id}` volta a mostrar `"origem": "banco"`.
4. `POST /reservas` → no Redis: `docker compose exec redis redis-cli TTL reserva:<reservaId>` (≈ 600) → `POST /pedidos/confirmar` (com o `subscriber.py` aberto em outro terminal).
5. Reserva expirada: crie outra reserva e force a expiração com `docker compose exec redis redis-cli EXPIRE reserva:<reservaId> 1` (para não esperar 10 minutos); em seguida `POST /pedidos/confirmar` → **410**.
6. `docker compose exec api python demo_limite.py` → 10 respostas 201 e a 11ª **429**.
7. `GET /eventos/ranking`, `GET /relatorios/faturamento` e `GET /relatorios/ocupacao/{id}`.
