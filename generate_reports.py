"""Генерация отчетов (CSV/Excel) из данных, собранных optimized_scraper.py.

Строит таблицу: строки — номенклатуры, столбцы — регионы.

Примеры запуска:
    python generate_reports.py                                        # optimized_scraped_data.json -> nomenclature_prices_report.*
    python generate_reports.py --input edo_optimized_scraped_data.json    # -> edo_nomenclature_prices_report.*
    python generate_reports.py --input data.json --prefix my_report    # -> my_report_nomenclature_prices_report.*
"""

import argparse
import json
import os
import sys

import pandas as pd

NO_DATA = "Нет данных"
INPUT_SUFFIX = "_optimized_scraped_data"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Создание CSV/Excel отчетов из собранных данных о ценах"
    )
    parser.add_argument(
        "--input",
        default="optimized_scraped_data.json",
        help="Входной JSON-файл с данными скрапинга (по умолчанию: optimized_scraped_data.json)",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help=(
            "Префикс имен отчетов. По умолчанию определяется из имени входного файла: "
            "edo_optimized_scraped_data.json -> edo_nomenclature_prices_report.*"
        ),
    )
    return parser.parse_args()


def derive_prefix(input_file):
    """Определяет префикс отчета из имени входного файла.

    edo_optimized_scraped_data.json -> "edo"
    optimized_scraped_data.json -> ""
    data.json -> "data"
    """
    stem = os.path.splitext(os.path.basename(input_file))[0]
    if stem.endswith(INPUT_SUFFIX):
        stem = stem[: -len(INPUT_SUFFIX)]
    elif stem == INPUT_SUFFIX.lstrip("_"):
        stem = ""
    return stem


def generate_reports(input_file, prefix):
    # Загружаем данные из JSON файла
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Файл {input_file} не найден. Сначала запустите скрипт скрапинга.")
        sys.exit(1)

    # Индексируем цены каждого региона по коду номенклатуры (O(N) вместо O(N^2))
    region_maps = {
        region_name: {item["nomenclature_code"]: item["price"] for item in items}
        for region_name, items in data.items()
    }

    # Собираем уникальные номенклатуры из всех регионов
    all_nomenclatures = sorted({code for m in region_maps.values() for code in m})

    # Строим таблицу: строки - номенклатура, столбцы - регионы
    rows = [
        {region_name: m.get(nomenclature, NO_DATA) for region_name, m in region_maps.items()}
        for nomenclature in all_nomenclatures
    ]
    df = pd.DataFrame(rows, index=all_nomenclatures, columns=list(region_maps))
    df.index.name = "Номенклатура"

    base = f"{prefix}_nomenclature_prices_report" if prefix else "nomenclature_prices_report"

    # Сохраняем в CSV (utf-8-sig, чтобы Excel корректно открывал кириллицу)
    csv_filename = f"{base}.csv"
    df.to_csv(csv_filename, encoding="utf-8-sig")
    print(f"CSV отчет сохранен: {csv_filename}")

    # Сохраняем в Excel
    excel_filename = f"{base}.xlsx"
    df.to_excel(excel_filename, engine="openpyxl")
    print(f"Excel отчет сохранен: {excel_filename}")

    print("\nСтатистика:")
    print(f"Всего уникальных номенклатур: {len(all_nomenclatures)}")
    print(f"Всего регионов: {len(data)}")
    print(f"Размер таблицы: {len(all_nomenclatures)} x {len(data)}")


def main():
    args = parse_args()
    prefix = args.prefix if args.prefix is not None else derive_prefix(args.input)
    generate_reports(args.input, prefix)


if __name__ == "__main__":
    main()
