"""Поиск цен в уже скачанных данных saby.ru по городу и/или названию услуги.

Работает по файлам *_optimized_scraped_data.json (20 вкладок, 90 регионов,
254 услуги) без обращения к сети. Названия услуг — из nomenclature_map.json
и поля name в данных; поиск по вхождению подстроки (без учёта регистра).

Примеры:
    python find_price.py --city Казань                      # все услуги региона
    python find_price.py --city СПб --service "ЭДО — Базовый"
    python find_price.py --service маркировка               # цены по всем регионам
    python find_price.py --service ЭТрН --tab edo           # по одной вкладке
    python find_price.py --city Москва --service ЭДО        # точечный запрос
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import Counter

# Крупные города -> регионы saby (цены привязаны к регионам)
CITY_ALIASES = {
    "москва": "Москва",
    "мск": "Москва",
    "санкт-петербург": "Санкт-Петербург",
    "спб": "Санкт-Петербург",
    "питер": "Санкт-Петербург",
    "новосибирск": "Новосибирская обл.",
    "екатеринбург": "Свердловская обл.",
    "казань": "Республика Татарстан",
    "нижний новгород": "Нижегородская обл.",
    "челябинск": "Челябинская обл.",
    "самара": "Самарская обл.",
    "тольятти": "Тольятти",
    "омск": "Омская обл.",
    "ростов-на-дону": "Ростовская обл.",
    "уфа": "Республика Башкортостан",
    "красноярск": "Красноярский край",
    "воронеж": "Воронежская обл.",
    "пермь": "Пермский край",
    "волгоград": "Волгоградская обл.",
    "краснодар": "Краснодарский край",
    "севастополь": "Севастополь",
    "симферополь": "Республика Крым",
    "крым": "Республика Крым",
}


def norm(text):
    return re.sub(r"\s+", " ", str(text)).strip().lower()


def parse_args():
    parser = argparse.ArgumentParser(description="Поиск цен по городу и услуге в скачанных данных")
    parser.add_argument("--city", default=None, help="Город или регион (Казань, СПб, Свердловская...)")
    parser.add_argument("--service", default=None, help="Название услуги или код (продукт, ЭДО — Базовый, ETRN_50000)")
    parser.add_argument("--tab", default=None, help="Только указанная вкладка (edo, retail, ...)")
    return parser.parse_args()


def find_data_files(tab=None):
    files = sorted(glob.glob("*_optimized_scraped_data.json"))
    if tab:
        files = [f for f in files if os.path.basename(f).startswith(f"{tab}_")]
    return files


def resolve_regions(all_regions, city):
    """Город -> список регионов данных (алиас или вхождение подстроки)."""
    key = norm(city)
    if key in CITY_ALIASES:
        name = CITY_ALIASES[key]
        return [name] if name in all_regions else []
    return [r for r in all_regions if key in norm(r)]


def service_names(data, mapping_codes):
    """code -> (человекочитаемое имя, группа) с учетом сайта и mapping."""
    names = {}
    for items in data.values():
        for item in items:
            code = item["nomenclature_code"]
            if code not in names:
                entry = mapping_codes.get(code, {})
                names[code] = (entry.get("name") or item.get("name") or code,
                               entry.get("group") or "Прочее")
    return names


def print_city_prices(files, regions_selected, service_filter, mapping_codes):
    for path in files:
        data = json.load(open(path, encoding="utf-8"))
        tab = os.path.basename(path).replace("_optimized_scraped_data.json", "")
        names = service_names(data, mapping_codes)
        for region in regions_selected:
            if region not in data:
                continue
            rows = []
            for item in data[region]:
                code = item["nomenclature_code"]
                name, group = names.get(code, (code, "Прочее"))
                if service_filter and service_filter not in norm(name) and service_filter not in norm(code):
                    continue
                rows.append((group, name, code, item["price"]))
            if not rows:
                continue  # вкладка без совпадений — не печатаем
            print(f"\n### {region} — вкладка «{tab}»")
            for group, name, code, price in sorted(rows):
                print(f"  {group:<28} {name:<46} {code:<22} {price}")


def print_service_prices(files, service_filter, mapping_codes):
    """Цены услуги по всем регионам: единая цена или ценовые уровни."""
    for path in files:
        data = json.load(open(path, encoding="utf-8"))
        tab = os.path.basename(path).replace("_optimized_scraped_data.json", "")
        names = service_names(data, mapping_codes)
        for code, (name, group) in sorted(names.items()):
            if service_filter not in norm(name) and service_filter not in norm(code):
                continue
            prices = Counter()
            where = {}
            for region, items in data.items():
                for item in items:
                    if item["nomenclature_code"] == code:
                        prices[item["price"]] += 1
                        where.setdefault(item["price"], []).append(region)
            if not prices:
                continue
            print(f"\n### «{name}» ({code}) — вкладка «{tab}», группа «{group}»")
            if len(prices) == 1:
                price = next(iter(prices))
                print(f"  Единая цена по всем {prices[price]} регионам: {price}")
            else:
                print(f"  Зависит от региона — {len(prices)} уровней:")
                for price, count in sorted(prices.items(), key=lambda kv: int(kv[0].replace(" ", ""))):
                    regions = where[price]
                    tail = f" ({', '.join(regions[:3])}{'...' if len(regions) > 3 else ''})" if count <= 45 else ""
                    print(f"    {price:>8} x{count} рег.{tail}")


def main():
    args = parse_args()
    if not args.city and not args.service:
        print("Укажите --city и/или --service (см. --help).")
        sys.exit(1)

    files = find_data_files(args.tab)
    if not files:
        print("Данные не найдены: нет файлов *_optimized_scraped_data.json"
              + (f" для вкладки {args.tab}" if args.tab else "") + ".")
        sys.exit(1)

    mapping = {}
    if os.path.exists("nomenclature_map.json"):
        mapping = json.load(open("nomenclature_map.json", encoding="utf-8"))
    mapping_codes = mapping.get("codes", {})

    service_filter = norm(args.service) if args.service else None

    if args.city:
        all_regions = set()
        for path in files:
            all_regions.update(json.load(open(path, encoding="utf-8")).keys())
        regions_selected = resolve_regions(all_regions, args.city)
        if not regions_selected:
            print(f"Регион по запросу «{args.city}» не найден. Примеры: "
                  f"Москва, СПб, Казань, Татарстан, Свердловская...")
            sys.exit(1)
        print(f"Регион(ы): {', '.join(regions_selected)}")
        print_city_prices(files, regions_selected, service_filter, mapping_codes)
    else:
        print_service_prices(files, service_filter, mapping_codes)


if __name__ == "__main__":
    main()
