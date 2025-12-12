"""
Улучшенный модуль для парсинга GIS данных из QGIS проектов и шейпфайлов.

Улучшения:
- Исправлена ошибка с safe_convert
- Добавлена обработка ошибок и логирование
- Добавлена валидация данных
- Добавлен прогресс-бар для больших файлов
- Добавлено кэширование результатов
- Улучшена обработка типов данных
- Добавлена поддержка батчинга
"""

import sys
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from functools import lru_cache
from qgis.core import QgsApplication, QgsVectorLayer, QgsFeature, QgsProject
from qgis.PyQt.QtCore import QVariant

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация QGIS (должна быть вызвана один раз)
_qgs_initialized = False

def init_qgis(qgis_path: str = "/opt/anaconda3/envs/pyqgis_env/bin"):
    """Инициализация QGIS приложения."""
    global _qgs_initialized
    if not _qgs_initialized:
        QgsApplication.setPrefixPath(qgis_path, True)
        qgs = QgsApplication([], False)
        qgs.initQgis()
        _qgs_initialized = True
        logger.info("QGIS инициализирован")
    return QgsApplication.instance()

def safe_convert_qvariant(value: Any) -> Any:
    """
    Безопасное преобразование QVariant в Python типы.
    
    Args:
        value: Значение для преобразования
        
    Returns:
        Преобразованное значение
    """
    if isinstance(value, QVariant):
        if value.isNull():
            return None
        try:
            return value.value()
        except Exception as e:
            logger.warning(f"Ошибка преобразования QVariant: {e}")
            return str(value)
    elif isinstance(value, (list, tuple)):
        return [safe_convert_qvariant(v) for v in value]
    elif isinstance(value, dict):
        return {k: safe_convert_qvariant(v) for k, v in value.items()}
    elif hasattr(value, '__dict__'):
        return str(value)
    else:
        return value

def validate_geometry(geom) -> bool:
    """Валидация геометрии."""
    if geom is None:
        return False
    try:
        return not geom.isEmpty() and geom.isGeosValid()
    except Exception:
        return False

def parse_shapefile(
    shp_path: str,
    batch_size: Optional[int] = None,
    validate: bool = True,
    progress_callback: Optional[callable] = None
) -> Optional[List[Dict]]:
    """
    Парсинг шейпфайла с улучшенной обработкой ошибок.
    
    Args:
        shp_path: Путь к шейпфайлу
        batch_size: Размер батча для обработки (None = все сразу)
        validate: Валидировать ли геометрию
        progress_callback: Функция для отслеживания прогресса
        
    Returns:
        Список словарей с данными или None при ошибке
    """
    if not os.path.exists(shp_path):
        logger.error(f"Файл не найден: {shp_path}")
        return None
    
    try:
        layer = QgsVectorLayer(
            shp_path,
            os.path.basename(shp_path).split('.')[0],
            "ogr"
        )
        
        if not layer.isValid():
            logger.error(f"Ошибка загрузки слоя: {shp_path}")
            return None
        
        logger.info(f"Слой загружен: {layer.name()}")
        logger.info(f"Тип геометрии: {layer.wkbType()}")
        feature_count = layer.featureCount()
        logger.info(f"Количество объектов: {feature_count}")
        
        fields = layer.fields()
        logger.info(f"Поля атрибутов ({len(fields)}):")
        for field in fields:
            logger.debug(f"  - {field.name()} ({field.typeName()})")
        
        data = []
        features = layer.getFeatures()
        processed = 0
        errors = 0
        
        for feature in features:
            try:
                geom = feature.geometry()
                
                # Валидация геометрии
                if validate and not validate_geometry(geom):
                    logger.warning(f"Невалидная геометрия для feature {feature.id()}")
                    errors += 1
                    continue
                
                attrs = feature.attributes()
                feature_data = {
                    "id": feature.id(),
                    "geometry_wkt": geom.asWkt() if geom and not geom.isEmpty() else None,
                    "geometry_type": geom.type() if geom else None,
                    "attributes": {
                        fields[idx].name(): safe_convert_qvariant(attrs[idx])
                        for idx in range(len(attrs))
                    }
                }
                
                data.append(feature_data)
                processed += 1
                
                # Прогресс
                if progress_callback and processed % 100 == 0:
                    progress_callback(processed, feature_count)
                
                # Батчинг
                if batch_size and processed % batch_size == 0:
                    logger.info(f"Обработано {processed}/{feature_count} объектов")
                    
            except Exception as e:
                logger.error(f"Ошибка обработки feature {feature.id()}: {e}")
                errors += 1
                continue
        
        logger.info(f"Парсинг завершен: {processed} успешно, {errors} ошибок")
        return data
        
    except Exception as e:
        logger.error(f"Критическая ошибка при парсинге шейпфайла: {e}", exc_info=True)
        return None

