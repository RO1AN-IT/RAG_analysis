import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Group, Panel, Separator } from 'react-resizable-panels';
import './App.css';
import QueryForm from './components/QueryForm';
import ResultsDisplay from './components/ResultsDisplay';
import MapDisplay from './components/MapDisplay';
import VideoAvatar from './components/VideoAvatar';

// API URL - для разработки используйте полный URL, для продакшена - относительный путь
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

function App() {
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [answer, setAnswer] = useState('');
  const [coordinates, setCoordinates] = useState([]);
  const [resultsCount, setResultsCount] = useState(0);
  const [userQuery, setUserQuery] = useState('');
  const [hasCoordinates, setHasCoordinates] = useState(false);
  const [videoPanelSize, setVideoPanelSize] = useState(55);
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
    setVideoPanelSize(newSize);
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
    setAnswer('');
    setCoordinates([]);
    setResultsCount(0);
    setUserQuery(userQuery);
    setHasCoordinates(false);

    try {
      // Симуляция прогресса
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 500);

      const response = await fetch(`${API_BASE_URL}/query/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: userQuery }),
      });

      clearInterval(progressInterval);
      setProgress(100);

      console.log('Ответ получен, status:', response.status, response.statusText);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Ошибка ответа:', response.status, errorText);
        throw new Error(`Ошибка ${response.status}: ${errorText}`);
      }

      const data = await response.json();
      console.log('Данные получены:', {
        hasAnswer: !!data.answer,
        answerLength: data.answer?.length || 0,
        coordinatesCount: data.coordinates?.length || 0,
        resultsCount: data.results_count || 0,
        hasCoordinates: data.has_coordinates || false
      });
      
      setAnswer(data.answer || '');
      setCoordinates(data.coordinates || []);
      setResultsCount(data.results_count || 0);
      setHasCoordinates(data.has_coordinates || false);
      
      console.log('State установлен, answer:', data.answer ? 'есть' : 'нет');
    } catch (error) {
      console.error('Ошибка при обработке запроса:', error);
      setAnswer(`Ошибка: ${error.message}`);
    } finally {
      setIsLoading(false);
      setTimeout(() => setProgress(0), 500);
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
                    overflow: 'hidden',
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

