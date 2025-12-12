import sys
import os
import json
from qgis.core import QgsApplication, QgsVectorLayer, QgsFeature, QgsProject
from qgis.PyQt.QtCore import QVariant 

QgsApplication.setPrefixPath("/opt/anaconda3/envs/pyqgis_env/bin", True) 
qgs = QgsApplication([], False)
qgs.initQgis()

def convert_qvariant(value):
    if isinstance(value, QVariant):
        if value.isNull():
            return None
        return value.value()
    elif isinstance(value, (list, tuple)):
        return [safe_convert(v) for v in value]
    elif isinstance(value, dict):
        return {k: safe_convert(v) for k, v in value.items()}
    elif hasattr(value, '__dict__'):
        return str(value)  
    else:
        return value

def parse_shapefile(shp_path):
    layer = QgsVectorLayer(shp_path, os.path.basename(shp_path).split('.')[0], "ogr")
    if not layer.isValid():
        print(f"Ошибка загрузки слоя: {shp_path}")
        return None
    
    print(f"Слой загружен: {layer.name()}")
    print(f"Тип геометрии: {layer.wkbType()}")
    print(f"Количество объектов: {layer.featureCount()}")
    
    fields = layer.fields()
    print("Поля атрибутов:")
    for field in fields:
        print(f"- {field.name()} ({field.typeName()})")
    
    data = []
    features = layer.getFeatures()
    for feature in features:
        geom = feature.geometry()
        attrs = feature.attributes()
        data.append({
            "id": feature.id(),
            "geometry_wkt": geom.asWkt() if geom else None,
            "geometry_type": geom.type() if geom else None,
            "attributes": {fields[idx].name(): convert_qvariant(attrs[idx]) for idx in range(len(attrs))}
        })
    
    return data

def parse_qgis_project(project_path):
    project = QgsProject.instance()
    if not project.read(project_path):
        print(f"Ошибка загрузки проекта: {project_path}")
        return None
    
    print(f"Проект загружен: {project.title()}")
    layers = project.mapLayers().values()
    print(f"Количество слоев: {len(layers)}")
    
    all_data = {}
    for layer in layers:
        if layer.type() == layer.VectorLayer:  #
            print(f"\nПарсинг слоя: {layer.name()}")
            data = []
            features = layer.getFeatures()
            fields = layer.fields()
            for feature in features:
                geom = feature.geometry()
                attrs = feature.attributes()
                data.append({
                    "id": feature.id(),
                    "geometry_wkt": geom.asWkt() if geom else None,
                    "attributes": {fields[idx].name(): convert_qvariant(attrs[idx]) for idx in range(len(attrs))}
                })
            all_data[layer.name()] = data
    
    return all_data

shp_path = "Разделенный ЦК/Проект/Современная береговая линия.shp"
parsed_shp = parse_shapefile(shp_path)
if parsed_shp:
    with open("parsed_shp.json", "w", encoding="utf-8") as f:
        json.dump(parsed_shp, f, ensure_ascii=False, indent=4)
    print("Данные из шейпфайла сохранены в parsed_shp.json")

qgz_path = "Разделенный ЦК/Проект/Цифровой Каспий (Южный).qgz"
parsed_project = parse_qgis_project(qgz_path)
if parsed_project:
    with open("parsed_project.json", "w", encoding="utf-8") as f:
        json.dump(parsed_project, f, ensure_ascii=False, indent=4)
    print("Данные из проекта сохранены в parsed_project.json")

qgs.exitQgis()
