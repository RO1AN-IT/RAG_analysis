"""
Парсер слоев из директории ЦК(25.06.25).
Извлекает данные из shapefiles и JS файлов, сохраняет в CSV таблицу.
"""

import os
import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
import re

# Попытка импорта pandas для проверки NaN
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LayerParser:
    """Парсер для извлечения данных из GIS слоев."""
    
    def __init__(self, base_path: str):
        """
        Инициализация парсера.
        
        Args:
            base_path: Базовый путь к директории с данными
        """
        self.base_path = Path(base_path)
        self.layers_data = []
        self.stats = {
            "shapefiles_found": 0,
            "shapefiles_processed": 0,
            "js_files_found": 0,
            "js_files_processed": 0,
            "total_features": 0
        }
    
    def find_shapefiles(self) -> List[Path]:
        """
        Поиск всех shapefiles в директории.
        
        Returns:
            Список путей к .shp файлам
        """
        shapefiles = []
        for shp_file in self.base_path.rglob("*.shp"):
            shapefiles.append(shp_file)
        self.stats["shapefiles_found"] = len(shapefiles)
        logger.info(f"Найдено shapefiles: {len(shapefiles)}")
        return shapefiles
    
    def find_js_data_files(self) -> List[Path]:
        """
        Поиск JS файлов с данными (обычно в папках data/).
        
        Returns:
            Список путей к .js файлам
        """
        js_files = []
        for js_file in self.base_path.rglob("*.js"):
            # Игнорируем библиотечные JS файлы
            if "data" in str(js_file) or "js" in str(js_file.parent.name.lower()):
                if not any(skip in str(js_file) for skip in ["leaflet", "jquery", "bootstrap", "min.js"]):
                    js_files.append(js_file)
        self.stats["js_files_found"] = len(js_files)
        logger.info(f"Найдено JS файлов с данными: {len(js_files)}")
        return js_files
    
    def parse_shapefile(self, shp_path: Path) -> List[Dict[str, Any]]:
        """
        Парсинг shapefile с использованием geopandas или альтернативных методов.
        
        Args:
            shp_path: Путь к .shp файлу
            
        Returns:
            Список словарей с данными объектов
        """
        features = []
        
        try:
            # Попытка использовать geopandas
            try:
                import geopandas as gpd
                gdf = gpd.read_file(str(shp_path))
                
                # Преобразование в список словарей
                for idx, row in gdf.iterrows():
                    feature = {
                        "layer_name": shp_path.stem,
                        "layer_path": str(shp_path.relative_to(self.base_path)),
                        "layer_type": "shapefile",
                        "geometry_type": str(row.geometry.geom_type) if hasattr(row, 'geometry') else None,
                    }
                    
                    # Добавление всех атрибутов
                    for col in gdf.columns:
                        if col != 'geometry':
                            value = row[col]
                            # Обработка различных типов данных
                            if HAS_PANDAS and pd.isna(value):
                                feature[col] = None
                            elif value is None:
                                feature[col] = None
                            elif isinstance(value, (int, float)):
                                feature[col] = value
                            else:
                                feature[col] = str(value)
                    
                    # Добавление координат (центроид для точек, bounds для остальных)
                    if hasattr(row, 'geometry') and row.geometry is not None:
                        try:
                            if row.geometry.geom_type == 'Point':
                                feature["lon"] = row.geometry.x
                                feature["lat"] = row.geometry.y
                            else:
                                bounds = row.geometry.bounds
                                feature["min_lon"] = bounds[0]
                                feature["min_lat"] = bounds[1]
                                feature["max_lon"] = bounds[2]
                                feature["max_lat"] = bounds[3]
                                # Центроид
                                centroid = row.geometry.centroid
                                feature["centroid_lon"] = centroid.x
                                feature["centroid_lat"] = centroid.y
                        except Exception as e:
                            logger.debug(f"Ошибка обработки геометрии: {e}")
                    
                    features.append(feature)
                
                self.stats["shapefiles_processed"] += 1
                self.stats["total_features"] += len(features)
                logger.info(f"Обработан shapefile: {shp_path.name} ({len(features)} объектов)")
                
            except ImportError:
                # Альтернативный метод через fiona и shapely
                try:
                    import fiona
                    from shapely.geometry import shape
                    
                    with fiona.open(str(shp_path), 'r') as src:
                        for record in src:
                            feature = {
                                "layer_name": shp_path.stem,
                                "layer_path": str(shp_path.relative_to(self.base_path)),
                                "layer_type": "shapefile",
                                "geometry_type": record['geometry']['type'] if record['geometry'] else None,
                            }
                            
                            # Добавление атрибутов
                            for key, value in record['properties'].items():
                                feature[key] = value
                            
                            # Обработка геометрии
                            if record['geometry']:
                                geom = shape(record['geometry'])
                                if geom.geom_type == 'Point':
                                    feature["lon"] = geom.x
                                    feature["lat"] = geom.y
                                else:
                                    bounds = geom.bounds
                                    feature["min_lon"] = bounds[0]
                                    feature["min_lat"] = bounds[1]
                                    feature["max_lon"] = bounds[2]
                                    feature["max_lat"] = bounds[3]
                                    centroid = geom.centroid
                                    feature["centroid_lon"] = centroid.x
                                    feature["centroid_lat"] = centroid.y
                            
                            features.append(feature)
                    
                    self.stats["shapefiles_processed"] += 1
                    self.stats["total_features"] += len(features)
                    logger.info(f"Обработан shapefile: {shp_path.name} ({len(features)} объектов)")
                    
                except ImportError:
                    logger.warning(f"Не установлены geopandas или fiona. Пропуск файла: {shp_path}")
                    return []
                    
        except Exception as e:
            logger.error(f"Ошибка парсинга shapefile {shp_path}: {e}")
            return []
        
        return features
    
    def parse_js_file(self, js_path: Path) -> List[Dict[str, Any]]:
        """
        Парсинг JS файла с геоданными (GeoJSON или другие форматы).
        
        Args:
            js_path: Путь к .js файлу
            
        Returns:
            Список словарей с данными объектов
        """
        features = []
        
        try:
            with open(js_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Попытка извлечь GeoJSON из JS файла
            # Формат: var json__10 = {"type":"FeatureCollection",...}
            geojson_data = None
            
            # Паттерн 1: var json_xxx = {...}
            # Ищем начало JSON объекта после знака =
            var_match = re.search(r'var\s+\w+\s*=\s*(\{)', content)
            if var_match:
                try:
                    start_pos = var_match.end(1) - 1  # Позиция открывающей скобки
                    # Находим соответствующую закрывающую скобку
                    brace_count = 0
                    json_str = ""
                    for i, char in enumerate(content[start_pos:], start_pos):
                        json_str += char
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                # Проверяем, что это действительно JSON
                                geojson_data = json.loads(json_str)
                                if geojson_data.get('type') == 'FeatureCollection':
                                    break
                                else:
                                    geojson_data = None
                                    break
                except (json.JSONDecodeError, ValueError):
                    geojson_data = None
            
            # Паттерн 2: Прямой поиск FeatureCollection
            if not geojson_data:
                fc_match = re.search(r'(\{"type"\s*:\s*"FeatureCollection".*?\})', content, re.DOTALL)
                if fc_match:
                    try:
                        json_str = fc_match.group(1)
                        # Попытка найти закрывающую скобку
                        brace_count = json_str.count('{') - json_str.count('}')
                        if brace_count > 0:
                            # Дополняем до закрытия
                            remaining = content[fc_match.end():]
                            for i, char in enumerate(remaining):
                                if char == '}':
                                    brace_count -= 1
                                    if brace_count == 0:
                                        json_str += remaining[:i+1]
                                        break
                        geojson_data = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass
            
            # Паттерн 3: L.geoJSON({...})
            if not geojson_data:
                leaflet_match = re.search(r'L\.geoJSON\((\{.*?\})\)', content, re.DOTALL)
                if leaflet_match:
                    try:
                        json_str = leaflet_match.group(1)
                        geojson_data = json.loads(json_str)
                    except json.JSONDecodeError:
                        pass
            
            # Если не найден GeoJSON, попробуем найти данные в другом формате
            if not geojson_data:
                # Попытка найти координаты напрямую
                coord_pattern = r'\[(\d+\.?\d*),\s*(\d+\.?\d*)\]'
                coords = re.findall(coord_pattern, content)
                
                if coords:
                    for i, (lon, lat) in enumerate(coords[:100]):  # Ограничение для производительности
                        feature = {
                            "layer_name": js_path.stem,
                            "layer_path": str(js_path.relative_to(self.base_path)),
                            "layer_type": "js_file",
                            "geometry_type": "Point",
                            "lon": float(lon),
                            "lat": float(lat),
                            "feature_id": i
                        }
                        features.append(feature)
                    
                    self.stats["js_files_processed"] += 1
                    self.stats["total_features"] += len(features)
                    logger.info(f"Обработан JS файл: {js_path.name} ({len(features)} объектов)")
                    return features
            
            # Обработка GeoJSON
            if geojson_data:
                if geojson_data.get('type') == 'FeatureCollection':
                    for i, feature_data in enumerate(geojson_data.get('features', [])):
                        feature = {
                            "layer_name": js_path.stem,
                            "layer_path": str(js_path.relative_to(self.base_path)),
                            "layer_type": "js_file",
                            "geometry_type": feature_data.get('geometry', {}).get('type'),
                            "feature_id": i
                        }
                        
                        # Добавление свойств
                        if 'properties' in feature_data:
                            for key, value in feature_data['properties'].items():
                                feature[key] = value
                        
                        # Обработка геометрии
                        geometry = feature_data.get('geometry', {})
                        if geometry:
                            coords = geometry.get('coordinates', [])
                            if geometry.get('type') == 'Point' and len(coords) >= 2:
                                feature["lon"] = coords[0]
                                feature["lat"] = coords[1]
                            elif coords:
                                # Для других типов геометрии берем первую точку или центроид
                                if isinstance(coords[0], (int, float)):
                                    if len(coords) >= 2:
                                        feature["lon"] = coords[0]
                                        feature["lat"] = coords[1]
                                elif isinstance(coords[0], list) and len(coords[0]) >= 2:
                                    feature["lon"] = coords[0][0]
                                    feature["lat"] = coords[0][1]
                        
                        features.append(feature)
                
                self.stats["js_files_processed"] += 1
                self.stats["total_features"] += len(features)
                logger.info(f"Обработан JS файл: {js_path.name} ({len(features)} объектов)")
        
        except Exception as e:
            logger.error(f"Ошибка парсинга JS файла {js_path}: {e}")
        
        return features
    
    def parse_all_layers(self, max_files: Optional[int] = None) -> None:
        """
        Парсинг всех найденных слоев.
        
        Args:
            max_files: Максимальное количество файлов для обработки (None = все)
        """
        logger.info("Начало парсинга слоев...")
        
        # Парсинг shapefiles
        shapefiles = self.find_shapefiles()
        for i, shp_path in enumerate(shapefiles):
            if max_files and i >= max_files:
                break
            try:
                features = self.parse_shapefile(shp_path)
                self.layers_data.extend(features)
            except Exception as e:
                logger.error(f"Ошибка обработки {shp_path}: {e}")
        
        # Парсинг JS файлов
        js_files = self.find_js_data_files()
        for i, js_path in enumerate(js_files):
            if max_files and (len(shapefiles) + i) >= max_files:
                break
            try:
                features = self.parse_js_file(js_path)
                self.layers_data.extend(features)
            except Exception as e:
                logger.error(f"Ошибка обработки {js_path}: {e}")
        
        logger.info(f"Парсинг завершен. Обработано объектов: {len(self.layers_data)}")
    
    def save_to_csv(self, output_path: str) -> None:
        """
        Сохранение данных в CSV файл.
        
        Args:
            output_path: Путь к выходному CSV файлу
        """
        if not self.layers_data:
            logger.warning("Нет данных для сохранения")
            return
        
        # Сбор всех уникальных ключей
        all_keys = set()
        for feature in self.layers_data:
            all_keys.update(feature.keys())
        
        # Сортировка ключей (стандартные поля сначала)
        standard_fields = [
            "layer_name", "layer_path", "layer_type", "geometry_type",
            "lon", "lat", "min_lon", "min_lat", "max_lon", "max_lat",
            "centroid_lon", "centroid_lat", "feature_id"
        ]
        
        ordered_fields = []
        for field in standard_fields:
            if field in all_keys:
                ordered_fields.append(field)
                all_keys.discard(field)
        
        # Остальные поля в алфавитном порядке
        ordered_fields.extend(sorted(all_keys))
        
        # Запись в CSV
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=ordered_fields)
                writer.writeheader()
                
                for feature in self.layers_data:
                    row = {}
                    for field in ordered_fields:
                        value = feature.get(field)
                        # Обработка значений для CSV
                        if value is None:
                            row[field] = ""
                        elif isinstance(value, (int, float)):
                            row[field] = value
                        else:
                            row[field] = str(value)
                    writer.writerow(row)
            
            logger.info(f"Данные сохранены в CSV: {output_path}")
            logger.info(f"Всего строк: {len(self.layers_data)}")
            logger.info(f"Колонок: {len(ordered_fields)}")
            
            # Вывод статистики
            print("\n" + "="*80)
            print("СТАТИСТИКА ПАРСИНГА")
            print("="*80)
            print(f"Найдено shapefiles: {self.stats['shapefiles_found']}")
            print(f"Обработано shapefiles: {self.stats['shapefiles_processed']}")
            print(f"Найдено JS файлов: {self.stats['js_files_found']}")
            print(f"Обработано JS файлов: {self.stats['js_files_processed']}")
            print(f"Всего объектов: {self.stats['total_features']}")
            print(f"Строк в CSV: {len(self.layers_data)}")
            print("="*80)
            
        except Exception as e:
            logger.error(f"Ошибка сохранения CSV: {e}")
            raise


if __name__ == "__main__":
    import sys
    
    # Путь к директории с данными
    base_dir = "/Users/rodionduktanov/anaconda_projects/RAG_Caspian_Analysis/ЦК(25.06.25)"
    
    # Выходной файл
    output_csv = "parsed_layers.csv"
    
    # Проверка аргументов командной строки
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    if len(sys.argv) > 2:
        output_csv = sys.argv[2]
    
    # Создание парсера
    parser = LayerParser(base_dir)
    
    # Парсинг (можно ограничить количество файлов для теста)
    # parser.parse_all_layers(max_files=10)  # Для теста первых 10 файлов
    parser.parse_all_layers()  # Для полного парсинга
    
    # Сохранение в CSV
    parser.save_to_csv(output_csv)
    
    print(f"\nГотово! Данные сохранены в {output_csv}")

