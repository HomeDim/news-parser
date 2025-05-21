import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse
import pytz
import logging
from pathlib import Path
import json

class BaseParser:
    """Базовый класс для всех новостных парсеров.
    
    Содержит общую функциональность:
    - Извлечение ID из URL
    - Шаблон структуры новости
    - Сохранение данных в файл
    - Логирование
    """
    
    def __init__(self, config_loader):
        """Инициализация парсера.
        
        Args:
            config_loader: Объект для загрузки конфигурации
        """
        self.config = config_loader
        self.logger = logging.getLogger(__name__)
        
        if not hasattr(self, 'source_name'):
            raise NotImplementedError("source_name должен быть указан в дочернем классе")
            
        # Загружаем конфигурацию
        self.source_config = self.config.get_source_config(self.source_name)
        
        # Устанавливаем основные атрибуты
        self.timezone = pytz.timezone(self.source_config['system']['parser_timezone'])
        self.request_timeout = self.source_config['system']['request_timeout']
        self.user_agent = self.source_config['defaults']['user_agent']
        
        self.logger.info(f"Инициализирован парсер для {self.source_name}")

    def _setup(self):
        """Загрузка конфигурации источника."""
        if not self.source_name:
            raise NotImplementedError("source_name должен быть указан в дочернем классе")
        self.source_config = self.config.get_source_config(self.source_name)
        self.timezone = pytz.timezone(self.source_config['system']['parser_timezone'])

    def _extract_news_id(self, url: str) -> str:
        """Базовая реализация извлечения ID новости из URL.
        
        По умолчанию ищет числовые сегменты в пути URL.
        Пример: 
        - https://example.com/news/123/ → "123"
        - https://example.com/news/abc/ → оригинальный URL
        
        Args:
            url: Ссылка на новость
            
        Returns:
            Извлеченный ID или оригинальный URL
        """
        try:
            path = urlparse(url).path
            numeric_parts = [p for p in path.split('/') if p.isdigit()]
            return numeric_parts[-1] if numeric_parts else url
        except Exception as e:
            self.logger.warning(f"Ошибка извлечения ID: {str(e)}")
            return url

    def _get_news_template(self) -> Dict:
        """Возвращает шаблон структуры новости.
        
        Все дочерние классы должны использовать этот шаблон 
        для обеспечения единого формата выходных данных.
        """
        return {
            'source': '',        # Идентификатор источника
            'id': '',            # Уникальный ID новости
            'title': '',         # Заголовок
            'url': '',           # Полная ссылка
            'pub_date': '',      # Дата публикации (ISO format)
            'categories': [],    # Список категорий
            'raw_content': ''    # Полный текст
        }

    def _save_raw_data(self, data: List[Dict]) -> Path:
        """Сохранение данных в JSON-файл.
        
        Args:
            data: Список новостей для сохранения
            
        Returns:
            Путь к сохраненному файлу
        """
        try:
            output_dir = Path(self.source_config['system']['raw_data_dir'])
            output_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{self.source_config['raw_prefix']}_{datetime.now(self.timezone).strftime('%Y%m%d_%H%M')}.json"
            output_path = output_dir / filename
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            self.logger.info(f"Сохранено {len(data)} новостей в {output_path}")
            return output_path
        except Exception as e:
            self.logger.critical(f"Ошибка сохранения: {str(e)}")
            raise

    def fetch_news(self) -> List[Dict]:
        """Основной метод получения новостей (должен быть переопределен)."""
        raise NotImplementedError("Метод fetch_news() должен быть реализован в дочернем классе")

    def run(self) -> Path:
        """Запуск парсера (может быть переопределен при необходимости)."""
        news = self.fetch_news()
        return self._save_raw_data(news)