"""
Улучшенный модуль для конвертации JSON в CSV.

Улучшения:
- Улучшенная обработка типов данных
- Нормализация имен колонок
- Обработка дубликатов
- Улучшенная обработка NaN значений
- Поддержка различных стратегий заполнения пропусков
- Валидация данных
- Прогресс-бар
- Сохранение метаданных
"""

import json
import pandas as pd
import numpy as np
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from shapely.wkt import loads
from shapely.errors import WKTReadingError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def normalize_column_name(name: str) -> str:
    """
    Нормализация имени колонки для CSV.
    
    Args:
        name: Исходное имя колонки
        
    Returns:
        Нормализованное имя
    """
    # Удаление специальных символов
    name = re.sub(r'[^\w\s-]', '', name)
    # Замена пробелов на подчеркивания
    name = re.sub(r'\s+', '_', name)
    # Удаление множественных подчеркиваний
    name = re.sub(r'_+', '_', name)
    # Удаление подчеркиваний в начале/конце
    name = name.strip('_')
    # Ограничение длины
    if len(name) > 100:
        name = name[:100]
    return name.lower()

def parse_numeric_range(value: str) -> Optional[float]:
    """
    Парсинг числовых диапазонов типа "1.0-1.5%" или "10-20".
    
    Args:
        value: Строка с диапазоном
        
    Returns:
        Среднее значение диапазона или None
    """
    if not isinstance(value, str):
        return None
    
    # Удаление процентов и пробелов
    value = value.replace('%', '').strip()
    
    # Поиск диапазона
    if '-' in value:
        try:
            parts = value.split('-')
            if len(parts) == 2:
                low = float(parts[0].strip())
                high = float(parts[1].strip())
                return (low + high) / 2
        except (ValueError, IndexError):
            pass
    
    # Попытка преобразовать в число
    try:
        return float(value)
    except ValueError:
        return None

def clean_numeric_value(value: Any) -> Optional[float]:
    """
    Очистка и преобразование значения в число.
    
    Args:
        value: Значение для преобразования
        
    Returns:
        Число или None
    """
    if pd.isna(value) or value is None:
        return None
    
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, str):
        # Удаление пробелов
        value = value.strip()
        if not value or value.lower() in ['nan', 'none', 'null', '']:
            return None
        
        # Парсинг диапазонов
        parsed = parse_numeric_range(value)
        if parsed is not None:
            return parsed
    
    return None

def get_centroid(wkt_str: Optional[str]) -> tuple:
    """
    Извлечение центроида из WKT с улучшенной обработкой ошибок.
    
    Args:
        wkt_str: WKT строка
        
    Returns:
        Кортеж (lon, lat) или (np.nan, np.nan)
    """
    if wkt_str is None or not isinstance(wkt_str, str) or not wkt_str.strip():
        return np.nan, np.nan
    
    try:
        geom = loads(wkt_str)
        if geom.is_empty:
            return np.nan, np.nan
        centroid = geom.centroid
        return centroid.x, centroid.y
    except (WKTReadingError, ValueError, AttributeError) as e:
        logger.debug(f"Ошибка парсинга WKT: {str(e)[:50]}")
        return np.nan, np.nan

def detect_column_type(series: pd.Series) -> str:
    """
    Определение типа колонки для оптимальной обработки.
    
    Args:
        series: Серия данных
        
    Returns:
        Тип: 'numeric', 'categorical', 'text', 'mixed'
    """
    non_null = series.dropna()
    if len(non_null) == 0:
        return 'empty'
    
    numeric_count = 0
    for val in non_null.head(100):  # Проверяем первые 100 значений
        if clean_numeric_value(val) is not None:
            numeric_count += 1
    
    numeric_ratio = numeric_count / len(non_null.head(100))
    
    if numeric_ratio > 0.8:
        return 'numeric'
    elif numeric_ratio < 0.2:
        return 'text'
    else:
        return 'mixed'

def fill_missing_values(
    df: pd.DataFrame,
    strategy: str = 'smart',
    numeric_fill: str = 'median',
    categorical_fill: str = 'mode'
) -> pd.DataFrame:
    """
    Заполнение пропущенных значений с умной стратегией.
    
    Args:
        df: DataFrame
        strategy: Стратегия ('smart', 'median', 'mean', 'mode', 'forward_fill')
        numeric_fill: Метод для числовых ('median', 'mean', 'zero')
        categorical_fill: Метод для категориальных ('mode', 'unknown', 'most_frequent')
        
    Returns:
        DataFrame с заполненными значениями
    """
    df = df.copy()
    
    for col in df.columns:
        if col in ['layer', 'id', 'lon', 'lat']:
            continue
        
        if df[col].isna().sum() == 0:
            continue
        
        col_type = detect_column_type(df[col])
        
        if col_type == 'numeric':
            if numeric_fill == 'median':
                fill_value = df[col].median()
            elif numeric_fill == 'mean':
                fill_value = df[col].mean()
            elif numeric_fill == 'zero':
                fill_value = 0
            else:
                fill_value = df[col].median()
            
            if pd.isna(fill_value):
                fill_value = 0
            
            df[col].fillna(fill_value, inplace=True)
            
        elif col_type in ['categorical', 'text', 'mixed']:
            if categorical_fill == 'mode':
                mode_value = df[col].mode()
                fill_value = mode_value[0] if len(mode_value) > 0 else 'unknown'
            elif categorical_fill == 'unknown':
                fill_value = 'unknown'
            else:
                fill_value = 'unknown'
            
            df[col].fillna(fill_value, inplace=True)
    
    return df

