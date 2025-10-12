import json
import random
import time
from playwright.sync_api import sync_playwright

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

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
]

def parse_nomenclature_prices(playwright):
    # Пример настройки прокси (требуется реальный адрес прокси)
    # proxy_server = "http://your_proxy_server:port"
    # browser = playwright.chromium.launch(
    #     headless=False,
    #     proxy={"server": proxy_server}
    # )
    browser = playwright.chromium.launch(headless=False)
    
    # Выбираем случайный User-Agent
    user_agent = random.choice(USER_AGENTS)
    
    # Устанавливаем случайный размер окна
    viewport = {
        "width": random.randint(1280, 1920),
        "height": random.randint(720, 1080),
    }

    page = browser.new_page(
        user_agent=user_agent,
        viewport=viewport,
        extra_http_headers={
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        }
    )
    result = {}
    
    total_regions = len(regions)
    processed_regions = 0

    for i, region in enumerate(regions, 1):
        region_id = region["id"]
        region_name = region["name"]
        url = f"https://saby.ru/tariffs?region={region_id}&tab=added"
        print(f"Обработка региона {i}/{total_regions}: {region_name}")
        try:
            page.goto(url)
            page.wait_for_load_state('domcontentloaded')
            page.wait_for_timeout(random.randint(3000, 7000))  # Даем время для загрузки динамического контента

            # Используем подход из второго скрипта для извлечения номенклатур с ценами
            nomenclature_data = []
            try:
                # Ожидание загрузки элементов с классом billing-PriceList__priceButton
                page.wait_for_selector("span.billing-PriceList__priceButton", timeout=5000)
                price_elements = page.query_selector_all("span.billing-PriceList__priceButton")
                
                print(f"Найдено элементов с номенклатурой в регионе {region_name}: {len(price_elements)}")
                
                seen_codes = set()  # Для отслеживания уникальных кодов
                for element in price_elements:
                    # Извлечение значения атрибута nomenclaturecode
                    nomenclature_code = element.get_attribute("nomenclaturecode")
                    
                    # Если атрибут отсутствует, переходим к следующему элементу
                    if not nomenclature_code:
                        continue
                    
                    # Проверяем, не встречался ли уже такой код
                    if nomenclature_code in seen_codes:
                        continue
                    seen_codes.add(nomenclature_code)
                    
                    # Извлечение текста внутри тега span (цена)
                    price_text = element.text_content()
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
            time.sleep(random.uniform(1, 3))

    browser.close()
    return result

def main():
    with sync_playwright() as playwright:
        data = parse_nomenclature_prices(playwright)
        # Выводим данные в консоль
        print(json.dumps(data, ensure_ascii=False, indent=2, separators=(',', ': ')))
        # Сохраняем данные в файл
        with open("optimized_scraped_data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
