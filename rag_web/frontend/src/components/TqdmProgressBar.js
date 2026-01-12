import React, { useState, useEffect } from 'react';
import './TqdmProgressBar.css';

const STEP_NAMES = {
  1: 'Генерация описания',
  2: 'Поиск в OpenSearch',
  3: 'Проверка признаков',
  4: 'SQL запросы',
  5: 'Формирование ответа',
  6: 'Завершено'
};

function TqdmProgressBar({ progress, step, isVisible }) {
  // Используем пропсы напрямую для начальных значений
  const [displayProgress, setDisplayProgress] = useState(progress || 0);
  const [currentStep, setCurrentStep] = useState(step || 0);

  useEffect(() => {
    // Мгновенное обновление прогресса без анимации
    const targetProgress = progress !== undefined && progress !== null 
      ? Math.min(100, Math.max(0, progress))
      : 0;
    
    if (targetProgress !== displayProgress) {
      setDisplayProgress(targetProgress);
    }
  }, [progress, displayProgress]);

  useEffect(() => {
    if (step !== undefined && step !== null) {
      setCurrentStep(step);
    }
  }, [step]);

  if (!isVisible) {
    return null;
  }

  const stepName = STEP_NAMES[currentStep] || 'Обработка...';
  const progressPercent = Math.round(displayProgress);
  const barWidth = Math.min(100, Math.max(0, displayProgress));

  return (
    <div className="tqdm-progress-container">
      <div className="tqdm-progress-bar-wrapper">
        <div className="tqdm-progress-bar">
          <div 
            className="tqdm-progress-fill"
            style={{ 
              width: `${barWidth}%`,
              minWidth: barWidth > 0 ? '2px' : '0px' // Минимальная ширина для видимости
            }}
          >
            <div className="tqdm-progress-shine"></div>
          </div>
        </div>
        <div className="tqdm-progress-percent-badge">
          {progressPercent}%
        </div>
      </div>
      
      <span className="tqdm-step-name">{stepName}</span>
    </div>
  );
}

export default TqdmProgressBar;

