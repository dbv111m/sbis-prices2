# Скрапер цен с сайта saby.ru

Этот проект представляет собой набор скриптов для сбора (скрапинга) данных о ценах на номенклатуру с сайта `saby.ru` по различным регионам и последующего создания отчетов на основе этих данных.

## 🚀 Установка и настройка (Windows)

### 1. Клонирование репозитория

Сначала склонируйте репозиторий из GitHub на ваш локальный компьютер. Откройте командную строку (cmd) или PowerShell и выполните команду:

```bash
git clone https://github.com/ваш-логин/ваш-репозиторий.git
cd ваш-репозиторий
```
*Замените `https://github.com/ваш-логин/ваш-репозиторий.git` на реальный URL вашего репозитория.*

### 2. Создание и активация виртуального окружения

Рекомендуется использовать виртуальное окружение для изоляции зависимостей проекта.

```bash
# Создание виртуального окружения в папке .venv
python -m venv .venv

# Активация окружения
.venv\Scripts\activate
```

После активации вы увидите `(.venv)` в начале вашей командной строки.

### 3. Установка зависимостей

Установите все необходимые библиотеки, перечисленные в `requirements.txt`.

```bash
pip install -r requirements.txt
```

Также необходимо установить браузеры для Playwright:

```bash
playwright install
```

## ⚙️ Использование

### 1. Запуск парсинга

Для сбора данных о ценах запустите скрипт `optimized_scraper.py`.

```bash
# Вкладка data_exchange (по умолчанию), все регионы, headless-режим
python optimized_scraper.py

# Вкладка edo (также доступны: ereport, added, data_exchange)
python optimized_scraper.py --tab edo

# Показать окно браузера (для отладки)
python optimized_scraper.py --tab edo --visible
```

Основные параметры:

| Параметр | Описание | По умолчанию |
|---|---|---|
| `--tab` | Вкладка тарифов: `edo`, `ereport`, `added`, `data_exchange` | `data_exchange` |
| `--output` | Имя выходного JSON-файла | `{tab}_optimized_scraped_data.json` |
| `--limit N` | Обработать только первые N регионов (для тестирования) | все регионы |
| `--regions 77,78,54` | Обработать только регионы с указанными кодами | все регионы |
| `--max-retries N` | Число попыток на регион при ошибке | `2` |
| `--visible` | Показывать окно браузера | headless |
| `--regions-file` | Путь к файлу регионов | `regions.json` |

Скрипт последовательно обойдет все регионы из `regions.json`, при сбоях повторит попытку и сохранит данные в JSON-файл.

### 2. Создание отчетов

После завершения скрапинга запустите `generate_reports.py`:

```bash
# Из файла по умолчанию -> nomenclature_prices_report.csv/.xlsx
python generate_reports.py

# Из данных вкладки edo -> edo_nomenclature_prices_report.csv/.xlsx
python generate_reports.py --input edo_optimized_scraped_data.json

# С явным префиксом имени отчета
python generate_reports.py --input data.json --prefix my_report
```

Префикс имен отчетов определяется автоматически из имени входного файла:
`edo_optimized_scraped_data.json` → `edo_nomenclature_prices_report.csv` / `.xlsx`.

Полученная таблица: строки — номенклатуры, столбцы — регионы.

## 📁 Структура проекта

- `optimized_scraper.py`: Основной скрипт для сбора данных с сайта.
- `generate_reports.py`: Скрипт для создания отчетов из собранных данных.
- `regions.json`: Файл с перечнем регионов для парсинга.
- `requirements.txt`: Список зависимостей Python с зафиксированными версиями.
- `{tab}_optimized_scraped_data.json`: Собранные данные по вкладке тарифов (например, `edo_...`, `ereport_...`).
- `{tab}_nomenclature_prices_report.csv` / `.xlsx`: Готовые отчеты по вкладке тарифов.
- `.gitignore`: Файл для исключения определенных файлов и папок из контроля версий Git (данные и отчеты публиковались намеренно).
