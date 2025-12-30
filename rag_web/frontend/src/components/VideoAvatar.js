import React, { useEffect, useRef, useState, useCallback } from 'react';
import './VideoAvatar.css';

// API URL - для разработки используйте полный URL, для продакшена - относительный путь
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';
const HEYGEN_API_BASE = "https://api.heygen.com";

function VideoAvatar({ answer = '', userQuery = '', hasCoordinates = false, resultsCount = null }) {
  const videoRef = useRef(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [skipVideo, setSkipVideo] = useState(false);
  const [videoId, setVideoId] = useState(null);
  const [status, setStatus] = useState(null);
  const pollingIntervalRef = useRef(null);
  
  // Streaming режим (live)
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingSession, setStreamingSession] = useState(null);
  const [streamingToken, setStreamingToken] = useState(null);
  const [videoText, setVideoText] = useState(null); // Текст для озвучивания
  const [showVideo, setShowVideo] = useState(true); // Управление видимостью видео
  const peerConnectionRef = useRef(null);
  const streamingSessionRef = useRef(null);
  const streamingTokenRef = useRef(null);
  const isStreamingRef = useRef(false); // Ref для отслеживания состояния streaming

  // Функция для проверки статуса видео (polling) - как в heygen_test
  const checkVideoStatus = useCallback(async (id) => {
    try {
      const response = await fetch(`${API_BASE_URL}/heygen/status/?video_id=${id}`);
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.error || 'Ошибка проверки статуса');
      }
      
      setStatus(data.status || 'pending');
      
      // Обработка ошибки (как в heygen_test)
      if (data.status === 'failed') {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        const errMsg = data.raw?.data?.error?.message || data.raw?.data?.error?.detail || 'Генерация не удалась';
        setError(errMsg);
        setIsLoading(false);
        setStatus('Ошибка генерации');
        return true; // Процесс завершен с ошибкой
      }
      
      // Видео готово
      if (data.video_url) {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
          pollingIntervalRef.current = null;
        }
        setVideoUrl(data.video_url);
        setIsLoading(false);
        setStatus('Готово!');
        return true; // Видео готово
      }
      
      return false; // Продолжаем polling
    } catch (err) {
      console.error('Ошибка проверки статуса:', err);
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
      setError(err.message);
      setIsLoading(false);
      setStatus('');
      return true; // Остановка polling при ошибке
    }
  }, []);

  // Получение streaming токена (улучшенная версия)
  const getStreamingToken = useCallback(async () => {
    try {
      console.log('Запрос streaming токена...');
      const response = await fetch(`${API_BASE_URL}/heygen/streaming-token/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        const errorMsg = data.error || data.details || `Ошибка получения токена: ${response.status}`;
        console.error('Ошибка получения токена:', errorMsg);
        throw new Error(errorMsg);
      }
      
      // Проверяем структуру ответа
      const token = data.data?.token || data.token;
      if (!token) {
        console.error('Токен не найден в ответе:', data);
        throw new Error('Токен не найден в ответе сервера');
      }
      
      console.log('Streaming токен получен');
      return token;
    } catch (err) {
      console.error('Ошибка получения streaming токена:', err);
      throw err;
    }
  }, []);

  // Создание streaming сессии (улучшенная версия)
  const createStreamingSession = useCallback(async (token) => {
    if (!token) {
      throw new Error('Токен не предоставлен');
    }
    
    const avatarId = 'Katya_Chair_Sitting_public'; // Дефолтный Interactive Avatar ID (для streaming нужен Interactive Avatar)
    const payload = {
      quality: 'medium',
      avatar_id: avatarId,
    };
    
    console.log('Создание streaming сессии с payload:', payload);
    
    try {
      const response = await fetch(`${HEYGEN_API_BASE}/v1/streaming.new`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });
      
      const data = await response.json();
      console.log('Ответ создания сессии:', data);
      
      if (!response.ok) {
        const errorMsg = data.error?.message || data.message || data.error || `Ошибка создания сессии: ${response.status}`;
        console.error('Ошибка создания сессии:', errorMsg);
        throw new Error(errorMsg);
      }
      
      // Проверяем структуру ответа
      const sessionData = data.data || data;
      if (!sessionData.session_id) {
        console.error('session_id не найден в ответе:', data);
        throw new Error('session_id не найден в ответе сервера');
      }
      
      console.log('Сессия создана:', sessionData.session_id);
      return sessionData;
    } catch (err) {
      console.error('Ошибка в createStreamingSession:', err);
      throw err;
    }
  }, []);

  // Настройка WebRTC соединения (улучшенная версия из heygen_test)
  const startWebRTC = useCallback(async (session, token) => {
    const peerConnection = new RTCPeerConnection({
      iceServers: session.ice_servers || [{ urls: 'stun:stun.l.google.com:19302' }],
    });

    let playStarted = false;
    
    // Обработчик получения треков (точно как в heygen_test)
    peerConnection.ontrack = (event) => {
      console.log(`Получен ${event.track.kind} трек`);
      
      // Устанавливаем поток в video элемент (только один раз) - точно как в heygen_test
      if (event.streams && event.streams[0] && videoRef.current) {
        // Устанавливаем srcObject (даже если уже установлен, обновляем для надежности)
        if (!videoRef.current.srcObject) {
          console.log('Установка srcObject для видео элемента...');
          videoRef.current.srcObject = event.streams[0];
          console.log('srcObject установлен, поток:', event.streams[0]);
          console.log('Активные треки в потоке:', event.streams[0].getTracks().map(t => ({ kind: t.kind, enabled: t.enabled, readyState: t.readyState })));
        }
        // Скрываем placeholder при получении потока (всегда обновляем состояние)
        setHasVideoStream(true);
        console.log('hasVideoStream установлен в true');
      }
      
      // Запускаем воспроизведение только один раз, когда есть оба трека (точно как в heygen_test)
      if (!playStarted && videoRef.current && videoRef.current.srcObject) {
        playStarted = true;
        console.log('Оба трека получены, запуск воспроизведения...');
        // Небольшая задержка, чтобы оба трека успели подключиться
        setTimeout(() => {
          if (videoRef.current && videoRef.current.srcObject) {
            console.log('Попытка запустить воспроизведение...');
            videoRef.current.play().then(() => {
              console.log('Видео воспроизводится успешно');
              if (videoRef.current) {
                videoRef.current.muted = false;
                console.log('Звук включен, video.readyState:', videoRef.current.readyState);
              }
            }).catch(err => {
              console.error('Ошибка воспроизведения:', err);
              setStatus('Кликните на видео для воспроизведения');
              setError('Кликните на видео для воспроизведения (автозапуск заблокирован браузером)');
            });
          } else {
            console.error('videoRef.current или srcObject отсутствует при попытке воспроизведения');
          }
        }, 200);
      }
    };

    // Обработчик ICE кандидатов
    peerConnection.onicecandidate = async (event) => {
      if (event.candidate && session.session_id) {
        try {
          await fetch(`${HEYGEN_API_BASE}/v1/streaming.ice`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              session_id: session.session_id,
              candidate: event.candidate,
            }),
          });
        } catch (err) {
          console.error('Ошибка отправки ICE кандидата:', err);
        }
      }
    };

    // Обработчик ошибок подключения
    peerConnection.onconnectionstatechange = () => {
      console.log('WebRTC connection state:', peerConnection.connectionState);
      if (peerConnection.connectionState === 'failed') {
        setError('Ошибка подключения WebRTC');
        setStatus('Ошибка подключения');
      }
    };

    try {
      // Устанавливаем remote SDP
      await peerConnection.setRemoteDescription(new RTCSessionDescription(session.sdp));
      
      // Создаем answer
      const answer = await peerConnection.createAnswer();
      await peerConnection.setLocalDescription(answer);

      // Отправляем answer на сервер
      await fetch(`${HEYGEN_API_BASE}/v1/streaming.start`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: session.session_id,
          sdp: answer,
        }),
      });

      console.log('WebRTC подключено!');
      return peerConnection;
    } catch (err) {
      console.error('Ошибка настройки WebRTC:', err);
      throw err;
    }
  }, []);

  // Отправка текста для озвучивания (улучшенная версия)
  const speakText = useCallback(async (text, session, token) => {
    if (!text || !text.trim()) {
      throw new Error('Текст для озвучивания пуст');
    }
    
    if (!session || !session.session_id) {
      throw new Error('Сессия не создана');
    }
    
    // Для Interactive Avatar voice_id может быть undefined - используется голос по умолчанию аватара
    const voiceId = undefined; // Interactive Avatar использует свой голос по умолчанию
    console.log(`Отправка текста для озвучивания (${text.length} символов})`);
    
    try {
      const response = await fetch(`${HEYGEN_API_BASE}/v1/streaming.task`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: session.session_id,
          text: text.trim(),
          voice_id: voiceId || undefined, // Опционально - если undefined, используется голос по умолчанию аватара
          task_type: 'repeat',
        }),
      });

      if (!response.ok) {
        const err = await response.json();
        const errorMsg = err.error?.message || err.message || `Ошибка озвучивания: ${response.status}`;
        console.error('Ошибка отправки текста:', errorMsg);
        throw new Error(errorMsg);
      }
      
      console.log('Текст успешно отправлен для озвучивания');
    } catch (err) {
      console.error('Ошибка в speakText:', err);
      throw err;
    }
  }, []);

  // Остановка streaming сессии (улучшенная версия)
  // Используем refs для доступа к текущим значениям без зависимостей
  const stopStreaming = useCallback(async () => {
    console.log('Остановка streaming сессии...');
    
    // Закрываем WebRTC соединение
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    
    // Останавливаем сессию на сервере (используем refs для получения текущих значений)
    const currentSession = streamingSessionRef.current;
    const currentToken = streamingTokenRef.current;
    
    if (currentSession && currentSession.session_id && currentToken) {
      try {
        await fetch(`${HEYGEN_API_BASE}/v1/streaming.stop`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${currentToken}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            session_id: currentSession.session_id,
          }),
        });
        console.log('Сессия остановлена на сервере');
      } catch (e) {
        console.error('Ошибка остановки сессии:', e);
      }
    }
    
    // Очищаем видео элемент
    if (videoRef.current) {
      videoRef.current.srcObject = null;
      videoRef.current.load(); // Сбрасываем состояние видео элемента
    }
    
    // Сбрасываем состояние и refs
    setIsStreaming(false);
    isStreamingRef.current = false;
    setHasVideoStream(false); // Показываем placeholder снова
    setShowVideo(true); // Показываем видео снова при закрытии сессии
    setStreamingSession(null);
    setStreamingToken(null);
    streamingSessionRef.current = null;
    streamingTokenRef.current = null;
    setStatus('не подключено');
    console.log('Streaming сессия закрыта');
  }, []);

  // Получение текста для видео через backend (подготовка, без запуска сессии)
  const prepareVideoText = useCallback(async () => {
    if (!answer) {
      return null;
    }

    try {
      const backendResponse = await fetch(`${API_BASE_URL}/heygen/generate/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          answer: answer,
          user_query: userQuery,
          has_coordinates: hasCoordinates,
          results_count: resultsCount,
        }),
      });

      const backendData = await backendResponse.json();
      
      if (backendData.skip_video) {
        setSkipVideo(true);
        return null;
      }
      
      setSkipVideo(false);
      
      if (!backendResponse.ok) {
        throw new Error(backendData.error || 'Ошибка генерации текста для видео');
      }

      // Получаем текст из ответа (backend генерирует его через GigaChat)
      const text = backendData.video_text || answer;
      setVideoText(text);
      return text;
    } catch (backendErr) {
      console.error('Ошибка подготовки текста для видео:', backendErr);
      setError(backendErr.message || 'Не удалось подготовить текст для видео. Проверьте настройки API.');
      return null;
    }
  }, [answer, userQuery, hasCoordinates, resultsCount]);

  // Запуск streaming сессии (как в heygen_test - только создание сессии и подключение, без озвучивания)
  const startSession = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      setStatus('подключение...');
      
      // Получаем токен
      console.log('Получение access token...');
      const token = await getStreamingToken();
      setStreamingToken(token);
      streamingTokenRef.current = token;
      console.log('Access token получен');
      
      // Создаем сессию
      console.log('Создание streaming сессии...');
      setStatus('Создание сессии...');
      const session = await createStreamingSession(token);
      setStreamingSession(session);
      streamingSessionRef.current = session;
      console.log('Сессия создана:', session.session_id);
      
      // Настраиваем WebRTC
      console.log('Настройка WebRTC соединения...');
      setStatus('Установка соединения...');
      const peerConnection = await startWebRTC(session, token);
      peerConnectionRef.current = peerConnection;
      console.log('WebRTC подключено');
      
      setIsStreaming(true);
      isStreamingRef.current = true;
      setStatus('подключено');
      setIsLoading(false);
    } catch (err) {
      console.error('Ошибка запуска сессии:', err);
      const errorMessage = err.message || 'Ошибка запуска сессии';
      setError(errorMessage);
      setIsLoading(false);
      setStatus('ошибка');
      
      // Останавливаем streaming при ошибке
      try {
        await stopStreaming();
      } catch (stopErr) {
        console.error('Ошибка при остановке streaming:', stopErr);
      }
    }
  }, [getStreamingToken, createStreamingSession, startWebRTC, stopStreaming]);

  // Озвучивание текста (как в heygen_test - отдельная функция)
  const handleSpeak = useCallback(async () => {
    if (!isStreaming) {
      setError('Сессия не запущена');
      return;
    }

    // Подготавливаем текст для видео (если еще не подготовлен)
    let textToSpeak = videoText;
    if (!textToSpeak) {
      textToSpeak = await prepareVideoText();
      if (!textToSpeak) {
        setError('Не удалось подготовить текст для озвучивания');
        return;
      }
    }

    if (!textToSpeak || !textToSpeak.trim()) {
      setError('Текст для озвучивания пуст');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      setStatus('Озвучивание текста...');
      
      const currentSession = streamingSessionRef.current;
      const currentToken = streamingTokenRef.current;
      
      if (!currentSession || !currentToken) {
        throw new Error('Сессия не активна');
      }
      
      // Небольшая задержка перед отправкой текста
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Отправляем текст для озвучивания
      console.log('Отправка текста для озвучивания...');
      await speakText(textToSpeak, currentSession, currentToken);
      console.log('Текст отправлен, аватар говорит...');
      
      setStatus('Готово! Аватар говорит...');
      setIsLoading(false);
    } catch (err) {
      console.error('Ошибка озвучивания:', err);
      const errorMessage = err.message || 'Ошибка озвучивания';
      setError(errorMessage);
      setStatus('ошибка озвучивания');
      setIsLoading(false);
    }
  }, [isStreaming, videoText, prepareVideoText, speakText]);

  // Обновленный stopStreaming с обновлением состояния кнопок
  const handleStopSession = useCallback(async () => {
    await stopStreaming();
    setVideoText(null); // Сбрасываем текст
    setSkipVideo(false);
  }, [stopStreaming]);

  // Перезапуск сессии (при ошибках)
  const handleRestartSession = useCallback(async () => {
    console.log('Перезапуск сессии...');
    try {
      // Сначала останавливаем текущую сессию, если она была
      if (isStreamingRef.current) {
        await stopStreaming();
        // Небольшая задержка перед перезапуском
        await new Promise(resolve => setTimeout(resolve, 500));
      }
      // Очищаем ошибку
      setError(null);
      setStatus('Перезапуск сессии...');
      // Запускаем новую сессию
      await startSession();
    } catch (err) {
      console.error('Ошибка при перезапуске сессии:', err);
      setError(`Ошибка перезапуска: ${err.message}`);
    }
  }, [stopStreaming, startSession]);

  // Переключение видимости видео
  const handleToggleVideo = useCallback(() => {
    setShowVideo(prev => !prev);
  }, []);

  // Подготовка текста при изменении answer (но не запуск сессии)
  useEffect(() => {
    if (answer) {
      prepareVideoText();
    } else {
      // Сбрасываем состояние, если ответа нет
      setVideoUrl(null);
      setError(null);
      setSkipVideo(false);
      setVideoId(null);
      setStatus(null);
      setVideoText(null);
      setHasVideoStream(false); // Сбрасываем состояние видеопотока
      setShowVideo(true); // Показываем видео снова
      
      // Останавливаем streaming, если он был (используем ref для проверки)
      if (isStreamingRef.current) {
        stopStreaming();
      }
      
      // Останавливаем polling при сбросе
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }
    
    // Cleanup: останавливаем streaming и polling при размонтировании
    return () => {
      if (isStreamingRef.current) {
        stopStreaming();
      }
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    };
  }, [answer, prepareVideoText, stopStreaming]);

  // Состояние для отслеживания, есть ли видеопоток (для скрытия placeholder)
  const [hasVideoStream, setHasVideoStream] = useState(false);
  
  // Определяем, показывать ли placeholder (показываем, если нет видеопотока)
  const showPlaceholder = !hasVideoStream;
  
  // Определяем класс статуса
  const getStatusClass = () => {
    if (error) return 'error';
    if (isStreaming) return 'connected';
    if (isLoading) return 'pending';
    return '';
  };

  // Проверяем, можно ли начать сессию (нет активной сессии и есть ответ)
  const canStartSession = answer && !isStreaming && !isLoading && !skipVideo;
  // Можно ли закрыть сессию (есть активная сессия)
  const canStopSession = isStreaming;
  // Можно ли озвучить (есть активная сессия и есть текст)
  const canSpeak = isStreaming && videoText && !isLoading;
  // Можно ли перезапустить сессию (есть ошибка и есть ответ для работы)
  const canRestartSession = error && answer && !skipVideo && !isLoading;

  return (
    <div className="video-avatar-container">
      <div className="video-header">
        <h3>🎥 Видео-аватар HeyGen</h3>
      </div>
      
      {/* Статус */}
      {status && (
        <div className={`status ${getStatusClass()}`} id="status">
          Статус: {status}
        </div>
      )}
      
      {/* Информация о пропуске видео */}
      {skipVideo && (
        <div className="status">
          Видео не генерируется, так как данные не найдены
        </div>
      )}
      
      {/* Кнопки управления (как в heygen_test) */}
      {answer && !skipVideo && (
        <div className="controls">
          <div className="controls-row">
            <button 
              id="btn-start" 
              className="btn-primary" 
              onClick={startSession}
              disabled={!canStartSession}
            >
              ▶ Начать сессию
            </button>
            <button 
              id="btn-stop" 
              className="btn-danger" 
              onClick={handleStopSession}
              disabled={!canStopSession}
            >
              ⏹ Закрыть сессию
            </button>
            {canRestartSession && (
              <button 
                id="btn-restart" 
                className="btn-secondary" 
                onClick={handleRestartSession}
                disabled={isLoading}
              >
                🔄 Перезапустить сессию
              </button>
            )}
          </div>
          <div className="controls-row">
            <button 
              id="btn-speak" 
              className="btn-secondary" 
              onClick={handleSpeak}
              disabled={!canSpeak}
            >
              🗣 Озвучить
            </button>
            {isStreaming && (
              <button 
                id="btn-toggle-video" 
                className="btn-secondary" 
                onClick={handleToggleVideo}
              >
                {showVideo ? '👁️ Скрыть видео' : '👁️‍🗨️ Показать видео'}
              </button>
            )}
          </div>
        </div>
      )}
      
      {/* Ошибка */}
      {error && (
        <div className="error">
          {error}
        </div>
      )}
      
      {/* Контейнер для видео с wrapper как в heygen_test */}
      <div id="video-container" className="video-container" style={{ display: showVideo ? 'block' : 'none' }}>
        <div className="video-wrapper">
          {/* Streaming видео (live) - всегда в DOM, как в heygen_test */}
          <video
            ref={videoRef}
            id="avatar-video"
            autoPlay
            playsInline
            muted={true}
            onClick={() => {
              // Разблокировка звука по клику (если браузер заблокировал автозапуск)
              if (videoRef.current && videoRef.current.muted) {
                videoRef.current.muted = false;
                setStatus('Звук включен');
              }
            }}
            onError={(e) => {
              console.error('Ошибка воспроизведения видео:', e);
              setError('Ошибка воспроизведения видео');
              setStatus('Ошибка');
            }}
            onLoadedMetadata={() => {
              console.log('Метаданные видео загружены');
              // Убеждаемся, что placeholder скрыт при загрузке видео
              if (videoRef.current && videoRef.current.srcObject) {
                setHasVideoStream(true);
              }
            }}
            onCanPlay={() => {
              console.log('Видео готово к воспроизведению');
              // Дополнительная проверка - убеждаемся, что placeholder скрыт
              if (videoRef.current && videoRef.current.srcObject) {
                setHasVideoStream(true);
                console.log('onCanPlay: srcObject установлен, hasVideoStream = true');
              }
            }}
            onPlaying={() => {
              console.log('Видео воспроизводится (onPlaying event)');
              if (videoRef.current && videoRef.current.srcObject) {
                setHasVideoStream(true);
              }
            }}
          >
            Ваш браузер не поддерживает видео.
          </video>
          
          {/* Placeholder как в heygen_test - скрывается при получении видеопотока */}
          {showPlaceholder && (
            <div className="video-placeholder" id="placeholder">
              {answer && !skipVideo 
                ? 'Нажмите "Начать сессию" для запуска аватара' 
                : 'Ожидание данных для генерации видео'}
            </div>
          )}
        </div>
      </div>
      
      {/* Сообщение, когда видео скрыто */}
      {!showVideo && isStreaming && (
        <div className="status" style={{ marginTop: '1rem' }}>
          Видео скрыто. Нажмите "Показать видео" для отображения.
        </div>
      )}
    </div>
  );
}

export default VideoAvatar;


