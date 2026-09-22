"""Скрапер цен с сайта saby.ru.

Обходит регионы из regions.json, собирает цены на номенклатуру
с выбранной вкладки тарифов и сохраняет результат в JSON.

Примеры запуска:
    python optimized_scraper.py                          # data_exchange по всем регионам
    python optimized_scraper.py --tab edo                # вкладка edo
    python optimized_scraper.py --tab ereport --limit 2  # только 2 региона (тест)
    python optimized_scraper.py --tab edo --visible      # показать окно браузера
"""

import argparse
import json
import random
import sys
import time

from playwright.sync_api import sync_playwright

# Доступные вкладки на странице тарифов
TABS = ("edo", "ereport", "added", "data_exchange")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
]

PRICE_SELECTOR = "span.billing-PriceList__priceButton"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Скрапинг цен на номенклатуру с сайта saby.ru по регионам"
    )
    parser.add_argument(
        "--tab",
        choices=TABS,
        default="data_exchange",
        help=f"Вкладка тарифов (по умолчанию: data_exchange). Доступно: {', '.join(TABS)}",
    )
    parser.add_argument(
        "--regions-file",
        default="regions.json",
        help="Путь к файлу с перечнем регионов (по умолчанию: regions.json)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Имя выходного JSON-файла (по умолчанию: {tab}_optimized_scraped_data.json)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Обработать только первые N регионов (для тестирования)",
    )
    parser.add_argument(
        "--regions",
        default=None,
        help="Обработать только регионы с указанными кодами через запятую (например: 77,78,54,66,16)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Число попыток на регион при ошибке или пустом результате (по умолчанию: 2)",
    )
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Показывать окно браузера (по умолчанию headless-режим)",
    )
    return parser.parse_args()


def load_regions(path):
    """Загружает справочник регионов из файла."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Файл {path} не найден. Создайте файл с регионами.")
        return []
    except json.JSONDecodeError:
        print(f"Файл {path} содержит некорректный JSON. Проверьте формат файла.")
        return []


def scrape_region(page, url):
    """Собирает номенклатуры с ценами для одного региона.

    Возвращает список записей {"nomenclature_code": ..., "price": ...}.
    Бросает исключение, если страница не загрузилась или данных нет.
    """
    page.goto(url, wait_until="domcontentloaded")
    # Ждем появления реальных элементов вместо фиксированной длинной паузы
    page.wait_for_selector(PRICE_SELECTOR, timeout=15000)
    # Небольшая пауза, чтобы динамический контент (цены) успел догрузиться
    page.wait_for_timeout(random.randint(1000, 3000))

    nomenclature_data = []
    seen_codes = set()
    for element in page.query_selector_all(PRICE_SELECTOR):
        nomenclature_code = element.get_attribute("nomenclaturecode")
        if not nomenclature_code or nomenclature_code in seen_codes:
            continue
        seen_codes.add(nomenclature_code)
        price_text = (element.text_content() or "").strip()
        nomenclature_data.append({
            "nomenclature_code": nomenclature_code,
            "price": price_text,
        })

    if not nomenclature_data:
        raise ValueError("не найдено ни одной номенклатуры с ценами")
    return nomenclature_data


def scrape_region_with_retries(page, url, region_name, max_retries):
    """Обрабатывает регион с повторными попытками при сбоях."""
    for attempt in range(1, max_retries + 1):
        try:
            return scrape_region(page, url)
        except Exception as e:
            print(f"  Попытка {attempt}/{max_retries} для \"{region_name}\" не удалась: {e}")
            if attempt < max_retries:
                delay = random.uniform(2, 5) * attempt
                print(f"  Повторная попытка через {delay:.1f} сек...")
                time.sleep(delay)
    return []


def parse_nomenclature_prices(playwright, regions, tab, headless, max_retries):
    """Обходит все регионы и возвращает словарь {регион: [записи]}."""
    browser = playwright.chromium.launch(headless=headless)

    try:
        # Выбираем случайный User-Agent и размер окна, чтобы снизить риск блокировки
        page = browser.new_page(
            user_agent=random.choice(USER_AGENTS),
            viewport={
                "width": random.randint(1280, 1920),
                "height": random.randint(720, 1080),
            },
            extra_http_headers={
                "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            },
        )

        result = {}
        total_regions = len(regions)

        for i, region in enumerate(regions, 1):
            region_id = region["id"]
            region_name = region["name"]
            url = f"https://saby.ru/tariffs?region={region_id}&tab={tab}"
            print(f"Обработка региона {i}/{total_regions}: {region_name}")

            nomenclature_data = scrape_region_with_retries(
                page, url, region_name, max_retries
            )
            result[region_name] = nomenclature_data

            print(f"  Номенклатура: {len(nomenclature_data)} записей")
            print(f"Обработано регионов: {i}/{total_regions} ({i / total_regions * 100:.1f}%)")

            # Случайная задержка между регионами, чтобы не нагружать сервер
            # (кроме последнего региона)
            if i < total_regions:
                print("Задержка перед следующим регионом...")
                time.sleep(random.uniform(1, 3))

        return result
    finally:
        browser.close()


def normalize_region_code(code):
    """Приводит код региона к виду без ведущих нулей ("02" -> "2")."""
    try:
        return str(int(code))
    except (TypeError, ValueError):
        return str(code).strip()


def filter_regions(regions, codes):
    """Оставляет только регионы с указанными кодами."""
    wanted = {normalize_region_code(c) for c in codes.split(",") if c.strip()}
    filtered = [r for r in regions if normalize_region_code(r["id"]) in wanted]
    found = {normalize_region_code(r["id"]) for r in filtered}
    missing = wanted - found
    if missing:
        print(f"Внимание: коды не найдены в справочнике регионов: {', '.join(sorted(missing))}")
    return filtered


def main():
    args = parse_args()

    regions = load_regions(args.regions_file)
    if not regions:
        sys.exit(1)
    if args.regions:
        regions = filter_regions(regions, args.regions)
        if not regions:
            print("Не выбран ни один регион.")
            sys.exit(1)
    if args.limit is not None:
        regions = regions[: max(0, args.limit)]

    output_file = args.output or f"{args.tab}_optimized_scraped_data.json"

    with sync_playwright() as playwright:
        data = parse_nomenclature_prices(
            playwright,
            regions=regions,
            tab=args.tab,
            headless=not args.visible,
            max_retries=args.max_retries,
        )

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Данные сохранены: {output_file}")


if __name__ == "__main__":
    main()
