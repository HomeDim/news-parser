from core.config import ConfigLoader
from core.lenta_parser import LentaParser
# from core.ria_parser import RiaParser # Закомментировано в твоем коде
from typing import Tuple
import logging
from pathlib import Path

def run_parser(parser) -> Tuple[bool, Path]:
    """Запускает парсер и обрабатывает базовые ошибки."""
    try:
        output_path = parser.run()
        return True, output_path
    except Exception as e:
        # Используем логгер с именем парсера для сообщений об ошибках
        logging.getLogger(parser.source_name).error(f"Ошибка в парсере {parser.source_name}: {str(e)}")
        return False, None

def main():
    # --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
    # Создаем директорию 'logs', если ее нет
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True) 
    log_file_path = log_dir / "parser.log" # Имя файла логов

    logging.basicConfig(
        level=logging.INFO, # Уровень INFO и выше будет записываться
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=log_file_path, # <--- Добавлено: путь к файлу логов
        filemode='a'            # <--- Добавлено: режим дозаписи (append)
    )
    # --- КОНЕЦ НАСТРОЙКИ ЛОГИРОВАНИЯ ---

    # Получаем логгер для main функции, чтобы логировать через него
    main_logger = logging.getLogger(__name__)

    main_logger.info("Запуск программы парсинга новостей.")

    config_loader = None # Инициализируем config_loader вне try, чтобы он был виден в finally
    try:
        # Инициализация загрузчика конфигурации
        config_loader = ConfigLoader()
        main_logger.info("Конфигурация успешно загружена.")
    except Exception as e:
        main_logger.critical(f"Критическая ошибка при загрузке конфигурации: {e}", exc_info=True) # exc_info=True для полного стектрейса
        main_logger.info("Программа завершена из-за ошибки конфигурации.")
        return # Выход из программы, если конфиг не загружен

    # Инициализация парсеров
    parsers = [
        LentaParser(config_loader),
        # RiaParser(config_loader) # Раскомментировать, когда будет готов
    ]

    # Запуск всех парсеров
    results = {}
    for parser in parsers:
        main_logger.info(f"Начинаем обработку парсера: {parser.source_name}")
        success, output_path = run_parser(parser)
        results[parser.source_name] = {
            'success': success,
            'output_path': output_path
        }
        status = "УСПЕШНО" if success else "ОШИБКА"
        # Используем логгер вместо print()
        main_logger.info(f"[{status}] {parser.source_name}: {output_path if output_path else 'N/A'}")

    # Сводный отчёт
    main_logger.info("\n=== Результаты ===")
    for source, data in results.items():
        # Используем логгер вместо print()
        main_logger.info(f"{source}: {'Успешно' if data['success'] else 'Ошибка'} -> {data['output_path'] if data['output_path'] else 'N/A'}")
    
    main_logger.info("Программа парсинга новостей завершена.")

if __name__ == "__main__":
    main()