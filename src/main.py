from news_parser.core.config import ConfigLoader  # Добавьте этот импорт
from news_parser.core.lenta_parser import LentaParser
from news_parser.core.ria_parser import RiaParser
from typing import Tuple
import logging
import sys
from pathlib import Path

def run_parser(parser) -> Tuple[bool, Path]:
    """Запускает парсер и обрабатывает базовые ошибки."""
    try:
        output_path = parser.run()
        return True, output_path
    except Exception as e:
        logging.error(f"Ошибка в парсере {parser.source_name}: {str(e)}")
        return False, None

def main():
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Инициализация загрузчика конфигурации
    config_loader = ConfigLoader()  # Создаём загрузчик конфигурации

    # Инициализация парсеров с передачей config_loader
    parsers = [
        LentaParser(config_loader),  # Передаём загрузчик
        RiaParser(config_loader)    # Передаём загрузчик
    ]

    # Запуск всех парсеров
    results = {}
    for parser in parsers:
        success, output_path = run_parser(parser)
        results[parser.source_name] = {
            'success': success,
            'output_path': output_path
        }
        status = "УСПЕШНО" if success else "ОШИБКА"
        print(f"[{status}] {parser.source_name}: {output_path}")

    # Сводный отчёт
    print("\n=== Результаты ===")
    for source, data in results.items():
        print(f"{source}: {'Успешно' if data['success'] else 'Ошибка'} -> {data['output_path']}")

if __name__ == "__main__":
    main()