import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';
import './App.css';
import QueryForm from './components/QueryForm';
import ResultsDisplay from './components/ResultsDisplay';
import MapDisplay from './components/MapDisplay';
import VideoAvatar from './components/VideoAvatar';
import useLocalStorage from './hooks/useLocalStorage';

// API URL - для разработки используйте полный URL, для продакшена - относительный путь
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

// Ключи для localStorage
const STORAGE_KEYS = {
  ANSWER: 'rag_app_answer',
  COORDINATES: 'rag_app_coordinates',
  RESULTS_COUNT: 'rag_app_results_count',
  USER_QUERY: 'rag_app_user_query',
  HAS_COORDINATES: 'rag_app_has_coordinates',
  VIDEO_PANEL_SIZE: 'rag_app_video_panel_size',
};

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [progressStep, setProgressStep] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [progressDetails, setProgressDetails] = useState(null);
  
  // Используем localStorage для сохранения состояния
  const [answer, setAnswer] = useLocalStorage(STORAGE_KEYS.ANSWER, '');
  const [coordinates, setCoordinates] = useLocalStorage(STORAGE_KEYS.COORDINATES, []);
  const [resultsCount, setResultsCount] = useLocalStorage(STORAGE_KEYS.RESULTS_COUNT, 0);
  const [userQuery, setUserQuery] = useLocalStorage(STORAGE_KEYS.USER_QUERY, '');
  const [hasCoordinates, setHasCoordinates] = useLocalStorage(STORAGE_KEYS.HAS_COORDINATES, false);
  const [videoPanelSize, setVideoPanelSize] = useLocalStorage(STORAGE_KEYS.VIDEO_PANEL_SIZE, 55);
  const separatorRef = useRef(null);
  const videoPanelRef = useRef(null);
  const resultsPanelRef = useRef(null);
  const containerRef = useRef(null);
  const isDraggingRef = useRef(false);
  const startYRef = useRef(0);
  const startSizeRef = useRef(50);

  // Кастомный обработчик для вертикального разделителя
  const handleSeparatorMouseDown = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    isDraggingRef.current = true;
    startYRef.current = e.clientY;
    startSizeRef.current = videoPanelSize;
    document.body.style.cursor = 'ns-resize';
    document.body.style.userSelect = 'none';
  }, [videoPanelSize]);

  const handleMouseMove = useCallback((e) => {
    if (!isDraggingRef.current || !containerRef.current) return;
    
    const container = containerRef.current;
    const containerHeight = container.offsetHeight;
    const separatorHeight = 8; // высота разделителя
    
    const deltaY = e.clientY - startYRef.current;
    const deltaPercent = (deltaY / containerHeight) * 100;
    
    const newSize = Math.max(30, Math.min(70, startSizeRef.current + deltaPercent));
    setVideoPanelSize(newSize); // Автоматически сохранится в localStorage через хук
  }, []);

  const handleMouseUp = useCallback(() => {
    if (isDraggingRef.current) {
      isDraggingRef.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
  }, []);

  useEffect(() => {
    if (answer) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      
      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [answer, handleMouseMove, handleMouseUp]);

  const handleQuerySubmit = async (userQuery) => {
    setIsLoading(true);
    setProgress(0);
    setProgressStep(0);
    setProgressMessage('');
    setProgressDetails(null);
    setAnswer('');
    setCoordinates([]);
    setResultsCount(0);
    setUserQuery(userQuery);
    setHasCoordinates(false);

    let requestId = null;
    let progressInterval = null;
    let currentTimeout = null;
    let isPollingActive = true;

    try {
      // Отправляем запрос
      const response = await fetch(`${API_BASE_URL}/query/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: userQuery }),
      });

      if (!response.ok) {
        throw new Error(`Ошибка ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      requestId = data.request_id;

      if (!requestId) {
        throw new Error('Не получен request_id от сервера');
      }

      // Начинаем polling прогресса с улучшенной обработкой ошибок
      let consecutiveErrors = 0;
      const maxConsecutiveErrors = 10; // Максимум 10 ошибок подряд
      const maxRequestTime = 10 * 60 * 1000; // Максимум 10 минут на запрос
      const startTime = Date.now();
      let pollInterval = 500; // Начальный интервал polling
      isPollingActive = true;
      currentTimeout = null;
      
      const pollProgress = async () => {
        if (!isPollingActive) return;
        currentTimeout = null; // Сбрасываем ссылку на timeout
        
        // Проверка таймаута запроса
        if (Date.now() - startTime > maxRequestTime) {
          isPollingActive = false;
          setIsLoading(false);
          setAnswer('Ошибка: Превышено время ожидания ответа от сервера. Попробуйте повторить запрос.');
          setProgressMessage('Ошибка: Превышено время ожидания');
          console.error('Таймаут запроса');
          return;
        }
        
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 10000); // Таймаут 10 секунд на запрос
          
          const progressResponse = await fetch(`${API_BASE_URL}/query/progress/?request_id=${requestId}`, {
            signal: controller.signal
          });
          
          clearTimeout(timeoutId);
          
          if (!progressResponse.ok) {
            consecutiveErrors++;
            console.error(`Ошибка получения прогресса (${consecutiveErrors}/${maxConsecutiveErrors}):`, progressResponse.status);
            
            if (consecutiveErrors >= maxConsecutiveErrors) {
              isPollingActive = false;
              setIsLoading(false);
              setAnswer('Ошибка: Потеряно соединение с сервером. Попробуйте повторить запрос.');
              setProgressMessage('Ошибка: Потеряно соединение с сервером');
              return;
            }
            
            // Увеличиваем интервал при ошибках
            pollInterval = Math.min(pollInterval * 1.5, 5000);
            currentTimeout = setTimeout(pollProgress, pollInterval);
            return;
          }

          const progressData = await progressResponse.json();
          
          // Сбрасываем счетчик ошибок при успешном запросе
          consecutiveErrors = 0;
          pollInterval = 500; // Возвращаем нормальный интервал

          // Обновляем прогресс
          if (progressData.progress !== undefined) {
            setProgress(progressData.progress);
          }
          if (progressData.step !== undefined) {
            setProgressStep(progressData.step);
          }
          if (progressData.message !== undefined) {
            setProgressMessage(progressData.message);
          }
          if (progressData.details !== undefined) {
            setProgressDetails(progressData.details);
          }

          // Если запрос завершен
          if (progressData.status === 'completed' && progressData.result) {
            isPollingActive = false;
            // Сохраняем результаты в состояние (автоматически сохранится в localStorage через хук)
            setAnswer(progressData.result.answer || '');
            setCoordinates(progressData.result.coordinates || []);
            setResultsCount(progressData.result.results_count || 0);
            setHasCoordinates(progressData.result.has_coordinates || false);
            setProgress(100);
            setProgressStep(6);
            setProgressMessage('Запрос выполнен успешно');
            setIsLoading(false);
          } else if (progressData.status === 'completed' && !progressData.result) {
            // Запрос завершен, но результат еще не готов - ждем еще немного
            // Используем короткий интервал для быстрого получения результата
            pollInterval = 500; // Короткий интервал для получения результата
            console.log(`Запрос завершен, ожидаем результат... (интервал: ${pollInterval}ms)`);
            
            // Ограничиваем время ожидания результата (максимум 30 секунд)
            const resultWaitTime = 30 * 1000;
            if (Date.now() - startTime > resultWaitTime) {
              isPollingActive = false;
              setIsLoading(false);
              setAnswer('Ошибка: Результат запроса не получен в течение ожидаемого времени. Попробуйте повторить запрос.');
              setProgressMessage('Ошибка: Результат не получен');
              return;
            }
            
            currentTimeout = setTimeout(pollProgress, pollInterval);
          } else if (progressData.status === 'error') {
            isPollingActive = false;
            setAnswer(`Ошибка: ${progressData.error || 'Неизвестная ошибка'}`);
            setProgressMessage(`Ошибка: ${progressData.error || 'Неизвестная ошибка'}`);
            setIsLoading(false);
          } else {
            // Продолжаем polling
            currentTimeout = setTimeout(pollProgress, pollInterval);
          }
        } catch (pollError) {
          consecutiveErrors++;
          console.error(`Ошибка при получении прогресса (${consecutiveErrors}/${maxConsecutiveErrors}):`, pollError);
          
          if (pollError.name === 'AbortError') {
            console.error('Таймаут запроса прогресса');
          }
          
          if (consecutiveErrors >= maxConsecutiveErrors) {
            isPollingActive = false;
            setIsLoading(false);
            setAnswer('Ошибка: Потеряно соединение с сервером. Попробуйте повторить запрос.');
            setProgressMessage('Ошибка: Потеряно соединение с сервером');
            return;
          }
          
          // Увеличиваем интервал при ошибках
          pollInterval = Math.min(pollInterval * 1.5, 5000);
          currentTimeout = setTimeout(pollProgress, pollInterval);
        }
      };
      
      // Начинаем polling
      progressInterval = setTimeout(pollProgress, pollInterval);
      currentTimeout = progressInterval;

    } catch (error) {
      console.error('Ошибка при обработке запроса:', error);
      if (progressInterval) {
        clearTimeout(progressInterval);
      }
      if (currentTimeout) {
        clearTimeout(currentTimeout);
      }
      setIsLoading(false);
      setAnswer(`Ошибка: ${error.message}`);
      setProgressMessage(`Ошибка: ${error.message}`);
    }
  };

  return (
    <div className="App">
      <div className="container">

        <Group direction="horizontal" className="main-panel-group">
          {/* Левая панель: QueryForm (фиксированный), VideoAvatar и ResultsDisplay (с разделителем) */}
          <Panel defaultSize={60} minSize={40} className="left-panel">
            <div className="left-panel-content">
              {/* Видео и Ответ - с кастомным разделителем, занимают основное пространство */}
              <div ref={containerRef} className="video-results-panel-group" style={{ display: 'flex', flexDirection: 'column', flex: '1 1 auto', minHeight: 0, width: '100%' }}>
                <div 
                  ref={videoPanelRef}
                  className="video-panel"
                  style={{ 
                    flex: answer ? `0 0 ${videoPanelSize}%` : '1 1 100%',
                    minHeight: answer ? '30%' : '0',
                    maxHeight: answer ? '70%' : '100%',
                    overflowY: 'auto',
                    overflowX: 'hidden',
                    display: 'flex',
                    flexDirection: 'column'
                  }}
                >
                  <VideoAvatar answer={answer} userQuery={userQuery} hasCoordinates={hasCoordinates} resultsCount={resultsCount} />
                </div>
            
                {answer && (
                  <>
                    <div 
                      ref={separatorRef}
                      className="panel-resize-handle-vertical custom-vertical-separator"
                      onMouseDown={handleSeparatorMouseDown}
                      style={{
                        cursor: 'ns-resize',
                        height: '8px',
                        width: '100%',
                        flexShrink: 0,
                        userSelect: 'none'
                      }}
                    />
                    <div 
                      ref={resultsPanelRef}
                      className="results-panel"
                      style={{ 
                        flex: `0 0 ${100 - videoPanelSize}%`,
                        minHeight: '30%',
                        maxHeight: '70%',
                        overflow: 'hidden',
                        display: 'flex',
                        flexDirection: 'column'
                      }}
                    >
                      <ResultsDisplay answer={answer} resultsCount={resultsCount} />
                    </div>
                  </>
                )}
              </div>
              
              {/* QueryForm - фиксированный, не изменяемый, внизу */}
              <div className="query-form-fixed">
                <QueryForm 
                  onSubmit={handleQuerySubmit} 
                  isLoading={isLoading}
                  progress={progress}
                  progressStep={progressStep}
                  progressMessage={progressMessage}
                  progressDetails={progressDetails}
                />
              </div>
            </div>
          </Panel>

          {/* Вертикальный разделитель между левой и правой панелями */}
          <Separator className="panel-resize-handle-horizontal" />

          {/* Правая панель: MapDisplay (автоматический размер) */}
          <Panel defaultSize={40} minSize={20} className="right-panel">
            {coordinates.length > 0 ? (
              <MapDisplay coordinates={coordinates} />
            ) : (
              <div className="empty-right-panel">
                <p>Карта появится здесь после получения координат</p>
              </div>
            )}
          </Panel>
        </Group>
      </div>
    </div>
  );
}

export default App;

