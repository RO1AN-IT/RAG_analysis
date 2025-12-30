import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './ResultsDisplay.css';

function ResultsDisplay({ answer, resultsCount }) {
  return (
    <div className="results-container">
      <div className="results-header">
        <h2>📋 Ответ преподавателя</h2>
        {resultsCount > 0 && (
          <span className="results-count">Найдено записей: {resultsCount}</span>
        )}
      </div>
      <div className="answer-content">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            // Кастомное форматирование для различных элементов
            p: ({ node, ...props }) => <p className="answer-line" {...props} />,
            h1: ({ node, ...props }) => <h1 className="answer-heading answer-h1" {...props} />,
            h2: ({ node, ...props }) => <h2 className="answer-heading answer-h2" {...props} />,
            h3: ({ node, ...props }) => <h3 className="answer-heading answer-h3" {...props} />,
            ul: ({ node, ...props }) => <ul className="answer-list" {...props} />,
            ol: ({ node, ...props }) => <ol className="answer-list answer-ordered-list" {...props} />,
            li: ({ node, ...props }) => <li className="answer-list-item" {...props} />,
            strong: ({ node, ...props }) => <strong className="answer-strong" {...props} />,
            em: ({ node, ...props }) => <em className="answer-em" {...props} />,
            code: ({ node, inline, ...props }) => 
              inline ? (
                <code className="answer-inline-code" {...props} />
              ) : (
                <code className="answer-code-block" {...props} />
              ),
            blockquote: ({ node, ...props }) => <blockquote className="answer-blockquote" {...props} />,
            a: ({ node, ...props }) => <a className="answer-link" {...props} />,
          }}
        >
          {answer}
        </ReactMarkdown>
      </div>
    </div>
  );
}

export default ResultsDisplay;

