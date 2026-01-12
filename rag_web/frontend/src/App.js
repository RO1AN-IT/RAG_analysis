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

      // Начинаем polling прогресса
      progressInterval = setInterval(async () => {
        try {
          const progressResponse = await fetch(`${API_BASE_URL}/query/progress/?request_id=${requestId}`);
          
          if (!progressResponse.ok) {
            console.error('Ошибка получения прогресса:', progressResponse.status);
            return;
          }

          const progressData = await progressResponse.json();

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
            clearInterval(progressInterval);
            // Сохраняем результаты в состояние (автоматически сохранится в localStorage через хук)
            setAnswer(progressData.result.answer || '');
            setCoordinates(progressData.result.coordinates || []);
            setResultsCount(progressData.result.results_count || 0);
            setHasCoordinates(progressData.result.has_coordinates || false);
            setProgress(100);
            setProgressStep(6);
            setProgressMessage('Запрос выполнен успешно');
            setIsLoading(false);
          } else if (progressData.status === 'error') {
            clearInterval(progressInterval);
            setAnswer(`Ошибка: ${progressData.error || 'Неизвестная ошибка'}`);
            setProgressMessage(`Ошибка: ${progressData.error || 'Неизвестная ошибка'}`);
            setIsLoading(false);
          }
        } catch (pollError) {
          console.error('Ошибка при получении прогресса:', pollError);
        }
      }, 500); // Polling каждые 500ms

    } catch (error) {
      console.error('Ошибка при обработке запроса:', error);
      if (progressInterval) {
        clearInterval(progressInterval);
      }
      setAnswer(`Ошибка: ${error.message}`);
      setProgressMessage(`Ошибка: ${error.message}`);
      setIsLoading(false);
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

