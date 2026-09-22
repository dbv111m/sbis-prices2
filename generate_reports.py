"""Генерация отчетов (CSV/Excel) из данных, собранных optimized_scraper.py.

CSV — плоская таблица с колонками «Группа | Услуга | Код | регионы».
Excel — оформленный лист с секциями-заголовками по группам услуг.

Человекочитаемые названия и группы берутся из nomenclature_map.json (--map).
Для кодов, которых нет в mapping, используется имя с сайта (поле name из
данных скрапинга) и группа «Прочее».

Примеры запуска:
    python generate_reports.py
    python generate_reports.py --input edo_optimized_scraped_data.json
    python generate_reports.py --input data.json --prefix my_report
"""

import argparse
import json
import os
import sys
from collections import OrderedDict

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

NO_DATA = "Нет данных"
DEFAULT_GROUP = "Прочее"
DEFAULT_MAP_FILE = "nomenclature_map.json"
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
    parser.add_argument(
        "--map",
        default=DEFAULT_MAP_FILE,
        help=f"JSON-файл с расшифровкой кодов номенклатуры (по умолчанию: {DEFAULT_MAP_FILE})",
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


def load_mapping(path):
    """Загружает расшифровку кодов номенклатуры. Возвращает None, если файла нет."""
    if not os.path.exists(path):
        print(f"Внимание: файл расшифровки {path} не найден — "
              f"все услуги попадут в группу «{DEFAULT_GROUP}».")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print(f"Внимание: {path} содержит некорректный JSON ({e}) — "
              f"работаем без расшифровки.")
        return None


def build_rows(data, mapping):
    """Строит отсортированный список строк (group, name, code, {регион: цена}).

    Название: приоритет — mapping, затем имя с сайта (name), затем код.
    Группа: из mapping, иначе «Прочее».
    """
    codes_map = mapping.get("codes", {}) if mapping else {}
    group_order = mapping.get("group_order", []) if mapping else []

    # Индексируем цены по коду номенклатуры (O(N) вместо O(N^2))
    # и собираем имена услуг с сайта (если скрапер их сохранил)
    region_maps = {}
    site_names = {}
    for region_name, items in data.items():
        region_maps[region_name] = {}
        for item in items:
            code = item["nomenclature_code"]
            region_maps[region_name][code] = item["price"]
            if not site_names.get(code) and item.get("name"):
                site_names[code] = item["name"]

    def group_rank(group):
        if group in group_order:
            return group_order.index(group)
        return len(group_order) + (1 if group == DEFAULT_GROUP else 0)

    rows = []
    for code in sorted({c for m in region_maps.values() for c in m}):
        entry = codes_map.get(code, {})
        name = entry.get("name") or site_names.get(code) or code
        group = entry.get("group") or DEFAULT_GROUP
        prices = {region: m.get(code, NO_DATA) for region, m in region_maps.items()}
        rows.append((group, name, code, prices))

    rows.sort(key=lambda r: (group_rank(r[0]), r[0], r[1], r[2]))
    return rows


def write_csv(filename, rows):
    """CSV: плоская таблица Группа | Услуга | Код | регионы."""
    records = []
    for group, name, code, prices in rows:
        records.append({"Группа": group, "Услуга": name, "Код": code, **prices})
    df = pd.DataFrame(records)
    # utf-8-sig, чтобы Excel корректно открывал кириллицу
    df.to_csv(filename, encoding="utf-8-sig", index=False)


def write_excel(filename, rows, regions):
    """Excel: секции-заголовки по группам, внутри — Услуга | Код | регионы."""
    headers = ["Услуга", "Код"] + list(regions)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4472C4")
    group_font = Font(bold=True)
    group_fill = PatternFill("solid", fgColor="DDEBF7")

    wb = Workbook()
    ws = wb.active
    ws.title = "Тарифы"

    ws.append(headers)
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # Группируем отсортированные строки в секции (порядок групп уже учтен сортировкой)
    sections = OrderedDict()
    for group, name, code, prices in rows:
        sections.setdefault(group, []).append([name, code] + [prices[r] for r in regions])

    for group, section_rows in sections.items():
        ws.append([group] + [""] * (len(headers) - 1))
        group_row = ws.max_row
        for col in range(1, len(headers) + 1):
            cell = ws.cell(group_row, col)
            cell.font = group_font
            cell.fill = group_fill
        ws.merge_cells(
            start_row=group_row, start_column=1, end_row=group_row, end_column=len(headers)
        )
        for row in section_rows:
            ws.append(row)

    # Ширины колонок и закрепление шапки
    ws.column_dimensions["A"].width = 48
    ws.column_dimensions["B"].width = 20
    for col in range(3, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 15
    ws.freeze_panes = "C2"

    wb.save(filename)


def generate_reports(input_file, prefix, map_file):
    # Загружаем данные из JSON файла
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Файл {input_file} не найден. Сначала запустите скрипт скрапинга.")
        sys.exit(1)

    mapping = load_mapping(map_file)
    rows = build_rows(data, mapping)
    regions = list(data.keys())

    base = f"{prefix}_nomenclature_prices_report" if prefix else "nomenclature_prices_report"

    csv_filename = f"{base}.csv"
    write_csv(csv_filename, rows)
    print(f"CSV отчет сохранен: {csv_filename}")

    excel_filename = f"{base}.xlsx"
    write_excel(excel_filename, rows, regions)
    print(f"Excel отчет сохранен: {excel_filename}")

    groups = OrderedDict((group, 0) for group, *_ in rows)
    for group, *_ in rows:
        groups[group] += 1
    unmapped = sum(1 for group, _, code, _ in rows if group == DEFAULT_GROUP)

    print("\nСтатистика:")
    print(f"Всего уникальных номенклатур: {len(rows)}")
    print(f"Всего регионов: {len(data)}")
    print(f"Группы: {', '.join(f'{g} ({n})' for g, n in groups.items())}")
    if unmapped:
        print(f"Внимание: {unmapped} кодов без расшифровки попали в «{DEFAULT_GROUP}» — "
              f"дополните {map_file}.")


def main():
    args = parse_args()
    prefix = args.prefix if args.prefix is not None else derive_prefix(args.input)
    generate_reports(args.input, prefix, args.map)


if __name__ == "__main__":
    main()
