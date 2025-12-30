import React, { useState } from 'react';
import './QueryForm.css';

function QueryForm({ onSubmit, isLoading, progress }) {
  const [query, setQuery] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSubmit(query);
      setQuery('');
    }
  };

  return (
    <div className="query-form-container">
      <form onSubmit={handleSubmit} className="query-form">
        <div className="input-group">
          <textarea
            className="query-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Введите ваш вопрос о геологических данных Каспийского моря..."
            rows="2"
            disabled={isLoading}
          />
          <button 
            type="submit" 
            className="submit-button"
            disabled={isLoading || !query.trim()}
          >
            {isLoading ? 'Обработка...' : 'Отправить запрос'}
          </button>
        </div>
      </form>

      {isLoading && (
        <div className="progress-container">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress}%` }}
            >
              <span className="progress-text">{progress}%</span>
            </div>
          </div>
          <p className="progress-status">Обработка запроса...</p>
        </div>
      )}
    </div>
  );
}

export default QueryForm;

