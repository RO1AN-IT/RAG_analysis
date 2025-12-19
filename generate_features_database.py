"""
Скрипт для создания базы данных признаков с описаниями через GigaChat.

Генерирует CSV файл с индексом признака, названием и описанием.
"""

import pandas as pd
import logging
from typing import List, Dict, Optional
from gigachat import GigaChat
import os
import time

# Инициализация логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Учетные данные GigaChat (из opensearch_test.py)
GIGACHAT_CREDENTIALS = "MDE5YjA0YmYtMDNlMy03ZmVjLTgyN2EtNDI5OGFhYmM4YzlhOjVjMGJhYWRmLTQ4ZjktNGNkNC1iNjBkLTRhODVjYTY5Y2RmNQ=="


class FeatureDescriptionGenerator:
    """
    Класс для генерации описаний признаков через GigaChat.
    """
    
    def __init__(self, credentials: str):
        """
        Инициализация генератора описаний.
        
        Args:
            credentials: Учетные данные для GigaChat
        """
        self.credentials = credentials
        
        # Промпт для генерации описаний признаков
        self.description_prompt_template = """Ты - эксперт по геологии, нефтегазовой геологии и геофизике.

Твоя задача - создать краткое, но информативное описание геологического признака для базы данных.

Название признака: "{feature_name}"

Контекст: Этот признак используется в базе данных геологических слоев Каспийского моря, связанной с нефтегазовой геологией.

ТРЕБОВАНИЯ К ОПИСАНИЮ:
1. Описание должно быть кратким (2-4 предложения, максимум 150 слов)
2. Объясни, что означает этот признак в контексте геологии и нефтегазовой отрасли
3. Укажи единицы измерения, если они применимы (например, проценты, метры, градусы Цельсия, МПа)
4. Объясни, почему этот признак важен для анализа нефтегазоносности
5. Если признак имеет сокращенное название, расшифруй его
6. Используй профессиональную терминологию, но будь понятным

ПРИМЕРЫ ХОРОШИХ ОПИСАНИЙ:

Признак: "Rо,%"
Описание: "Отражательная способность витринита (Rо) - ключевой показатель зрелости органического вещества в нефтегазовой геологии. Измеряется в процентах и показывает степень преобразования органического материала под воздействием температуры и давления. Значения Rо > 1.0% указывают на зрелую нефть, Rо > 1.3% - на газ. Используется для оценки нефтегазоносности пород."

Признак: "Глубина,м"
Описание: "Глубина залегания геологического слоя или объекта в метрах от поверхности земли или уровня моря. Критически важный параметр для оценки условий формирования и сохранности углеводородов, а также для планирования бурения скважин."

Признак: "Сорг,%"
Описание: "Содержание органического углерода (Сорг) в породах, выраженное в процентах. Показывает количество органического вещества, способного генерировать углеводороды. Породы с Сорг > 0.5% считаются потенциально нефтематеринскими. Высокие значения Сорг (>2-3%) указывают на хорошие условия для генерации нефти и газа."

Верни ТОЛЬКО описание признака без дополнительных комментариев, заголовков или форматирования."""

    def generate_description(self, feature_name: str, retry_count: int = 3) -> Optional[str]:
        """
        Генерация описания признака через GigaChat.
        
        Args:
            feature_name: Название признака
            retry_count: Количество попыток при ошибке
            
        Returns:
            Описание признака или None при ошибке
        """
        prompt = self.description_prompt_template.format(feature_name=feature_name)
        
        for attempt in range(retry_count):
            try:
                logger.info(f"Генерация описания для признака '{feature_name}' (попытка {attempt + 1}/{retry_count})...")
                
                with GigaChat(
                    credentials=self.credentials,
                    verify_ssl_certs=False
                ) as giga:
                    response = giga.chat(prompt)
                    description = response.choices[0].message.content.strip()
                    
                    # Очистка описания от возможных markdown блоков
                    if description.startswith("```"):
                        # Убираем markdown блоки
                        lines = description.split('\n')
                        description = '\n'.join([line for line in lines if not line.strip().startswith('```')])
                        description = description.strip()
                    
                    logger.info(f"Описание для '{feature_name}' успешно сгенерировано ({len(description)} символов)")
                    return description
                    
            except Exception as e:
                logger.error(f"Ошибка при генерации описания для '{feature_name}' (попытка {attempt + 1}): {e}")
                if attempt < retry_count - 1:
                    wait_time = (attempt + 1) * 2  # Экспоненциальная задержка
                    logger.info(f"Ожидание {wait_time} секунд перед повторной попыткой...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Не удалось сгенерировать описание для '{feature_name}' после {retry_count} попыток")
                    return None
        
        return None

    def generate_descriptions_batch(
        self,
        feature_names: List[str],
        delay_between_requests: float = 1.0,
        save_progress: bool = True,
        progress_file: str = "features_descriptions_progress.json"
    ) -> Dict[str, str]:
        """
        Генерация описаний для списка признаков с сохранением прогресса.
        
        Args:
            feature_names: Список названий признаков
            delay_between_requests: Задержка между запросами (секунды)
            save_progress: Сохранять ли прогресс в файл
            progress_file: Путь к файлу прогресса
            
        Returns:
            Словарь {название_признака: описание}
        """
        descriptions = {}
        
        # Загрузка существующего прогресса, если есть
        if save_progress and os.path.exists(progress_file):
            try:
                import json
                with open(progress_file, 'r', encoding='utf-8') as f:
                    descriptions = json.load(f)
                logger.info(f"Загружен прогресс: {len(descriptions)} описаний уже готово")
            except Exception as e:
                logger.warning(f"Не удалось загрузить прогресс: {e}")
        
        total_features = len(feature_names)
        processed = len(descriptions)
        
        logger.info(f"Начало генерации описаний. Всего признаков: {total_features}, уже обработано: {processed}")
        
        for idx, feature_name in enumerate(feature_names, 1):
            # Пропускаем уже обработанные признаки
            if feature_name in descriptions and descriptions[feature_name]:
                logger.info(f"[{idx}/{total_features}] Пропуск '{feature_name}' (уже есть описание)")
                continue
            
            logger.info(f"[{idx}/{total_features}] Обработка признака: '{feature_name}'")
            
            description = self.generate_description(feature_name)
            
            if description:
                descriptions[feature_name] = description
            else:
                descriptions[feature_name] = ""  # Сохраняем пустое описание, чтобы не повторять
        
            # Сохранение прогресса
            if save_progress:
                try:
                    import json
                    with open(progress_file, 'w', encoding='utf-8') as f:
                        json.dump(descriptions, f, ensure_ascii=False, indent=2)
                    logger.debug(f"Прогресс сохранен: {len(descriptions)} описаний")
                except Exception as e:
                    logger.warning(f"Не удалось сохранить прогресс: {e}")
            
            # Задержка между запросами для избежания rate limiting
            if idx < total_features:
                time.sleep(delay_between_requests)
        
        logger.info(f"Генерация описаний завершена. Обработано: {len(descriptions)} признаков")
        return descriptions


