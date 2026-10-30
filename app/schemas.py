"""Modelos de entrada da API (validação com Pydantic)."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class Local(BaseModel):
    cidade: str
    endereco: str


class Setor(BaseModel):
    nome: str
    preco: float = Field(ge=0)
    capacidade: int = Field(gt=0)
    vendidos: int = Field(default=0, ge=0)


class EventoIn(BaseModel):
    # extra="allow": eventos podem ter campos próprios (ex.: classificacaoEtaria),
    # aproveitando o esquema flexível do MongoDB
    model_config = ConfigDict(extra="allow")

    nome: str
    categoria: str
    data: datetime
    local: Local
    atracoes: list[str] = []
    setores: list[Setor]


class EventoUpdate(BaseModel):
    model_config = ConfigDict(extra="allow")

    nome: Optional[str] = None
    categoria: Optional[str] = None
    data: Optional[datetime] = None
    local: Optional[Local] = None
    atracoes: Optional[list[str]] = None
    setores: Optional[list[Setor]] = None


class ReservaIn(BaseModel):
    usuarioId: str
    eventoId: str
    setor: str
    quantidade: int = Field(gt=0, le=10)


class ConfirmacaoIn(BaseModel):
    reservaId: str
