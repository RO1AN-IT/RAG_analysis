import React, { useEffect, useRef, useState, useCallback } from 'react';
import './VideoAvatar.css';

// API URL - для разработки используйте полный URL, для продакшена - относительный путь
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';
const HEYGEN_API_BASE = "https://api.heygen.com";

function VideoAvatar({ answer = '', userQuery = '', hasCoordinates = false, resultsCount = null }) {
  const videoRef = useRef(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [skipVideo, setSkipVideo] = useState(false);
  const [status, setStatus] = useState(null);
  
  // Streaming режим (live)
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingSession, setStreamingSession] = useState(null);
  const [streamingToken, setStreamingToken] = useState(null);
  const [streamingAvatarId, setStreamingAvatarId] = useState(null); // Avatar ID из сервера
  const [videoText, setVideoText] = useState(null); // Текст для озвучивания
  const [showVideo, setShowVideo] = useState(true); // Управление видимостью видео
  const peerConnectionRef = useRef(null);
  const streamingSessionRef = useRef(null);
  const streamingTokenRef = useRef(null);
  const streamingAvatarIdRef = useRef(null); // Ref для avatar_id
  const isStreamingRef = useRef(false); // Ref для отслеживания состояния streaming


  // Получение streaming токена (точно как в heygen_test)
  const getStreamingToken = useCallback(async () => {
    console.log('Получаем access token...');
    const response = await fetch(`${API_BASE_URL}/heygen/streaming-token/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `Token error: ${response.status}`);
    }
    
    console.log('Access token получен');
    
    // Сохраняем avatar_id из ответа (если есть)
    const avatarId = data.data?.avatar_id || data.avatar_id;
    if (avatarId) {
      console.log('Avatar ID получен из сервера:', avatarId);
      setStreamingAvatarId(avatarId);
      streamingAvatarIdRef.current = avatarId;
    }
    
    return data.data.token;
  }, []);

  // Создание streaming сессии (точно как в heygen_test)
  const createStreamingSession = useCallback(async (token) => {
    // Используем avatar_id из сервера или fallback на дефолтный
    const avatarId = streamingAvatarIdRef.current || streamingAvatarId || 'Katya_Chair_Sitting_public';
    
    if (!avatarId) {
      throw new Error('Введите Avatar ID');
    }
    
    const payload = {
      quality: 'medium',
    };
    if (avatarId) {
      payload.avatar_id = avatarId;  // Use avatar_id for interactive avatars
    }
    
    console.log(`Payload: ${JSON.stringify(payload)}`);
    
    const response = await fetch(`${HEYGEN_API_BASE}/v1/streaming.new`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });
    
    const data = await response.json();
    console.log('Session response:', data);
    
    if (!response.ok) {
      const errMsg = data.error?.message || data.message || JSON.stringify(data);
      console.error(`Детали ошибки: ${errMsg}`);
      throw new Error(`Session error: ${response.status} - ${errMsg}`);
    }
    
    console.log(`Сессия создана: ${data.data.session_id}`);
    return data.data;
  }, [streamingAvatarId]);

  // Настройка WebRTC соединения (точно как в heygen_test)
  const startWebRTC = useCallback(async (session, token) => {
    const peerConnection = new RTCPeerConnection({
      iceServers: session.ice_servers || [{ urls: 'stun:stun.l.google.com:19302' }],
    });

    let playStarted = false;
    
    // Обработчик получения треков (точно как в heygen_test)
    peerConnection.ontrack = (event) => {
      console.log(`Получен ${event.track.kind} трек`);
      
      // Set stream to video element (only once) - точно как в heygen_test
      if (event.streams && event.streams[0] && !videoRef.current.srcObject) {
        videoRef.current.srcObject = event.streams[0];
        setHasVideoStream(true); // Скрываем placeholder
      }
      
      // Start playback only once when we have both tracks - точно как в heygen_test
      if (!playStarted && videoRef.current && videoRef.current.srcObject) {
        playStarted = true;
        // Small delay to let both tracks attach
        setTimeout(() => {
          if (videoRef.current && videoRef.current.srcObject) {
            videoRef.current.play().then(() => {
              console.log('Видео воспроизводится');
              if (videoRef.current) {
                videoRef.current.muted = false;
              }
            }).catch(err => {
              console.error('Play error:', err);
              setStatus('Кликните на видео для воспроизведения');
            });
          }
        }, 200);
      }
    };

    // Обработчик ICE кандидатов (точно как в heygen_test)
    peerConnection.onicecandidate = async (event) => {
      if (event.candidate) {
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
      }
    };

    // Обработчик ошибок подключения (опционально, не в heygen_test, но полезно)
    peerConnection.onconnectionstatechange = () => {
      console.log('WebRTC connection state:', peerConnection.connectionState);
    };

    // Set remote SDP - точно как в heygen_test
    await peerConnection.setRemoteDescription(new RTCSessionDescription(session.sdp));
    
    // Create answer - точно как в heygen_test
    const answer = await peerConnection.createAnswer();
    await peerConnection.setLocalDescription(answer);

    // Send answer to server - точно как в heygen_test
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
  }, []);

  // Отправка текста для озвучивания (точно как в heygen_test)
  const speakText = useCallback(async (text, session, token) => {
    if (!session || !token) return;
    
    console.log(`Отправляем текст: "${text.substring(0, 50)}..."`);
    
    // Для Interactive Avatar voice_id может быть undefined - используется голос по умолчанию аватара
    const voiceId = undefined;
    
    const response = await fetch(`${HEYGEN_API_BASE}/v1/streaming.task`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_id: session.session_id,
        text: text.trim(),
        voice_id: voiceId || undefined,
        task_type: 'repeat',
      }),
    });
    
    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error?.message || `Speak error: ${response.status}`);
    }
    
    console.log('Текст отправлен, аватар говорит...');
  }, []);

  // Остановка streaming сессии (точно как в heygen_test)
  const stopStreaming = useCallback(async () => {
    const currentSession = streamingSessionRef.current;
    const currentToken = streamingTokenRef.current;
    
    if (!currentSession) return;
    
    console.log('Закрываем сессию...');
    
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
    } catch (e) {
      console.error(e);
    }
    
    if (peerConnectionRef.current) {
      peerConnectionRef.current.close();
      peerConnectionRef.current = null;
    }
    
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    
    setHasVideoStream(false); // Показываем placeholder снова
    setShowVideo(true);
    setIsStreaming(false);
    isStreamingRef.current = false;
    setStreamingSession(null);
    setStreamingToken(null);
    setStreamingAvatarId(null);
    streamingSessionRef.current = null;
    streamingTokenRef.current = null;
    streamingAvatarIdRef.current = null;
    setStatus('не подключено');
    console.log('Сессия закрыта');
  }, []);

  // Получение текста для видео через backend (подготовка, без запуска сессии)
  const prepareVideoText = useCallback(async () => {
    if (!answer) {
      return null;
    }

    try {
      const backendResponse = await fetch(`${API_BASE_URL}/heygen/prepare-text/`, {
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

  // Запуск streaming сессии (точно как в heygen_test)
  const startSession = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      setStatus('подключение...');
      
      const token = await getStreamingToken();
      setStreamingToken(token);
      streamingTokenRef.current = token;
      
      const session = await createStreamingSession(token);
      setStreamingSession(session);
      streamingSessionRef.current = session;
      
      const peerConnection = await startWebRTC(session, token);
      peerConnectionRef.current = peerConnection;
      
      setIsStreaming(true);
      isStreamingRef.current = true;
      setStatus('подключено');
      setIsLoading(false);
    } catch (err) {
      console.error('Ошибка:', err);
      setError(err.message);
      setStatus('ошибка');
      setIsLoading(false);
    }
  }, [getStreamingToken, createStreamingSession, startWebRTC]);

  // Озвучивание текста (точно как в heygen_test)
  const handleSpeak = useCallback(async () => {
    // Проверяем, что сессия запущена (как в heygen_test)
    if (!isStreamingRef.current || !streamingSessionRef.current || !streamingTokenRef.current) {
      setError('Сначала запустите сессию');
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
      setError('Введите текст для озвучки');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      
      const currentSession = streamingSessionRef.current;
      const currentToken = streamingTokenRef.current;
      
      await speakText(textToSpeak, currentSession, currentToken);
      setIsLoading(false);
    } catch (err) {
      console.error('Ошибка:', err);
      setError(err.message);
      setIsLoading(false);
    }
  }, [videoText, prepareVideoText, speakText]);

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

  // Подготовка текста при изменении answer (без автоматического запуска сессии)
  useEffect(() => {
    if (answer) {
      // Подготавливаем текст, но не запускаем сессию автоматически
      prepareVideoText();
    } else {
      // Сбрасываем состояние, если ответа нет
      setError(null);
      setSkipVideo(false);
      setStatus(null);
      setVideoText(null);
      setHasVideoStream(false); // Сбрасываем состояние видеопотока
      setShowVideo(true); // Показываем видео снова
      
      // Останавливаем streaming, если он был (используем ref для проверки)
      if (isStreamingRef.current) {
        stopStreaming();
      }
    }
    
    // Cleanup: останавливаем streaming при размонтировании
    return () => {
      if (isStreamingRef.current) {
        stopStreaming();
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
  // Можно ли озвучить (сессия запущена и есть ответ для подготовки текста) - как в heygen_test
  const canSpeak = isStreaming && answer && !isLoading && !skipVideo;
  // Можно ли перезапустить сессию (есть ошибка и есть ответ для работы)
  const canRestartSession = error && answer && !skipVideo && !isLoading;

  return (
    <div className="video-avatar-container">
      
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
              title={!isStreaming ? "Сначала запустите сессию" : "Озвучит текст"}
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
              {/* Текст placeholder удален */}
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


