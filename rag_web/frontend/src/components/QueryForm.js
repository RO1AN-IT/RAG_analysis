import React, { useState } from 'react';
import './QueryForm.css';
import TqdmProgressBar from './TqdmProgressBar';

function QueryForm({ 
  onSubmit, 
  isLoading, 
  progress = 0, 
  progressStep = 0,
  progressMessage = '',
  progressDetails = null
}) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSubmit(query.trim());
      setQuery('');
    }
  };

  return (
    <div className="query-form-container">
      <form className="query-form" onSubmit={handleSubmit}>
        <div className="input-group">
          <textarea
            className="query-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите ваш вопрос о геологических данных..."
            disabled={isLoading}
            rows={3}
          />
          {isLoading ? (
            <TqdmProgressBar
              progress={progress}
              step={progressStep}
              isVisible={isLoading}
            />
          ) : (
            <button
              type="submit"
              className="submit-button"
              disabled={!query.trim()}
            >
              Отправить запрос
            </button>
          )}
        </div>
      </form>
    </div>
  );
}

export default QueryForm;
