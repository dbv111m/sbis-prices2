"""Быстрый HTTP-скрапер тарифов saby.ru — без браузера.

Цены на saby.ru отдаются в серверном HTML, поэтому вкладку региона можно
скачивать обычным HTTP-запросом: ~1 сек на регион вместо ~10 сек в браузере.
Полный прогон (90 регионов) занимает ~2-3 минуты на вкладку.

Формат вывода идентичен optimized_scraper.py (Playwright-версия) — скрипты
взаимозаменяемы. Отличие: HTTP-скрапер не извлекает названия услуг с сайта
(поле name пустое) — человекочитаемые названия берутся из nomenclature_map.json.

Если сайт начнет блокировать HTTP-запросы (страница диагностики, капча) —
используйте fallback: optimized_scraper.py (--visible для отладки).

Примеры:
    python http_scraper.py --tab edo                     # все 90 регионов
    python http_scraper.py --tab retail --limit 2         # тест: 2 региона
    python http_scraper.py --tab staff --regions 77,78,05
"""

import argparse
import gzip
import html as html_lib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request

# Все вкладки страницы тарифов: ключ URL (tab=...) -> название категории
TABS = {
    "added": "Базовые возможности",
    "ereport": "Отчетность и бухгалтерия",
    "edo": "Документооборот и EDI",
    "data_exchange": "Обмен с госсистемами",
    "contragents": "Все о компаниях и владельцах",
    "tenders": "Торги и закупки",
    "staff": "Управление персоналом",
    "ofd": "Онлайн-кассы и ОФД",
    "retail": "Для магазинов (розница)",
    "marketplace": "Для селлеров маркетплейсов",
    "presto": "Для ресторанов, кафе, столовых",
    "salons": "Для салонов и сферы услуг",
    "med": "Для медицины и клиник",
    "hotel": "Для отелей и хостелов",
    "inventory": "Торговля и производство",
    "mobile_workers": "Транспорт и логистика",
    "crm": "CRM и телефония",
    "video_monitoring": "Видеонаблюдение",
    "meet": "Мессенджер и звонки",
    "desk": "Сервис и администрирование",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

PRICE_BUTTON_RE = re.compile(
    r'<span[^>]*nomenclaturecode="([^"]+)"[^>]*>(.*?)</span>', re.DOTALL
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Быстрый HTTP-скрапинг тарифов saby.ru без браузера"
    )
    parser.add_argument(
        "--tab",
        choices=sorted(TABS),
        default=None,
        required=True,
        help="Вкладка тарифов (см. README — доступно 20 вкладок)",
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
        help="Обработать только регионы с указанными кодами через запятую (например: 77,78,54)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Число попыток на регион (по умолчанию: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Таймаут HTTP-запроса в секундах (по умолчанию: 30)",
    )
    return parser.parse_args()


def load_regions(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Файл {path} не найден. Создайте файл с регионами.")
        return []
    except json.JSONDecodeError:
        print(f"Файл {path} содержит некорректный JSON. Проверьте формат файла.")
        return []


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


def fetch_html(url, timeout):
    """Скачивает HTML страницы тарифов обычным HTTP-запросом."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Connection": "keep-alive",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
        if response.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return raw.decode("utf-8", errors="replace")


def parse_prices(page_html):
    """Извлекает из HTML пары (код номенклатуры, цена), без повторов кода."""
    items = []
    seen = set()
    for code, inner in PRICE_BUTTON_RE.findall(page_html):
        if code in seen:
            continue
        seen.add(code)
        price = html_lib.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        items.append({"nomenclature_code": code, "price": price, "name": ""})
    return items


def scrape_region_with_retries(url, region_name, max_retries, timeout):
    for attempt in range(1, max_retries + 1):
        try:
            page_html = fetch_html(url, timeout)
            items = parse_prices(page_html)
            if not items:
                raise ValueError(
                    "в HTML нет номенклатур (возможно, страница диагностики или блокировка)"
                )
            return items
        except Exception as e:
            print(f"  Попытка {attempt}/{max_retries} для \"{region_name}\" не удалась: {e}")
            if attempt < max_retries:
                delay = random.uniform(2, 5) * attempt
                print(f"  Повторная попытка через {delay:.1f} сек...")
                time.sleep(delay)
    return []


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
    print(f"Вкладка: {TABS[args.tab]} (tab={args.tab})")
    print(f"Регионов к обработке: {len(regions)} | Режим: HTTP без браузера")

    result = {}
    total = len(regions)
    for i, region in enumerate(regions, 1):
        region_id, region_name = region["id"], region["name"]
        url = f"https://saby.ru/tariffs?region={region_id}&tab={args.tab}"
        print(f"[{i}/{total}] {region_name}...", end=" ", flush=True)

        items = scrape_region_with_retries(url, region_name, args.max_retries, args.timeout)
        result[region_name] = items
        print(f"{len(items)} записей")

        # Короткая вежливая пауза между запросами
        if i < total:
            time.sleep(random.uniform(0.5, 1.5))

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"Данные сохранены: {output_file}")


if __name__ == "__main__":
    main()
