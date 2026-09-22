"""Анализ цен: единые/региональные услуги и кластеры регионов.

Определяет:
1. По каким услугам цены одинаковы во всех регионах, а по каким различаются
   (с уровнями цен и регионами на каждом уровне);
2. Кластеры регионов с идентичными ценами на все услуги вкладки — кандидаты
   для оптимизации скрапинга (один регион-представитель на кластер);
3. Сводные кластеры по всем вкладкам сразу (пересечение разбиений).

Примеры:
    python analyze_prices.py                          # все найденные вкладки
    python analyze_prices.py --input edo_optimized_scraped_data.json
    python analyze_prices.py --save-clusters region_clusters.json
"""

import argparse
import glob
import json
import os
import sys
from collections import Counter, defaultdict

NO_DATA = "Нет данных"


def parse_args():
    parser = argparse.ArgumentParser(description="Анализ единообразия цен и кластеров регионов")
    parser.add_argument(
        "--input",
        action="append",
        default=None,
        help="JSON-файл скрапинга (можно указать несколько раз). По умолчанию — все *_optimized_scraped_data.json",
    )
    parser.add_argument(
        "--save-clusters",
        default=None,
        help="Сохранить сводные кластеры в JSON-файл (для оптимизации скрапинга)",
    )
    return parser.parse_args()


def find_inputs():
    """Автопоиск файлов данных по стандартному шаблону."""
    files = sorted(glob.glob("*_optimized_scraped_data.json"))
    if os.path.exists("optimized_scraped_data.json"):
        files.append("optimized_scraped_data.json")
    return files


def load_data(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def region_vectors(data):
    """Вектор цен региона: кортеж (код, цена) по всем услугам."""
    vectors = {}
    for region, items in data.items():
        vectors[region] = tuple(sorted((item["nomenclature_code"], item["price"]) for item in items))
    return vectors


def cluster_regions(vectors):
    """Группирует регионы с идентичными векторами цен.

    Возвращает список кластеров, отсортированный по размеру (по убыванию):
    [{representative, regions, vector}, ...]
    """
    groups = defaultdict(list)
    for region, vector in vectors.items():
        groups[vector].append(region)
    clusters = [
        {"representative": sorted(regions)[0], "regions": sorted(regions), "vector": vector}
        for vector, regions in groups.items()
    ]
    clusters.sort(key=lambda c: -len(c["regions"]))
    return clusters


def print_services(data, label):
    """Сводка: услуги с едиными ценами против региональных."""
    service_prices = defaultdict(dict)
    for region, items in data.items():
        for item in items:
            service_prices[item["nomenclature_code"]][region] = item["price"]

    uniform, varying = 0, 0
    for code in sorted(service_prices):
        levels = Counter(service_prices[code].values())
        if len(levels) == 1:
            uniform += 1
        else:
            varying += 1
    print(f"\n### {label}: услуги")
    print(f"  Единые цены по всем регионам : {uniform}")
    print(f"  Зависят от региона           : {varying}")


def print_clusters(clusters, label):
    """Печать кластеров регионов."""
    total = sum(len(c["regions"]) for c in clusters)
    print(f"\n### {label}: кластеры регионов ({len(clusters)} шт. на {total} регионов)")
    for i, cluster in enumerate(clusters, 1):
        regions = cluster["regions"]
        head = ", ".join(regions[:6])
        tail = "..." if len(regions) > 6 else ""
        print(f"  [{i:>2}] {cluster['representative']:<28} {len(regions):>2} рег.: {head}{tail}")


def main():
    args = parse_args()
    inputs = args.input or find_inputs()
    if not inputs:
        print("Не найдено файлов данных. Запустите скрапинг или укажите --input.")
        sys.exit(1)

    combined_vectors = {}

    for path in inputs:
        label = os.path.basename(path).replace("_optimized_scraped_data.json", "")
        data = load_data(path)

        print_services(data, label)
        clusters = cluster_regions(region_vectors(data))
        print_clusters(clusters, label)

        # Накопление сводного вектора (все вкладки вместе) для пересечения кластеров
        for region, vector in region_vectors(data).items():
            combined_vectors[region] = combined_vectors.get(region, ()) + vector

    if len(inputs) > 1:
        combined = cluster_regions(combined_vectors)
        print_clusters(combined, "СВОДНО по всем вкладкам")
        n = len(combined)
        total = sum(len(c["regions"]) for c in combined)
        print(f"\n  => Скрапить можно {n} регионов вместо {total} "
              f"(ускорение ~{total / n:.1f}x) при неизменных ценовых зонах")

        if args.save_clusters:
            out = [
                {"cluster": i, "representative": c["representative"], "regions": c["regions"]}
                for i, c in enumerate(combined, 1)
            ]
            with open(args.save_clusters, "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print(f"  Сводные кластеры сохранены: {args.save_clusters}")
    elif args.save_clusters:
        clusters = cluster_regions(region_vectors(load_data(inputs[0])))
        out = [
            {"cluster": i, "representative": c["representative"], "regions": c["regions"]}
            for i, c in enumerate(clusters, 1)
        ]
        with open(args.save_clusters, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"Кластеры сохранены: {args.save_clusters}")


if __name__ == "__main__":
    main()
