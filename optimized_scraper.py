import asyncio
import json
import random
from playwright.async_api import async_playwright

# Загружаем справочник регионов из файла
try:
    with open("regions.json", "r", encoding="utf-8") as f:
        regions = json.load(f)
except FileNotFoundError:
    print("regions.json файл не найден. Создайте файл с регионами.")
    regions = []
except json.JSONDecodeError:
    print("regions.json содержит некорректный JSON. Проверьте формат файла.")
    regions = []

async def parse_nomenclature_prices(playwright):
    browser = await playwright.chromium.launch(headless=False)
    page = await browser.new_page()
    result = {}
    
    total_regions = len(regions)
    processed_regions = 0

    for i, region in enumerate(regions, 1):
        region_id = region["id"]
        region_name = region["name"]
        url = f"https://saby.ru/tariffs?region={region_id}&tab=added"
        print(f"Обработка региона {i}/{total_regions}: {region_name}")
        try:
            await page.goto(url)
            await page.wait_for_load_state('domcontentloaded')
            await page.wait_for_timeout(5000)  # Даем время для загрузки динамического контента

            # Используем подход из второго скрипта для извлечения номенклатур с ценами
            nomenclature_data = []
            try:
                # Ожидание загрузки элементов с классом billing-PriceList__priceButton
                await page.wait_for_selector("span.billing-PriceList__priceButton", timeout=5000)
                price_elements = await page.query_selector_all("span.billing-PriceList__priceButton")
                
                print(f"Найдено элементов с номенклатурой в регионе {region_name}: {len(price_elements)}")
                
                seen_codes = set()  # Для отслеживания уникальных кодов
                for element in price_elements:
                    # Извлечение значения атрибута nomenclaturecode
                    nomenclature_code = await element.get_attribute("nomenclaturecode")
                    
                    # Если атрибут отсутствует, переходим к следующему элементу
                    if not nomenclature_code:
                        continue
                    
                    # Проверяем, не встречался ли уже такой код
                    if nomenclature_code in seen_codes:
                        continue
                    seen_codes.add(nomenclature_code)
                    
                    # Извлечение текста внутри тега span (цена)
                    price_text = await element.text_content()
                    price_text = price_text.strip()

                    # Добавляем данные в список
                    nomenclature_data.append({
                        "nomenclature_code": nomenclature_code,
                        "price": price_text
                    })
            except Exception as e:
                print(f"Ошибка при извлечении номенклатуры в регионе {region_name}: {str(e)}")

            # Сохраняем только nomenclature_data для региона
            result[region_name] = nomenclature_data
            
        except Exception as e:
            print(f"Ошибка при обработке региона {region_name}: {str(e)}")
            result[region_name] = []

        processed_regions += 1
        print(f"Обработано регионов: {processed_regions}/{total_regions} ({processed_regions/total_regions*100:.1f}%)")
        print(f" - Номенклатура: {len(nomenclature_data)} записей")

        # Добавляем случайную задержку между запросами к разным регионам (1-3 секунды)
        # чтобы быть более вежливыми к серверу и избежать блокировки
        if region != regions[-1]:  # Не добавляем задержку после последнего региона
            print(f"Задержка перед следующим регионом...")
            await asyncio.sleep(random.uniform(1, 3))

    await browser.close()
    return result

async def main():
    async with async_playwright() as playwright:
        data = await parse_nomenclature_prices(playwright)
        # Выводим данные в консоль
        print(json.dumps(data, ensure_ascii=False, indent=2, separators=(',', ': ')))
        # Сохраняем данные в файл
        with open("optimized_scraped_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(main())