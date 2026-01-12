import React, { useEffect, useRef } from 'react';
import './MapDisplay.css';

function MapDisplay({ coordinates }) {
  const mapRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const containerRef = useRef(null);

  // Функция для обновления размера карты
  const updateMapSize = () => {
    if (mapInstanceRef.current && mapRef.current) {
      try {
        // Обновляем размер карты через container
        const container = mapInstanceRef.current.container;
        if (container && container.fitToViewport) {
          container.fitToViewport();
        } else {
          // Альтернативный способ - принудительное обновление через изменение размера
          const width = mapRef.current.offsetWidth;
          const height = mapRef.current.offsetHeight;
          if (width > 0 && height > 0) {
            mapInstanceRef.current.container.setSize([width, height]);
          }
        }
      } catch (error) {
        console.error('Ошибка обновления размера карты:', error);
      }
    }
  };

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
          
          // Обновляем размер после небольшой задержки для корректной инициализации
          setTimeout(() => {
            updateMapSize();
          }, 100);
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
          
          setTimeout(() => {
            updateMapSize();
          }, 100);
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

  // Обработчик изменения размера контейнера
  useEffect(() => {
    if (!containerRef.current) return;

    // Используем ResizeObserver для отслеживания изменения размера
    const resizeObserver = new ResizeObserver(() => {
      // Небольшая задержка для корректного обновления
      setTimeout(() => {
        updateMapSize();
      }, 50);
    });

    resizeObserver.observe(containerRef.current);

    // Также слушаем изменения размера окна
    const handleResize = () => {
      setTimeout(() => {
        updateMapSize();
      }, 50);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  if (!coordinates || coordinates.length === 0) {
    return null;
  }

  return (
    <div className="map-container" ref={containerRef}>
      <div className="map-header">
        <h3>🗺️ Карта найденных мест</h3>
        <span className="markers-count">{coordinates.length} меток</span>
      </div>
      <div ref={mapRef} className="yandex-map" />
    </div>
  );
}

export default MapDisplay;

