import React, { useEffect, useRef } from 'react';
import './MapDisplay.css';

function MapDisplay({ coordinates }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);

  useEffect(() => {
    if (!coordinates || coordinates.length === 0) return;

    // Функция инициализации карты
    const initMap = () => {
      if (window.ymaps && window.ymaps.ready) {
        window.ymaps.ready(() => {
          if (mapInstanceRef.current) {
            mapInstanceRef.current.destroy();
          }

          // Создаем карту
          const map = new window.ymaps.Map(mapRef.current, {
            center: [coordinates[0].lat, coordinates[0].lon],
            zoom: 6,
            controls: ['zoomControl', 'fullscreenControl']
          });

          // Добавляем метки для каждой координаты
          coordinates.forEach((coord, index) => {
            const placemark = new window.ymaps.Placemark(
              [coord.lat, coord.lon],
              {
                balloonContent: coord.info || `Точка ${index + 1}`,
                hintContent: `Долгота: ${coord.lon}, Широта: ${coord.lat}`
              },
              {
                preset: 'islands#blueDotIcon'
              }
            );
            map.geoObjects.add(placemark);
          });

          // Если координат несколько, устанавливаем границы видимости
          if (coordinates.length > 1) {
            const bounds = coordinates.map(coord => [coord.lat, coord.lon]);
            map.setBounds(bounds, {
              checkZoomRange: true,
              duration: 500
            });
          }

          mapInstanceRef.current = map;
        });
      } else if (window.ymaps) {
        // Если ymaps уже загружен, но ready не доступен
        try {
          if (mapInstanceRef.current) {
            mapInstanceRef.current.destroy();
          }

          const map = new window.ymaps.Map(mapRef.current, {
            center: [coordinates[0].lat, coordinates[0].lon],
            zoom: 6,
            controls: ['zoomControl', 'fullscreenControl']
          });

          coordinates.forEach((coord, index) => {
            const placemark = new window.ymaps.Placemark(
              [coord.lat, coord.lon],
              {
                balloonContent: coord.info || `Точка ${index + 1}`,
                hintContent: `Долгота: ${coord.lon}, Широта: ${coord.lat}`
              },
              {
                preset: 'islands#blueDotIcon'
              }
            );
            map.geoObjects.add(placemark);
          });

          if (coordinates.length > 1) {
            const bounds = coordinates.map(coord => [coord.lat, coord.lon]);
            map.setBounds(bounds, {
              checkZoomRange: true,
              duration: 500
            });
          }

          mapInstanceRef.current = map;
        } catch (error) {
          console.error('Ошибка создания карты:', error);
        }
      } else {
        // Если ymaps еще не загружен, ждем
        const checkInterval = setInterval(() => {
          if (window.ymaps) {
            clearInterval(checkInterval);
            initMap();
          }
        }, 100);

        // Таймаут через 10 секунд
        setTimeout(() => {
          clearInterval(checkInterval);
          if (!window.ymaps) {
            console.error('Яндекс карты не загружены за 10 секунд');
          }
        }, 10000);
      }
    };

    initMap();

    // Очистка при размонтировании
    return () => {
      if (mapInstanceRef.current) {
        try {
          mapInstanceRef.current.destroy();
        } catch (e) {
          console.error('Ошибка при уничтожении карты:', e);
        }
        mapInstanceRef.current = null;
      }
    };
  }, [coordinates]);

  if (!coordinates || coordinates.length === 0) {
    return null;
  }

  return (
    <div className="map-container">
      <div className="map-header">
        <h3>🗺️ Карта найденных мест</h3>
        <span className="markers-count">{coordinates.length} меток</span>
      </div>
      <div ref={mapRef} className="yandex-map" />
    </div>
  );
}

export default MapDisplay;

