import json
import pandas as pd
import os

def generate_reports():
    # Загружаем данные из JSON файла
    try:
        with open('optimized_scraped_data.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Файл optimized_scraped_data.json не найден. Сначала запустите скрипт скрапинга.")
        return

    # Извлекаем уникальные номенклатуры из всех регионов
    all_nomenclatures = set()
    for region_data in data.values():
        for item in region_data:
            all_nomenclatures.add(item["nomenclature_code"])
    
    all_nomenclatures = sorted(list(all_nomenclatures))
    
    # Создаем таблицу: строки - номенклатура, столбцы - регионы
    report_data = {}
    
    for nomenclature in all_nomenclatures:
        report_data[nomenclature] = {}
        for region_name, region_data in data.items():
            # Найти цену для данной номенклатуры в этом регионе
            price = "Нет данных"
            for item in region_data:
                if item["nomenclature_code"] == nomenclature:
                    price = item["price"]
                    break
            report_data[nomenclature][region_name] = price
    
    # Создаем DataFrame
    df = pd.DataFrame(report_data).T  # Транспонируем, чтобы номенклатура была по строкам
    
    # Сохраняем в CSV
    csv_filename = 'nomenclature_prices_report.csv'
    df.to_csv(csv_filename, encoding='utf-8-sig', index_label='Номенклатура')
    print(f"CSV отчет сохранен: {csv_filename}")
    
    # Сохраняем в Excel
    excel_filename = 'nomenclature_prices_report.xlsx'
    df.to_excel(excel_filename, index_label='Номенклатура')
    print(f"Excel отчет сохранен: {excel_filename}")
    
    # Также создаем отчет с тарифами (если нужно)
    print("\nСтатистика:")
    print(f"Всего уникальных номенклатур: {len(all_nomenclatures)}")
    print(f"Всего регионов: {len(data)}")
    print(f"Размер таблицы: {len(all_nomenclatures)} x {len(data)}")

if __name__ == "__main__":
    # Убедимся, что pandas установлен
    try:
        import pandas as pd
    except ImportError:
        print("Установите pandas: pip install pandas openpyxl")
        exit(1)
    
    generate_reports()