from .base_parser import BaseParser
import feedparser
import requests
from datetime import datetime, timedelta
import pytz
import logging
from typing import List, Dict, Optional
from pathlib import Path
import re
import time
from bs4 import BeautifulSoup
from ratelimit import limits, sleep_and_retry

class RiaParser(BaseParser):
    """Парсер новостей RIA.ru с полной поддержкой всех форматов URL"""
    
    source_name = "ria.ru"
    API_BASE_URL = "https://ria.ru/api/"
    REQUEST_LIMIT = 5  # Лимит запросов в секунду

    def __init__(self, config_loader):
        super().__init__(config_loader)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.source_config['defaults']['user_agent'],
            'Accept': 'application/json',
            'Referer': 'https://ria.ru/'
        })

    @sleep_and_retry
    @limits(calls=5, period=1)
    def _make_api_request(self, url: str) -> Optional[Dict]:
        """Безопасный запрос к API с ограничением скорости"""
        try:
            response = self.session.get(
                url,
                timeout=self.source_config['system']['request_timeout']
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"API request failed: {url} - {str(e)}")
            return None
        except ValueError as e:
            self.logger.error(f"JSON decode error: {url} - {str(e)}")
            return None

    def _extract_news_id(self, url: str) -> Optional[str]:
        """Универсальное извлечение ID для всех форматов RIA"""
        try:
            # Нормализация URL
            clean_url = url.split('?')[0].split('#')[0].rstrip('/')
            
            # Все возможные форматы URL RIA
            patterns = [
                r'-(\d+)\.html$',      # Стандартный формат
                r'-(\d+)/?$',           # Без .html
                r'/(\d+)\.html$',       # Альтернативный формат
                r'/(\d+)/?$',           # URL без префикса
                r'/(\d+)$',             # Короткий URL
                r'_(\d+)\.html$',       # Для некоторых спецпроектов
                r'(\d{8,})'             # Резервный вариант
            ]
            
            for pattern in patterns:
                match = re.search(pattern, clean_url)
                if match:
                    return match.group(1)
            
            self.logger.warning(f"Неизвестный формат URL: {url}")
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения ID: {str(e)} URL: {url}")
            return None

    def _extract_full_text(self, url: str) -> str:
        """Комбинированный метод получения текста (API + fallback)"""
        # Пропускаем не-статьи
        if any(x in url for x in ["/video/", "/gallery/", "/infographics/"]):
            return ""
            
        # Пытаемся через API
        article_id = self._extract_news_id(url)
        if article_id:
            api_url = f"{self.API_BASE_URL}{article_id}.json"
            data = self._make_api_request(api_url)
            
            if data and data.get('text'):
                return data['text']
        
        # Fallback через HTML-парсинг
        return self._extract_full_text_fallback(url)

    def _extract_full_text_fallback(self, url: str) -> str:
        """Резервный метод парсинга текста из HTML"""
        try:
            response = self.session.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Основной текст статьи
            body = soup.find('div', class_='article__body') or \
                   soup.find('div', class_='article__text')
            
            if not body:
                return ""
                
            # Удаляем ненужные элементы
            for elem in body(['script', 'style', 'iframe', 'div.article__info']):
                elem.decompose()
                
            return ' '.join(p.text.strip() for p in body.find_all('p') if p.text.strip())
            
        except Exception as e:
            self.logger.error(f"Fallback parsing failed: {url} - {str(e)}")
            return ""

    def _parse_rss_item(self, entry, channel_name: str) -> Optional[Dict]:
        """Парсинг элемента RSS с улучшенной обработкой ошибок"""
        try:
            # Проверка обязательных полей
            if not all([hasattr(entry, 'link'), hasattr(entry, 'title')]):
                self.logger.warning(f"Invalid RSS entry: {entry}")
                return None
                
            # Обработка даты
            pub_date = datetime.fromtimestamp(
                time.mktime(entry.published_parsed)
            ).astimezone(self.timezone)
            
            # Подготовка данных
            news_data = self._get_news_template()
            news_data.update({
                'source': self.source_name,
                'id': self._extract_news_id(entry.link) or entry.link,
                'title': entry.title,
                'url': entry.link,
                'pub_date': pub_date.isoformat(),
                'categories': [self.source_config['rss_channels'][channel_name]['category']],
                'description': getattr(entry, 'description', ''),
                'raw_content': ""  # Будет заполнено позже
            })
            
            # Получаем полный текст только для новых статей
            time_threshold = datetime.now(self.timezone) - timedelta(
                hours=self.source_config['system']['lookback_hours']
            )
            
            if pub_date >= time_threshold:
                news_data['raw_content'] = self._extract_full_text(entry.link)
            
            return news_data
            
        except Exception as e:
            self.logger.error(f"RSS parsing error: {str(e)}\nEntry: {entry}")
            return None

    def fetch_news(self) -> List[Dict]:
        """Основной метод сбора новостей с улучшенной обработкой ошибок"""
        news_items = []
        
        for channel_name, channel_cfg in self.source_config['rss_channels'].items():
            try:
                self.logger.info(f"Processing channel: {channel_name}")
                
                # Парсинг RSS
                feed = feedparser.parse(channel_cfg['url'])
                if feed.bozo:
                    self.logger.error(f"RSS parse error: {feed.bozo_exception}")
                    continue
                    
                # Обработка новостей
                for entry in feed.entries[:channel_cfg.get('max_news', self.source_config['defaults']['max_news'])]:
                    if news_item := self._parse_rss_item(entry, channel_name):
                        news_items.append(news_item)
                        
                self.logger.info(f"Processed {len(news_items)} news from {channel_name}")
                
            except Exception as e:
                self.logger.error(f"Channel processing error: {channel_name} - {str(e)}")
                continue
                
        return news_items

    def run(self) -> Path:
        """Запуск парсера с расширенным логированием"""
        self.logger.info(f"Starting RIA parser at {datetime.now(self.timezone)}")
        result = super().run()
        self.logger.info(f"Parser finished. Results saved to {result}")
        return result