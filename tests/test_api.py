import datetime as dt
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

import rsb3

FIXTURE = Path(__file__).parent / "fixtures" / "COTAHIST_D20250602.TXT"
RECORD = 245 + 2  # bytes por linha, com CRLF


def test_versoes_e_esquema():
    assert rsb3.__version__
    assert rsb3.CRATE_VERSION == "0.2.0"
    assert rsb3.SCHEMA_VERSION == "v1"
    schema = rsb3.schema()
    assert isinstance(schema, pa.Schema)
    assert schema.names[:3] == ["refdate", "bdi_code", "symbol"]
    assert len(schema) == 25
    assert schema.field("open_cents").type == pa.int64()
    assert not schema.field("open_cents").nullable
    assert schema.field("maturity_date").nullable


def test_parse_fixture():
    t = rsb3.parse(FIXTURE)
    assert isinstance(t, pa.Table)
    assert t.num_rows == 6
    assert t.schema.equals(rsb3.schema())
    assert t["symbol"][0].as_py() == "PETR4"
    # 2 decimais implícitos -> centavos inteiros, nunca float
    assert t["open_cents"][0].as_py() == 3210
    assert t["close_cents"][0].as_py() == 3255
    assert t["volume_cents"][0].as_py() == 147_993_516_000
    assert t["refdate"][0].as_py() == dt.date(2025, 6, 2)
    # mercado à vista: PRAZOT em branco e DATVEN 99991231 viram null
    assert t["days_to_settlement"][0].as_py() is None
    assert t["maturity_date"][0].as_py() is None
    # papel sem negócio traz zeros, não nulls
    assert t["symbol"][5].as_py() == "XPTO3F"
    assert t["close_cents"][5].as_py() == 0


def test_parse_bytes_igual_a_parse():
    assert rsb3.parse_bytes(FIXTURE.read_bytes()).equals(rsb3.parse(FIXTURE))


def test_arquivo_truncado_e_layout_error():
    data = FIXTURE.read_bytes()
    sem_trailer = data[: -RECORD]
    with pytest.raises(rsb3.LayoutError, match="sem trailer"):
        rsb3.parse_bytes(sem_trailer)
    assert issubclass(rsb3.LayoutError, ValueError)


def test_largura_errada_e_layout_error_com_linha():
    with pytest.raises(rsb3.LayoutError, match="linha 1"):
        rsb3.parse_bytes(b"01202506029XCURTO\n")


def test_campo_corrompido_e_record_error_com_linha():
    data = bytearray(FIXTURE.read_bytes())
    data[RECORD + 56] = ord("X")  # PREABE da primeira cotação (linha 2)
    with pytest.raises(rsb3.RecordError, match="linha 2"):
        rsb3.parse_bytes(bytes(data))


def test_arquivo_inexistente_e_oserror(tmp_path):
    with pytest.raises(OSError):
        rsb3.parse(tmp_path / "nao-existe.TXT")


def test_roundtrip_parquet(tmp_path):
    t = rsb3.parse(FIXTURE)
    out = tmp_path / "cotahist.parquet"
    rsb3.to_parquet(t, out)
    back = pq.read_table(out)
    assert back.num_rows == 6
    assert back.schema.remove_metadata().equals(rsb3.schema())
    assert back["close_cents"].to_pylist() == t["close_cents"].to_pylist()
    # RecordBatch solto e lista também servem
    rsb3.to_parquet(t.to_batches()[0], tmp_path / "b.parquet")
    rsb3.to_parquet(t.to_batches(), tmp_path / "c.parquet")


def test_to_parquet_recusa_esquema_diferente(tmp_path):
    t = rsb3.parse(FIXTURE).append_column("extra", pa.array([1] * 6))
    with pytest.raises(ValueError):
        rsb3.to_parquet(t, tmp_path / "x.parquet")


def test_nomes_oficiais():
    assert rsb3.file_name(2025) == "COTAHIST_A2025.ZIP"
    assert rsb3.file_name((2026, 9)) == "COTAHIST_M092026.ZIP"
    assert rsb3.file_name(dt.date(2025, 6, 2)) == "COTAHIST_D02062025.ZIP"
    with pytest.raises(ValueError, match="mês"):
        rsb3.file_name((2026, 13))
    with pytest.raises(TypeError):
        rsb3.file_name("2025")


def test_fetch_reaproveita_cache_sem_rede(tmp_path):
    # Com o TXT já no cache, fetch devolve o caminho sem tocar na rede.
    cached = tmp_path / "COTAHIST_D02062025.TXT"
    cached.write_bytes(FIXTURE.read_bytes())
    path = rsb3.fetch(dt.date(2025, 6, 2), tmp_path)
    assert Path(path) == cached
    assert rsb3.load(dt.date(2025, 6, 2), tmp_path).num_rows == 6


@pytest.mark.network
def test_fetch_diario_oficial(tmp_path):
    # Dia útil recente; o arquivo diário tem ~600 KB zipado.
    t = rsb3.load(dt.date(2026, 10, 28), tmp_path)
    assert t.num_rows > 10_000
    assert (tmp_path / "COTAHIST_D28102026.manifest.json").exists()