def remove_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Удаление дублирующихся колонок.
    
    Args:
        df: DataFrame
        
    Returns:
        DataFrame без дубликатов
    """
    # Находим дубликаты по содержимому
    duplicate_cols = []
    seen_cols = {}
    
    for col in df.columns:
        col_hash = hash(tuple(df[col].dropna().head(100)))
        if col_hash in seen_cols:
            duplicate_cols.append(col)
        else:
            seen_cols[col_hash] = col
    
    if duplicate_cols:
        logger.info(f"Удалено {len(duplicate_cols)} дублирующихся колонок")
        df = df.drop(columns=duplicate_cols)
    
    return df

def json_to_csv(
    json_path: str,
    csv_path: str = 'features.csv',
    target_col: Optional[str] = None,
    normalize_names: bool = True,
    fill_strategy: str = 'smart',
    remove_duplicates: bool = True,
    chunk_size: Optional[int] = None,
    progress_callback: Optional[Callable] = None
) -> pd.DataFrame:
    """
    Улучшенная конвертация JSON в CSV.
    
    Args:
        json_path: Путь к JSON файлу
        csv_path: Путь для сохранения CSV
        target_col: Имя целевой колонки (переместится в конец)
        normalize_names: Нормализовать ли имена колонок
        fill_strategy: Стратегия заполнения пропусков
        remove_duplicates: Удалять ли дубликаты колонок
        chunk_size: Размер чанка для обработки (None = все сразу)
        progress_callback: Функция для отслеживания прогресса
        
    Returns:
        DataFrame с данными
    """
    logger.info(f"Загрузка JSON: {json_path}")
    
    # Загрузка JSON
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Ошибка загрузки JSON: {e}")
        raise
    
    # Сбор всех фич в список рядов
    rows = []
    total_features = sum(len(features) if isinstance(features, list) else 0 
                        for features in data.values())
    processed = 0
    
    logger.info(f"Обработка {total_features} объектов из {len(data)} слоев")
    
    for layer_name, features in data.items():
        if not isinstance(features, list):
            logger.warning(f"Пропуск не-листа: {layer_name}")
            continue
        
        for feat in features:
            try:
                row = {
                    'layer': layer_name,
                    'id': feat.get('id'),
                }
                
                # Геометрия: центроид (lon, lat)
                wkt = feat.get('geometry_wkt')
                lon, lat = get_centroid(wkt)
                row['lon'] = lon
                row['lat'] = lat
                
                # Атрибуты: flatten с префиксом layer_ для уникальности
                attrs = feat.get('attributes', {})
                for attr_key, attr_val in attrs.items():
                    # Очистка значений
                    cleaned_val = clean_numeric_value(attr_val)
                    if cleaned_val is not None:
                        attr_val = cleaned_val
                    
                    # Нормализация имени колонки
                    col_name = f"{layer_name}_{attr_key}"
                    if normalize_names:
                        col_name = normalize_column_name(col_name)
                    
                    row[col_name] = attr_val
                
                rows.append(row)
                processed += 1
                
                # Прогресс
                if progress_callback and processed % 100 == 0:
                    progress_callback(processed, total_features)
                
            except Exception as e:
                logger.warning(f"Ошибка обработки feature {feat.get('id')}: {e}")
                continue
    
    logger.info(f"Создание DataFrame из {len(rows)} строк")
    
    # DataFrame
    df = pd.DataFrame(rows)
    
    # Удаление дубликатов колонок
    if remove_duplicates:
        df = remove_duplicate_columns(df)
    
    # Заполнение пропусков
    logger.info("Заполнение пропущенных значений...")
    df = fill_missing_values(df, strategy=fill_strategy)
    
    # Перемещение целевой колонки в конец
    if target_col and target_col in df.columns:
        target = df.pop(target_col)
        df[target_col] = target
    
    # Сохранение CSV
    logger.info(f"Сохранение CSV: {csv_path}")
    try:
        df.to_csv(csv_path, index=False, encoding='utf-8')
        file_size = Path(csv_path).stat().st_size / (1024 * 1024)  # MB
        logger.info(f"CSV сохранен: {csv_path} ({file_size:.2f} MB)")
        logger.info(f"Форма: {df.shape[0]} строк × {df.shape[1]} колонок")
    except Exception as e:
        logger.error(f"Ошибка сохранения CSV: {e}")
        raise
    
    # Сохранение метаданных
    metadata_path = csv_path.replace('.csv', '_metadata.json')
    metadata = {
        'source_json': json_path,
        'rows': int(df.shape[0]),
        'columns': int(df.shape[1]),
        'column_names': list(df.columns),
        'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
        'missing_values': {col: int(df[col].isna().sum()) for col in df.columns},
        'normalized_names': normalize_names,
        'fill_strategy': fill_strategy
    }
    
    try:
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Метаданные сохранены: {metadata_path}")
    except Exception as e:
        logger.warning(f"Не удалось сохранить метаданные: {e}")
    
    return df

# Пример использования
if __name__ == "__main__":
    def progress(current, total):
        if total > 0:
            print(f"Прогресс: {current}/{total} ({current/total*100:.1f}%)")
    
    json_path = "parsed_project.json"
    if Path(json_path).exists():
        df = json_to_csv(
            json_path,
            csv_path="pars_test_improved.csv",
            target_col="has_oil_gas",
            normalize_names=True,
            fill_strategy='smart',
            progress_callback=progress
        )
        print("\nПервые строки:")
        print(df.head())
        print("\nИнформация о данных:")
        print(df.info())
    else:
        print(f"Файл {json_path} не найден")

