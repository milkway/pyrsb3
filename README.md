# pyrsb3

> Arquivos públicos da B3 em Arrow — parser estrito do COTAHIST com preços em
> centavos inteiros, em Rust. *B3 (Brazilian stock exchange) public files as
> Arrow: a strict COTAHIST parser with integer-cent prices, in Rust.*

Bindings Python do crate [`rsb3`](https://crates.io/crates/rsb3). O parser, o
download com cache e a escrita Parquet são do crate; este pacote só converte,
e entrega o resultado como `pyarrow.Table` pela Arrow C Data Interface, sem
cópia. O GIL é solto enquanto o Rust trabalha.

```bash
pip install pyrsb3
```

```python
import datetime as dt
import pyarrow.compute as pc
import rsb3

table = rsb3.load(2025, cache_dir="data")          # download + cache + SHA-256 + manifesto + parse
petr4 = table.filter(pc.field("symbol") == "PETR4")
petr4.to_pandas()                                   # ou polars.from_arrow(petr4)

rsb3.load((2026, 9), "data")                        # arquivo mensal
rsb3.load(dt.date(2026, 10, 28), "data")            # arquivo diário
rsb3.to_parquet(table, "cotahist_2025.parquet")     # Parquet no esquema v1
```

Três decisões do crate valem aqui:

1. **O esquema é o contrato.** `rsb3.schema()` é o esquema Arrow versionado
   (`v1`, 25 colunas, congelado): mudança de esquema gera versão nova.
2. **Preços são inteiros em centavos** (`open_cents`, `close_cents`, …).
   Converter para float é decisão sua, nunca do parser.
3. **Nenhuma linha é descartada em silêncio.** Largura errada, tipo de
   registro desconhecido ou arquivo truncado levantam `rsb3.LayoutError`;
   campo inválido levanta `rsb3.RecordError`; as duas com o número da linha.

## API

| Função | O que faz |
|---|---|
| `fetch(period, cache_dir="data") -> str` | baixa o ZIP oficial (ou reaproveita o cache) e devolve o caminho do TXT |
| `parse(path) -> pyarrow.Table` | TXT posicional → Arrow |
| `parse_bytes(data) -> pyarrow.Table` | idem, de bytes em memória |
| `load(period, cache_dir="data") -> pyarrow.Table` | `fetch` + `parse` |
| `to_parquet(table_or_batches, path)` | Parquet Snappy, exigindo o esquema v1 |
| `schema() -> pyarrow.Schema` | o contrato |
| `file_name(period) -> str` | nome oficial do ZIP, como publicado pela B3 |

`period` é `2025` (anual), `(2025, 6)` (mensal) ou `datetime.date` (diário).
`CRATE_VERSION` diz qual versão do `rsb3` está compilada no pacote.

## Validação

O crate é testado diferencialmente contra o pacote R
[`{rb3}`](https://github.com/ropensci/rb3) (rOpenSci), nas 25 colunas, sobre o
ano de 2025 completo (3.174.698 linhas). Os testes deste pacote cobrem a
conversão: esquema, nulls, exceções e o roundtrip Parquet.

```bash
uv venv -p 3.12 .venv && uv pip install -p .venv maturin pytest pyarrow
.venv/bin/maturin develop --release
.venv/bin/pytest                 # -m network inclui um download oficial
```

## Licença

MIT.
