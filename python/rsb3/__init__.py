"""Arquivos públicos da B3 em Arrow: parser estrito do COTAHIST, em Rust.

O **COTAHIST** é o arquivo oficial de cotações históricas do pregão da B3
(posicional, 245 bytes, preços com 2 decimais implícitos). Este pacote
compila o crate Rust ``rsb3`` (https://crates.io/crates/rsb3) e entrega o
resultado como ``pyarrow.Table`` no esquema congelado ``v1``:

- preços são **inteiros em centavos** (``open_cents``, ``close_cents``, ...);
  converter para float é decisão sua, nunca do parser;
- **nenhuma linha é descartada em silêncio**: largura errada, tipo de registro
  desconhecido, campo inválido ou arquivo truncado (sem trailer) são exceções
  com número de linha.

>>> import rsb3
>>> table = rsb3.load(2025, cache_dir="data")        # doctest: +SKIP
>>> table.filter(pc.field("symbol") == "PETR4")      # doctest: +SKIP
"""

from __future__ import annotations

import datetime as _dt
import os as _os
from typing import Iterable, Tuple, Union

import pyarrow as pa

from . import _rsb3
from ._rsb3 import (
    CRATE_VERSION,
    SCHEMA_VERSION,
    DownloadError,
    LayoutError,
    RecordError,
    __version__,
    file_name,
    schema,
)

__all__ = [
    "CRATE_VERSION",
    "SCHEMA_VERSION",
    "DownloadError",
    "LayoutError",
    "RecordError",
    "Period",
    "__version__",
    "fetch",
    "file_name",
    "load",
    "parse",
    "parse_bytes",
    "schema",
    "to_parquet",
]

#: Período de um arquivo oficial: ``2025`` (anual), ``(2025, 6)`` (mensal) ou
#: ``datetime.date(2025, 6, 2)`` (diário).
Period = Union[int, Tuple[int, int], _dt.date]

_PathLike = Union[str, "_os.PathLike[str]"]


def fetch(period: Period, cache_dir: _PathLike = "data") -> str:
    """Baixa (ou reaproveita do cache) o arquivo oficial e devolve o caminho do TXT.

    O ZIP original fica imutável em ``cache_dir`` com SHA-256 e manifesto de
    ingestão (``<nome>.manifest.json``); o TXT extraído fica ao lado. Se o TXT
    já existe, nada é baixado.
    """
    return _os.fspath(_rsb3.fetch(period, _os.fspath(cache_dir)))


def parse(path: _PathLike) -> pa.Table:
    """Lê um TXT do COTAHIST e devolve um ``pyarrow.Table`` no esquema v1."""
    return pa.Table.from_batches([_rsb3.parse(_os.fspath(path))])


def parse_bytes(data: bytes) -> pa.Table:
    """Mesmo que :func:`parse`, sobre o conteúdo do arquivo já em memória."""
    return pa.Table.from_batches([_rsb3.parse_bytes(bytes(data))])


def load(period: Period, cache_dir: _PathLike = "data") -> pa.Table:
    """:func:`fetch` seguido de :func:`parse`."""
    return parse(fetch(period, cache_dir))


def to_parquet(
    data: Union[pa.Table, pa.RecordBatch, Iterable[pa.RecordBatch]],
    path: _PathLike,
) -> None:
    """Grava em Parquet (Snappy) exigindo o esquema v1 — a saída de :func:`parse`.

    Um ``Table`` com outro esquema (coluna a mais, tipo diferente) é recusado:
    o esquema é o contrato do dataset.
    """
    if isinstance(data, pa.Table):
        batches = data.to_batches()
    elif isinstance(data, pa.RecordBatch):
        batches = [data]
    else:
        batches = list(data)
    _rsb3.to_parquet(batches, _os.fspath(path))