def extract_features_from_csv(csv_path: str) -> List[str]:
    """
    Извлечение списка признаков (колонок) из CSV файла.
    
    Args:
        csv_path: Путь к CSV файлу
        
    Returns:
        Список названий колонок (признаков)
    """
    logger.info(f"Чтение CSV файла: {csv_path}")
    try:
        df = pd.read_csv(csv_path, nrows=1)  # Читаем только заголовки
        features = list(df.columns)
        logger.info(f"Извлечено {len(features)} признаков из CSV файла")
        return features
    except Exception as e:
        logger.error(f"Ошибка чтения CSV файла: {e}")
        raise


def create_features_database(
    csv_path: str,
    output_path: str = "features_database.csv",
    credentials: str = GIGACHAT_CREDENTIALS,
    delay_between_requests: float = 1.0,
    save_progress: bool = True
) -> pd.DataFrame:
    """
    Создание базы данных признаков с описаниями.
    
    Args:
        csv_path: Путь к исходному CSV файлу с данными
        output_path: Путь к выходному CSV файлу с базой данных признаков
        credentials: Учетные данные GigaChat
        delay_between_requests: Задержка между запросами к GigaChat (секунды)
        save_progress: Сохранять ли прогресс генерации описаний
        
    Returns:
        DataFrame с базой данных признаков
    """
    # Извлечение признаков из CSV
    features = extract_features_from_csv(csv_path)
    
    # Инициализация генератора описаний
    generator = FeatureDescriptionGenerator(credentials)
    
    # Генерация описаний
    progress_file = output_path.replace('.csv', '_progress.json')
    descriptions = generator.generate_descriptions_batch(
        features,
        delay_between_requests=delay_between_requests,
        save_progress=save_progress,
        progress_file=progress_file
    )
    
    # Создание DataFrame с результатами
    data = []
    for idx, feature_name in enumerate(features, 1):
        description = descriptions.get(feature_name, "")
        data.append({
            'index': idx,
            'feature_name': feature_name,
            'description': description
        })
    
    df_result = pd.DataFrame(data)
    
    # Сохранение в CSV
    logger.info(f"Сохранение базы данных признаков в файл: {output_path}")
    df_result.to_csv(output_path, index=False, encoding='utf-8-sig')
    logger.info(f"База данных сохранена: {len(df_result)} признаков")
    
    return df_result


if __name__ == "__main__":
    # Путь к исходному CSV файлу
    csv_path = "/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/parsed_layers.csv"
    
    # Путь к выходному файлу с базой данных признаков
    output_path = "/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/features_database.csv"
    
    # Проверка существования исходного файла
    if not os.path.exists(csv_path):
        logger.error(f"Исходный CSV файл не найден: {csv_path}")
        exit(1)
    
    logger.info("="*80)
    logger.info("СОЗДАНИЕ БАЗЫ ДАННЫХ ПРИЗНАКОВ С ОПИСАНИЯМИ")
    logger.info("="*80)
    logger.info(f"Исходный файл: {csv_path}")
    logger.info(f"Выходной файл: {output_path}")
    logger.info("="*80)
    
    try:
        # Создание базы данных
        features_db = create_features_database(
            csv_path=csv_path,
            output_path=output_path,
            credentials=GIGACHAT_CREDENTIALS,
            delay_between_requests=1.0,  # Задержка 1 секунда между запросами
            save_progress=True
        )
        
        # Вывод статистики
        logger.info("\n" + "="*80)
        logger.info("СТАТИСТИКА")
        logger.info("="*80)
        logger.info(f"Всего признаков: {len(features_db)}")
        logger.info(f"Признаков с описаниями: {features_db['description'].str.len().gt(0).sum()}")
        logger.info(f"Признаков без описаний: {features_db['description'].str.len().eq(0).sum()}")
        logger.info("="*80)
        
        # Вывод первых нескольких записей
        logger.info("\nПервые 5 записей базы данных:")
        print("\n", features_db.head().to_string(index=False))
        
    except Exception as e:
        logger.error(f"Ошибка при создании базы данных: {e}", exc_info=True)
        exit(1)

