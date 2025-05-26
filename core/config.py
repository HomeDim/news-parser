import yaml
from pathlib import Path
import logging
from typing import Dict, Any

# Получаем логгер для модуля config
logger = logging.getLogger(__name__)

class ConfigLoader:
    """Загрузчик и валидатор конфигурации парсеров.
    
    Обрабатывает YAML-файл с настройками и обеспечивает:
    - Проверку обязательных секций
    - Доступ к параметрам с type hints
    - Защищенную загрузку конфига
    """

    def __init__(self, config_path: str = None):
        """Инициализация загрузчика.
        
        Args:
            config_path: Опциональный путь к конфигу. По умолчанию ищет settings.yaml в папке config
        """
        self._config = self._load_config(config_path)
        self._validate_config()
        # Этот логгер будет использовать настроенный basicConfig после его вызова в main.py
        logger.info("ConfigLoader успешно инициализирован.")

    def _load_config(self, custom_path: str = None) -> Dict[str, Any]:
        """Загрузка YAML-конфига с обработкой ошибок.
        
        Args:
            custom_path: Альтернативный путь к конфигу
            
        Returns:
            Словарь с конфигурацией
            
        Raises:
            FileNotFoundError: Если файл не существует
            yaml.YAMLError: При ошибках парсинга YAML
        """
        try:
            config_path = Path(custom_path) if custom_path else \
                         Path(__file__).parent.parent / "config" / "settings.yaml"
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            if not config:
                # Используем локальный логгер
                logger.error("Конфиг пустой или содержит недопустимые значения")
                raise ValueError("Конфиг пустой или содержит недопустимые значения")
                
            return config
            
        except FileNotFoundError:
            # Используем локальный логгер, добавляем exc_info=True для вывода стектрейса
            logger.critical(f"Конфиг не найден по пути: {config_path}", exc_info=True)
            raise
        except yaml.YAMLError as e:
            # Используем локальный логгер, добавляем exc_info=True
            logger.critical(f"Ошибка парсинга YAML: {str(e)}", exc_info=True)
            raise
        except Exception as e:
            # Используем локальный логгер, добавляем exc_info=True
            logger.critical(f"Неизвестная ошибка загрузки конфига: {str(e)}", exc_info=True)
            raise

    def _validate_config(self) -> None:
        """Проверка обязательных структур конфига.
        
        Raises:
            ValueError: При отсутствии обязательных секций/полей
        """
        required_common = ['system', 'defaults']
        for section in required_common:
            if section not in self._config.get('common', {}): # Добавлено .get({}, {}) для безопасности
                logger.error(f"Отсутствует обязательная секция 'common.{section}' в конфиге.")
                raise ValueError(f"Отсутствует обязательная секция 'common.{section}'")
        
        if not isinstance(self._config.get('sources'), dict):
            logger.error("Секция 'sources' должна быть словарем или отсутствовать.")
            raise ValueError("Секция 'sources' должна быть словарем")
        
        logger.info("Конфигурация успешно валидирована.")

    @property
    def system_settings(self) -> Dict[str, Any]:
        """Системные настройки (непереопределяемые)."""
        return self._config['common']['system']

    @property
    def default_settings(self) -> Dict[str, Any]:
        """Настройки по умолчанию для источников."""
        return self._config['common']['defaults']

    @property
    def sources(self) -> Dict[str, Any]:
        """Доступ ко всем источникам."""
        return self._config['sources']

    def get_source_config(self, source_name: str) -> Dict[str, Any]:
        """Получает полный конфиг источника с подставленными дефолтами.
        
        Args:
            source_name: Ключ источника (например 'ria.ru')
            
        Returns:
            Объединенный конфиг: system + defaults + source_specific
            
        Raises:
            KeyError: Если источник не найден
        """
        if source_name not in self.sources:
            logger.error(f"Источник {source_name} не найден в секции 'sources' конфига.")
            raise KeyError(f"Источник {source_name} не найден в конфиге")
            
        source_cfg = self.sources[source_name]
        return {
            'system': self.system_settings,
            'defaults': self.default_settings,
            'raw_prefix': source_cfg['raw_prefix'],
            'rss_channels': self._prepare_channels_config(source_cfg)
        }

    def _prepare_channels_config(self, source_cfg: Dict[str, Any]) -> Dict[str, Any]:
        """Объединяет настройки каналов с дефолтами."""
        channels = {}
        for name, channel in source_cfg['rss_channels'].items():
            channels[name] = {
                'url': channel['url'],
                'category': channel['category'],
                'max_news': channel.get('max_news', self.default_settings['max_news'])
            }
        return channels