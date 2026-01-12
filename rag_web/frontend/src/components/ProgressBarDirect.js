import React, { useEffect, useRef } from 'react';
import progressManager from '../utils/progressManager';
import './ProgressBarDirect.css';

function ProgressBarDirect() {
  const containerRef = useRef(null);
  const fillRef = useRef(null);
  const messageRef = useRef(null);
  const debugRef = useRef(null);

  useEffect(() => {
    // Создаем DOM элементы напрямую
    if (!containerRef.current) return;

    const container = containerRef.current;
    
    // Очищаем контейнер
    container.innerHTML = '';

    // Создаем структуру прогресс-бара
    const wrapper = document.createElement('div');
    wrapper.className = 'progress-bar-wrapper-direct';
    
    const track = document.createElement('div');
    track.className = 'progress-bar-track-direct';
    
    const fill = document.createElement('div');
    fill.className = 'progress-bar-fill-direct';
    fill.setAttribute('data-progress', '0');
    
    const text = document.createElement('span');
    text.className = 'progress-bar-text-direct';
    fill.appendChild(text);
    
    track.appendChild(fill);
    
    const message = document.createElement('div');
    message.className = 'progress-bar-message-direct';
    
    const debug = document.createElement('div');
    debug.className = 'progress-bar-debug-direct';
    
    wrapper.appendChild(track);
    wrapper.appendChild(message);
    wrapper.appendChild(debug);
    
    container.appendChild(wrapper);

    // Сохраняем ссылки для прямого обновления
    fillRef.current = fill;
    messageRef.current = message;
    debugRef.current = debug;

    // Подписываемся на обновления
    const unsubscribe = progressManager.subscribe((progress, message, isLoading) => {
      if (!isLoading) {
        container.style.display = 'none';
        return;
      }

      container.style.display = 'block';

      // Прямое обновление DOM
      if (fill) {
        fill.style.width = `${progress}%`;
        fill.setAttribute('data-progress', progress);
        
        if (progress > 5) {
          text.textContent = `${Math.round(progress)}%`;
        } else {
          text.textContent = '';
        }
      }

      if (messageEl) {
        messageEl.textContent = message || 'Обработка запроса...';
      }

      if (debugEl) {
        debugEl.textContent = `Progress: ${progress.toFixed(1)}% | Message: "${message}"`;
      }
    });

    // Первоначальное обновление
    progressManager.updateDOM();

    return () => {
      unsubscribe();
      if (container) {
        container.innerHTML = '';
      }
    };
  }, []);

  return <div ref={containerRef} className="progress-bar-direct-container" style={{ display: 'none' }} />;
}

export default ProgressBarDirect;

