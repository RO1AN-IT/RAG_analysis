# Парсер слоев GIS данных

## Описание

Парсер для извлечения данных из shapefiles (.shp) и JavaScript файлов с геоданными из директории ЦК(25.06.25). Извлекает атрибуты, геометрию и сохраняет все в единую CSV таблицу.

## Возможности

- ✅ Парсинг shapefiles (.shp) с атрибутами из .dbf
- ✅ Парсинг JS файлов с GeoJSON данными
- ✅ Извлечение координат (точек, границ, центроидов)
- ✅ Сохранение в CSV с автоматическим определением колонок
- ✅ Статистика обработки

## Установка зависимостей

### Минимальные зависимости (только для JS файлов):
```bash
pip install pandas
```

### Для полной поддержки shapefiles:
```bash
# Вариант 1: geopandas (рекомендуется)
pip install geopandas

# Вариант 2: fiona + shapely
pip install fiona shapely
```

## Использование

### Базовое использование:
```bash
python layer_parser.py
```

### С указанием путей:
```bash
python layer_parser.py "/path/to/ЦК(25.06.25)" "output.csv"
```

### В коде:
```python
from layer_parser import LayerParser

# Создание парсера
parser = LayerParser("/path/to/ЦК(25.06.25)")

# Парсинг всех слоев
parser.parse_all_layers()

# Или ограниченное количество для теста
parser.parse_all_layers(max_files=10)

# Сохранение в CSV
parser.save_to_csv("parsed_layers.csv")
```

## Структура выходного CSV

CSV файл содержит следующие колонки:

### Стандартные поля:
- `layer_name` - имя слоя (имя файла без расширения)
- `layer_path` - относительный путь к файлу
- `layer_type` - тип слоя ("shapefile" или "js_file")
- `geometry_type` - тип геометрии (Point, Polygon, LineString и т.д.)

### Геометрические поля:
- `lon`, `lat` - координаты для точек
- `min_lon`, `min_lat`, `max_lon`, `max_lat` - границы для полигонов/линий
- `centroid_lon`, `centroid_lat` - координаты центроида

### Атрибуты слоя:
Все остальные поля из атрибутов shapefile или properties GeoJSON

## Примеры

### Пример 1: Парсинг всех слоев
```python
from layer_parser import LayerParser

parser = LayerParser("ЦК(25.06.25)")
parser.parse_all_layers()
parser.save_to_csv("all_layers.csv")
```

### Пример 2: Обработка только shapefiles
```python
from layer_parser import LayerParser

parser = LayerParser("ЦК(25.06.25)")
shapefiles = parser.find_shapefiles()

for shp in shapefiles[:5]:  # Первые 5 файлов
    features = parser.parse_shapefile(shp)
    print(f"{shp.name}: {len(features)} объектов")
```

### Пример 3: Обработка только JS файлов
```python
from layer_parser import LayerParser

parser = LayerParser("ЦК(25.06.25)")
js_files = parser.find_js_data_files()

for js_file in js_files[:5]:  # Первые 5 файлов
    features = parser.parse_js_file(js_file)
    print(f"{js_file.name}: {len(features)} объектов")
```

## Форматы данных

### Shapefiles
Парсер читает:
- `.shp` - геометрия
- `.dbf` - атрибуты
- `.prj` - проекция (информация сохраняется, но не парсится)

### JS файлы
Парсер поддерживает форматы:
- `var json_xxx = {"type":"FeatureCollection",...}` - стандартный формат
- `L.geoJSON({...})` - Leaflet формат
- Прямой GeoJSON в тексте

## Обработка ошибок

Парсер продолжает работу при ошибках:
- Нечитаемые файлы пропускаются с предупреждением
- Ошибки геометрии логируются, но не останавливают процесс
- Статистика показывает успешно обработанные файлы

## Производительность

- Для тестирования используйте `max_files` параметр
- Большие shapefiles обрабатываются построчно
- JS файлы читаются целиком (может быть медленно для очень больших файлов)

## Выходные данные

После выполнения создается:
1. CSV файл с данными
2. Статистика в консоли:
   - Количество найденных файлов
   - Количество обработанных файлов
   - Общее количество объектов
   - Количество строк и колонок в CSV

## Примечания

- Парсер автоматически определяет структуру данных
- Все колонки из всех слоев объединяются в один CSV
- Отсутствующие значения заполняются пустыми строками
- Координаты извлекаются в WGS84 (если доступно)



