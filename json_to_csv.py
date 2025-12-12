import json
import pandas as pd
from shapely.geometry import shape
from shapely.wkt import loads
from shapely.errors import WKTReadingError
import numpy as np

# Функция для извлечения центроида из WKT (lon, lat)
def get_centroid(wkt_str):
    if wkt_str is None or not wkt_str.strip():
        return np.nan, np.nan
    try:
        geom = loads(wkt_str)
        if geom.is_empty:
            return np.nan, np.nan
        centroid = geom.centroid
        return centroid.x, centroid.y
    except (WKTReadingError, ValueError):
        print(f"Ошибка парсинга WKT: {wkt_str[:50]}...")
        return np.nan, np.nan

# Универсальный пайплайн: JSON -> DF -> CSV
def json_to_csv(json_path, csv_path='features.csv', target_col=None):
    # 1. Загрузка JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 2. Сбор всех фич в список рядов
    rows = []
    for layer_name, features in data.items():
        if not isinstance(features, list):
            continue  # Пропуск не-листов
        
        for feat in features:
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
                # Очистка: str -> float если возможно (для чисел типа "1.0-1.5%" -> среднее)
                if isinstance(attr_val, str):
                    if '%' in attr_val:
                        attr_val = attr_val.replace('%', '').strip()
                    if '-' in attr_val:
                        try:
                            low, high = map(float, attr_val.split('-'))
                            attr_val = (low + high) / 2
                        except ValueError:
                            pass
                    else:
                        try:
                            attr_val = float(attr_val)
                        except ValueError:
                            pass
                row[f"{layer_name}_{attr_key}"] = attr_val
            
            rows.append(row)
    
    # 3. DataFrame
    df = pd.DataFrame(rows)
    
    # 4. Обработка: заполнить NaN (медиана для чисел, 'unknown' для str)
    for col in df.columns:
        if pd.api.types.is_numeric_dtype(df[col]):
            df[col].fillna(df[col].median(), inplace=True)
        elif pd.api.types.is_string_dtype(df[col]):
            df[col].fillna('unknown', inplace=True)
    
    # 5. Если есть target (e.g., 'has_oil_gas'), переместить в конец
    if target_col and target_col in df.columns:
        target = df.pop(target_col)
        df[target_col] = target
    
    # 6. Сохранить CSV
    df.to_csv(csv_path, index=False, encoding='utf-8')
    print(f"CSV сохранен: {csv_path}")
    print(f"Форма: {df.shape}")
    print(df.head())
    
    return df

# Пример запуска
if __name__ == "__main__":
    # Укажи путь к твоему JSON (он больше, но код универсальный)
    json_path = "parsed_project.json"  # Или полный путь
    df = json_to_csv(json_path, csv_path="pars_test.csv", target_col="has_oil_gas")  # Если есть target