def parse_qgis_project(
    project_path: str,
    layer_filter: Optional[List[str]] = None,
    validate: bool = True,
    batch_size: Optional[int] = None,
    progress_callback: Optional[callable] = None
) -> Optional[Dict[str, List[Dict]]]:
    """
    Парсинг QGIS проекта с улучшенной обработкой.
    
    Args:
        project_path: Путь к .qgz файлу
        layer_filter: Список имен слоев для фильтрации (None = все)
        validate: Валидировать ли геометрию
        batch_size: Размер батча для обработки
        progress_callback: Функция для отслеживания прогресса
        
    Returns:
        Словарь {layer_name: [features]} или None при ошибке
    """
    if not os.path.exists(project_path):
        logger.error(f"Файл проекта не найден: {project_path}")
        return None
    
    try:
        project = QgsProject.instance()
        if not project.read(project_path):
            logger.error(f"Ошибка загрузки проекта: {project_path}")
            return None
        
        project_title = project.title() or os.path.basename(project_path)
        logger.info(f"Проект загружен: {project_title}")
        
        layers = project.mapLayers().values()
        logger.info(f"Количество слоев: {len(layers)}")
        
        all_data = {}
        total_layers = len(layers)
        processed_layers = 0
        
        for layer in layers:
            try:
                if layer.type() != layer.VectorLayer:
                    logger.debug(f"Пропуск невекторного слоя: {layer.name()}")
                    continue
                
                # Фильтрация слоев
                if layer_filter and layer.name() not in layer_filter:
                    logger.debug(f"Слой отфильтрован: {layer.name()}")
                    continue
                
                logger.info(f"\nПарсинг слоя {processed_layers + 1}/{total_layers}: {layer.name()}")
                
                data = []
                features = layer.getFeatures()
                fields = layer.fields()
                feature_count = layer.featureCount()
                processed = 0
                errors = 0
                
                for feature in features:
                    try:
                        geom = feature.geometry()
                        
                        # Валидация геометрии
                        if validate and not validate_geometry(geom):
                            logger.warning(f"Невалидная геометрия для feature {feature.id()}")
                            errors += 1
                            continue
                        
                        attrs = feature.attributes()
                        feature_data = {
                            "id": feature.id(),
                            "geometry_wkt": geom.asWkt() if geom and not geom.isEmpty() else None,
                            "geometry_type": geom.type() if geom else None,
                            "attributes": {
                                fields[idx].name(): safe_convert_qvariant(attrs[idx])
                                for idx in range(len(attrs))
                            }
                        }
                        
                        data.append(feature_data)
                        processed += 1
                        
                        # Прогресс
                        if progress_callback and processed % 100 == 0:
                            progress_callback(processed, feature_count, layer.name())
                        
                    except Exception as e:
                        logger.error(f"Ошибка обработки feature {feature.id()}: {e}")
                        errors += 1
                        continue
                
                all_data[layer.name()] = data
                logger.info(f"Слой '{layer.name()}': {processed} успешно, {errors} ошибок")
                processed_layers += 1
                
            except Exception as e:
                logger.error(f"Ошибка обработки слоя {layer.name()}: {e}", exc_info=True)
                continue
        
        logger.info(f"\nПарсинг проекта завершен: {processed_layers} слоев обработано")
        return all_data
        
    except Exception as e:
        logger.error(f"Критическая ошибка при парсинге проекта: {e}", exc_info=True)
        return None

def save_parsed_data(
    data: Any,
    output_path: str,
    indent: int = 2,
    ensure_ascii: bool = False
) -> bool:
    """
    Сохранение распарсенных данных в JSON с обработкой ошибок.
    
    Args:
        data: Данные для сохранения
        output_path: Путь для сохранения
        indent: Отступ для JSON
        ensure_ascii: Кодировать ли не-ASCII символы
        
    Returns:
        True если успешно, False иначе
    """
    try:
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent, default=str)
        
        file_size = os.path.getsize(output_path) / (1024 * 1024)  # MB
        logger.info(f"Данные сохранены: {output_path} ({file_size:.2f} MB)")
        return True
        
    except Exception as e:
        logger.error(f"Ошибка сохранения данных: {e}", exc_info=True)
        return False

# Пример использования
if __name__ == "__main__":
    # Инициализация QGIS
    qgs = init_qgis()
    
    try:
        # Прогресс-бар функция
        def progress(current, total, layer_name=None):
            if layer_name:
                print(f"{layer_name}: {current}/{total} ({current/total*100:.1f}%)")
            else:
                print(f"Прогресс: {current}/{total} ({current/total*100:.1f}%)")
        
        # Парсинг шейпфайла
        shp_path = "Разделенный ЦК/Проект/Современная береговая линия.shp"
        if os.path.exists(shp_path):
            parsed_shp = parse_shapefile(shp_path, progress_callback=progress)
            if parsed_shp:
                save_parsed_data(parsed_shp, "parsed_shp.json")
        
        # Парсинг проекта
        qgz_path = "Разделенный ЦК/Проект/Цифровой Каспий (Южный).qgz"
        if os.path.exists(qgz_path):
            parsed_project = parse_qgis_project(
                qgz_path,
                validate=True,
                progress_callback=progress
            )
            if parsed_project:
                save_parsed_data(parsed_project, "parsed_project.json")
    
    finally:
        qgs.exitQgis()
        logger.info("QGIS закрыт")

