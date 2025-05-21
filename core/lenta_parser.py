from .base_parser import BaseParser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import pytz
import logging
from typing import List, Dict, Optional
from pathlib import Path
import re
from urllib.parse import urlparse

class LentaParser(BaseParser):
    """Парсер новостей для Lenta.ru.
    
    Наследует базовую функциональность от BaseParser и реализует:
    - Специфичный для Lenta.ru парсинг RSS
    - Извлечение полного текста новостей
    - Обработку URL и идентификаторов
    """

    source_name = "lenta.ru"  # Определяем как атрибут класса

    def __init__(self, config_loader):
        """Инициализация парсера.
        
        Args:
            config_loader: Объект для загрузки конфигурации
        """
        super().__init__(config_loader)  # Всё инициализируется в базовом классе

    def _extract_news_id(self, url: str) -> str:
        """Извлечение ID новости для Lenta.ru.
        
        Lenta.ru использует URL вида:
        https://lenta.ru/news/2024/05/15/coffee/
        Извлекаем последнюю часть пути ('coffee')
        
        Args:
            url: Ссылка на новость
            
        Returns:
            Уникальный идентификатор новости
        """
        try:
            path = urlparse(url).path
            # Извлекаем последний сегмент пути
            return path.split('/')[-2] if path.endswith('/') else path.split('/')[-1]
        except Exception as e:
            self.logger.warning(f"Ошибка извлечения ID: {str(e)}")
            return url

    def _parse_rss_item(self, item, channel_name: str) -> Optional[Dict]:
        """Парсинг элемента RSS-ленты Lenta.ru."""
        news_data = self._get_news_template()  # Используем базовый шаблон
        
        try:
            # Обработка даты с конвертацией в часовой пояс парсера
            pub_date = datetime.strptime(
                item.pubDate.text, 
                "%a, %d %b %Y %H:%M:%S %z"
            ).astimezone(self.timezone)

            url = item.link.text.strip()
            
            # Заполнение данных новости
            news_data.update({
                'source': self.source_name,
                'id': self._extract_news_id(url),
                'title': item.title.text.strip(),
                'url': url,
                'pub_date': pub_date.isoformat(),
                'categories': [self.source_config['rss_channels'][channel_name]['category']]
            })
            
            return news_data
        except Exception as e:
            self.logger.error(f"Ошибка парсинга элемента: {str(e)}")
            return None

    def _extract_full_text(self, url: str) -> str:
        """Извлечение полного текста новости Lenta.ru."""
        if not self._is_news_url(url):
            return ""

        try:
            response = requests.get(
                url,
                headers={"User-Agent": self.source_config['defaults']['user_agent']},
                timeout=self.source_config['system']['request_timeout']
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            content = soup.find('div', class_='topic-body__content')
            
            if content:
                return ' '.join(p.text.strip() for p in content.find_all('p'))
            return ""
        except Exception as e:
            self.logger.error(f"Ошибка загрузки текста: {url} - {str(e)}")
            return ""

    def _is_news_url(self, url: str) -> bool:
        """Проверка, что URL ведет на новостную статью."""
        return "lenta.ru/news" in url and not any(x in url for x in ['/video/', '/photo/'])

    def fetch_news(self) -> List[Dict]:
        """Основной метод сбора новостей для Lenta.ru."""
        try:
            time_threshold = datetime.now(self.timezone) - timedelta(
                hours=self.source_config['system']['lookback_hours']
            )
            
            news_items = []
            for channel_name, channel_cfg in self.source_config['rss_channels'].items():
                try:
                    response = requests.get(
                        channel_cfg['url'],
                        headers={"User-Agent": self.source_config['defaults']['user_agent']},
                        timeout=self.source_config['system']['request_timeout']
                    )
                    response.raise_for_status()
                    
                    soup = BeautifulSoup(response.text, 'xml')
                    for item in soup.find_all('item')[:channel_cfg.get('max_news', self.source_config['defaults']['max_news'])]:
                        if news_item := self._parse_rss_item(item, channel_name):
                            if datetime.fromisoformat(news_item['pub_date']) >= time_threshold:
                                news_item['raw_content'] = self._extract_full_text(news_item['url'])
                                news_items.append(news_item)
                except Exception as e:
                    self.logger.error(f"Ошибка обработки канала {channel_name}: {str(e)}")
            
            return news_items
        except Exception as e:
            self.logger.critical(f"Ошибка получения новостей: {str(e)}")
            return []

    def run(self) -> Path:
        """Запуск парсера с дополнительным логированием."""
        self.logger.info(f"Запуск парсера Lenta.ru")
        news = self.fetch_news()
        
        if not news:
            self.logger.warning("Не удалось получить новости")
            raise RuntimeError("Новости не получены")
        
        output_path = self._save_raw_data(news)
        self.logger.info(f"Сохранено {len(news)} новостей")
        return output_path