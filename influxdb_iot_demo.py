"""
Demo de uso do dataset iot_telemetry_data.csv com InfluxDB 2.x.

Operacoes cobertas:
- criar bucket no InfluxDB;
- inserir dados do CSV em formato line protocol;
- consultar leituras por dispositivo;
- deletar dados por intervalo de tempo.

Antes de executar, configure as variaveis de ambiente ou use os valores padrao:
  INFLUX_URL=http://localhost:8086
  INFLUX_ORG=ecom041
  INFLUX_TOKEN=ecom041-token
  INFLUX_BUCKET=iot_telemetry
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "iot_telemetry_data.csv"

INFLUX_URL = os.getenv("INFLUX_URL", "http://localhost:8086").rstrip("/")
INFLUX_ORG = os.getenv("INFLUX_ORG", "ecom041")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET", "iot_telemetry")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "ecom041-token")

MEASUREMENT = "environmental_telemetry"


def http_request(
    method: str,
    path: str,
    *,
    body: bytes | str | None = None,
    content_type: str = "application/json",
    expected_status: tuple[int, ...] = (200, 201, 204),
) -> bytes:
    if isinstance(body, str):
        body = body.encode("utf-8")

    headers = {"Authorization": f"Token {INFLUX_TOKEN}"}
    if body is not None:
        headers["Content-Type"] = content_type

    request = Request(
        f"{INFLUX_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(request, timeout=30) as response:
            data = response.read()
            if response.status not in expected_status:
                raise RuntimeError(f"Status inesperado: {response.status}; resposta={data!r}")
            return data
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Erro HTTP {exc.code} em {method} {path}: {details}") from exc
    except URLError as exc:
        raise RuntimeError(
            f"Nao foi possivel conectar ao InfluxDB em {INFLUX_URL}. "
            "Verifique se o servidor esta em execucao."
        ) from exc


def get_org_id() -> str:
    data = http_request("GET", f"/api/v2/orgs?org={quote(INFLUX_ORG)}")
    payload = json.loads(data.decode("utf-8"))
    orgs = payload.get("orgs", [])
    if not orgs:
        raise RuntimeError(f"Organizacao nao encontrada no InfluxDB: {INFLUX_ORG}")
    return orgs[0]["id"]


def ensure_bucket() -> None:
    org_id = get_org_id()
    data = http_request("GET", f"/api/v2/buckets?name={quote(INFLUX_BUCKET)}")
    payload = json.loads(data.decode("utf-8"))
    if payload.get("buckets"):
        print(f"Bucket ja existe: {INFLUX_BUCKET}")
        return

    body = {
        "orgID": org_id,
        "name": INFLUX_BUCKET,
        "retentionRules": [],
    }
    http_request("POST", "/api/v2/buckets", body=json.dumps(body))
    print(f"Bucket criado: {INFLUX_BUCKET}")


def escape_tag(value: str) -> str:
    return value.replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def bool_to_lp(value: str) -> str:
    return "true" if value.strip().lower() == "true" else "false"


def row_to_line_protocol(row: dict[str, str]) -> str:
    timestamp_ns = int(Decimal(row["ts"]) * Decimal("1000000000"))
    device = escape_tag(row["device"])

    fields = [
        f'co={float(row["co"])}',
        f'humidity={float(row["humidity"])}',
        f'light={bool_to_lp(row["light"])}',
        f'lpg={float(row["lpg"])}',
        f'motion={bool_to_lp(row["motion"])}',
        f'smoke={float(row["smoke"])}',
        f'temp={float(row["temp"])}',
    ]
    return f"{MEASUREMENT},device={device} {','.join(fields)} {timestamp_ns}"


def iter_line_protocol(csv_path: Path, limit: int | None = None) -> Iterable[str]:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if limit is not None and index >= limit:
                break
            yield row_to_line_protocol(row)


def insert_csv(limit: int | None, batch_size: int) -> None:
    ensure_bucket()

    query = (
        f"/api/v2/write?org={quote(INFLUX_ORG)}"
        f"&bucket={quote(INFLUX_BUCKET)}&precision=ns"
    )
    total = 0
    batch: list[str] = []

    for line in iter_line_protocol(CSV_PATH, limit=limit):
        batch.append(line)
        if len(batch) >= batch_size:
            http_request("POST", query, body="\n".join(batch), content_type="text/plain")
            total += len(batch)
            print(f"Inseridos {total} pontos...")
            batch.clear()

    if batch:
        http_request("POST", query, body="\n".join(batch), content_type="text/plain")
        total += len(batch)

    print(f"Ingestao finalizada. Total de pontos inseridos: {total}")


def query_data(limit: int) -> None:
    flux = f"""
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: 2020-07-12T00:00:00Z, stop: 2020-07-20T00:00:00Z)
  |> filter(fn: (r) => r._measurement == "{MEASUREMENT}")
  |> filter(fn: (r) => r._field == "temp" or r._field == "humidity")
  |> limit(n: {limit})
"""
    body = {"query": flux, "type": "flux"}
    data = http_request("POST", f"/api/v2/query?org={quote(INFLUX_ORG)}", body=json.dumps(body))
    print(data.decode("utf-8", errors="replace"))


def delete_data() -> None:
    body = {
        "start": "2020-07-12T00:00:00Z",
        "stop": "2020-07-20T00:00:00Z",
        "predicate": f'_measurement="{MEASUREMENT}"',
    }
    path = f"/api/v2/delete?org={quote(INFLUX_ORG)}&bucket={quote(INFLUX_BUCKET)}"
    http_request("POST", path, body=json.dumps(body))
    print(f"Dados deletados do measurement {MEASUREMENT} no bucket {INFLUX_BUCKET}.")


def show_sample() -> None:
    with CSV_PATH.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        row = next(reader)

    print("Primeira linha do CSV:")
    print(json.dumps(row, indent=2))
    print("\nMesmo registro em line protocol:")
    print(row_to_line_protocol(row))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Operacoes simples com InfluxDB e dataset IoT.")
    parser.add_argument(
        "command",
        choices=("sample", "create-bucket", "insert", "query", "delete"),
        help="Operacao a executar.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Quantidade maxima de linhas para inserir ou consultar. Use 0 para inserir o CSV inteiro.",
    )
    parser.add_argument("--batch-size", type=int, default=5000, help="Tamanho do lote de escrita.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not CSV_PATH.exists():
        print(f"CSV nao encontrado: {CSV_PATH}", file=sys.stderr)
        return 1

    if args.command == "sample":
        show_sample()
    elif args.command == "create-bucket":
        ensure_bucket()
    elif args.command == "insert":
        limit = None if args.limit == 0 else args.limit
        insert_csv(limit=limit, batch_size=args.batch_size)
    elif args.command == "query":
        query_data(limit=args.limit)
    elif args.command == "delete":
        delete_data()
    else:
        raise AssertionError(args.command)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
