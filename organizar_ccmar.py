#!/usr/bin/env python3

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def parse_page_number(path: Path) -> int:
    return int(path.stem.replace("pagina", ""))


def parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_iso8601(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z").replace("Z", ".000Z")


def infer_interval_minutes(records: list[dict]) -> int | None:
    if len(records) < 2:
        return None

    deltas = []
    for current, nxt in zip(records, records[1:]):
        current_dt = parse_iso8601(current["data_hora"])
        next_dt = parse_iso8601(nxt["data_hora"])
        diff = int((next_dt - current_dt).total_seconds() // 60)
        if diff > 0:
            deltas.append(diff)

    if not deltas:
        return None

    return Counter(deltas).most_common(1)[0][0]


def load_records(data_dir: Path) -> tuple[list[dict], list[Path]]:
    page_files = sorted(data_dir.glob("pagina*.json"), key=parse_page_number)
    if not page_files:
        raise FileNotFoundError(f"Nenhum arquivo pagina*.json encontrado em {data_dir}")

    records = []
    for page_file in page_files:
        payload = json.loads(page_file.read_text())
        records.extend(payload.get("dados", []))

    deduplicated = {
        (record["data_hora"], record["sensor_id"]): record
        for record in records
    }

    ordered = sorted(deduplicated.values(), key=lambda item: item["data_hora"])
    return ordered, page_files


def build_missing_timestamps(records: list[dict]) -> list[str]:
    interval_minutes = infer_interval_minutes(records)
    if not interval_minutes:
        return []

    start = parse_iso8601(records[0]["data_hora"])
    end = parse_iso8601(records[-1]["data_hora"])
    expected = set()
    current = start
    while current <= end:
        expected.add(format_iso8601(current))
        current += timedelta(minutes=interval_minutes)

    actual = {record["data_hora"] for record in records}
    return sorted(expected - actual)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Consolida arquivos paginados pagina*.json em uma pasta organizada."
    )
    parser.add_argument(
        "--data-dir",
        default=str(ROOT / "data"),
        help="Pasta com os arquivos pagina*.json",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT / "CCMAR"),
        help="Pasta de saída para os arquivos consolidados",
    )
    parser.add_argument(
        "--local-name",
        default="CCMAR",
        help="Nome do local associado às medições",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    daily_dir = output_dir / "por_dia"

    records, page_files = load_records(data_dir)
    output_dir.mkdir(exist_ok=True)
    daily_dir.mkdir(exist_ok=True)

    sensor_ids = sorted({record["sensor_id"] for record in records})
    grouped_by_day: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped_by_day[record["data_hora"][:10]].append(record)

    interval_minutes = infer_interval_minutes(records)
    missing_timestamps = build_missing_timestamps(records)

    resumo = {
        "local": args.local_name,
        "origem": {
            "diretorio": str(data_dir),
            "arquivos_processados": len(page_files),
            "arquivos": [path.name for path in page_files],
        },
        "sensor_ids": sensor_ids,
        "sensor_unico": len(sensor_ids) == 1,
        "total_registros": len(records),
        "dias_cobertos": len(grouped_by_day),
        "periodo": {
            "inicio": records[0]["data_hora"],
            "fim": records[-1]["data_hora"],
        },
        "intervalo_predominante_minutos": interval_minutes,
        "horarios_faltantes": missing_timestamps,
        "registros_por_dia": {
            day: len(day_records) for day, day_records in sorted(grouped_by_day.items())
        },
    }

    dados_consolidados = {
        "local": args.local_name,
        "sensor_id": sensor_ids[0] if len(sensor_ids) == 1 else sensor_ids,
        "total_registros": len(records),
        "periodo": resumo["periodo"],
        "intervalo_predominante_minutos": interval_minutes,
        "horarios_faltantes": missing_timestamps,
        "dados": records,
    }

    write_json(output_dir / "resumo.json", resumo)
    write_json(output_dir / "dados_consolidados.json", dados_consolidados)

    for day, day_records in sorted(grouped_by_day.items()):
        daily_payload = {
            "data": day,
            "local": args.local_name,
            "sensor_id": sensor_ids[0] if len(sensor_ids) == 1 else sensor_ids,
            "total_registros": len(day_records),
            "dados": day_records,
        }
        write_json(daily_dir / f"{day}.json", daily_payload)

    with (output_dir / "medicoes.csv").open("w", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "local",
                "data",
                "hora",
                "data_hora",
                "valor",
                "sensor_id",
                "criado_em",
            ],
        )
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "local": args.local_name,
                    "data": record["data_hora"][:10],
                    "hora": record["data_hora"][11:19],
                    "data_hora": record["data_hora"],
                    "valor": record["valor"],
                    "sensor_id": record["sensor_id"],
                    "criado_em": record["criado_em"],
                }
            )


if __name__ == "__main__":
    main()
