#!/usr/bin/env python3

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent
BASE_URL = "https://api-medidas-porto-7bni.onrender.com/dados/{sensor_id}/ultimos-dias?page={page}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Baixa todas as páginas de dados de um sensor da API."
    )
    parser.add_argument("--sensor-id", required=True, help="Identificador do sensor")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Pasta onde os arquivos paginaN.json serão salvos",
    )
    parser.add_argument(
        "--base-url",
        default=BASE_URL,
        help="Template da URL da API. Use {sensor_id} e {page}.",
    )
    return parser.parse_args()


def fetch_page(url: str) -> dict:
    with urlopen(url) as response:
        return json.load(response)


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(exist_ok=True)

    first_page_url = args.base_url.format(sensor_id=args.sensor_id, page=1)
    try:
        first_page = fetch_page(first_page_url)
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"Falha ao baixar a primeira página: {exc}") from exc

    total_pages = int(first_page.get("total_paginas", 1))
    write_json(output_dir / "pagina1.json", first_page)

    for page in range(2, total_pages + 1):
        page_url = args.base_url.format(sensor_id=args.sensor_id, page=page)
        try:
            payload = fetch_page(page_url)
        except (HTTPError, URLError) as exc:
            raise SystemExit(f"Falha ao baixar a página {page}: {exc}") from exc
        write_json(output_dir / f"pagina{page}.json", payload)

    metadata = {
        "sensor_id": args.sensor_id,
        "base_url": args.base_url,
        "total_paginas": total_pages,
        "output_dir": str(output_dir),
    }
    write_json(output_dir / "_download_metadata.json", metadata)


if __name__ == "__main__":
    main()
