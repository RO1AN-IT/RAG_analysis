import React, { useState, useRef, useEffect } from 'react';
import Draggable from 'react-draggable';
import { Resizable } from 'react-resizable';
import 'react-resizable/css/styles.css';
import './DraggableResizable.css';

function DraggableResizable({ 
  children, 
  defaultPosition = { x: 0, y: 0 },
  defaultSize = { width: 'auto', height: 'auto' },
  minWidth = 300,
  minHeight = 200,
  isResizable = true,
  isDraggable = true,
  className = ''
}) {
  const [position, setPosition] = useState(defaultPosition);
  const [size, setSize] = useState(defaultSize);
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const wrapperRef = useRef(null);
  const containerRef = useRef(null);

  const handleDrag = (e, data) => {
    setPosition({ x: data.x, y: data.y });
  };

  const handleDragStart = () => {
    setIsDragging(true);
  };

  const handleDragStop = () => {
    setIsDragging(false);
  };

  const handleResize = (e, { size }) => {
    setSize({ width: size.width, height: size.height });
  };

  const handleResizeStart = () => {
    setIsResizing(true);
  };

  const handleResizeStop = () => {
    setIsResizing(false);
  };

  // Инициализация размера для '100%' ширины
  useEffect(() => {
    if (defaultSize.width === '100%' && (size.width === '100%' || size.width === defaultSize.width) && containerRef.current) {
      const parent = containerRef.current.parentElement;
      if (parent) {
        const parentWidth = parent.getBoundingClientRect().width;
        if (parentWidth && parentWidth > 0) {
          setSize(prev => ({ ...prev, width: parentWidth }));
        }
      }
    }
  }, [defaultSize.width]);

  // Нормализуем размеры
  const numericWidth = typeof size.width === 'number' ? size.width : 
                      (defaultSize.width === '100%' ? 
                        (containerRef.current?.parentElement?.getBoundingClientRect().width || 500) : 
                        (typeof defaultSize.width === 'number' ? defaultSize.width : 500));
  
  const numericHeight = typeof size.height === 'number' ? size.height : 
                       (typeof defaultSize.height === 'number' ? defaultSize.height : 400);

  if (!isDraggable && !isResizable) {
    return (
      <div 
        className={`draggable-resizable-content ${className}`}
        style={{
          width: defaultSize.width === '100%' ? '100%' : `${numericWidth}px`,
          height: `${numericHeight}px`,
        }}
      >
        {children}
      </div>
    );
  }

  let resizableContent;

  // Обертка для изменения размера
  if (isResizable) {
    const contentDiv = (
      <div 
        className={`draggable-resizable-content ${isResizing ? 'resizing' : ''} ${className}`}
        style={{
          width: '100%',
          height: '100%',
          overflow: 'auto',
        }}
      >
        {children}
      </div>
    );

    resizableContent = (
      <div 
        ref={containerRef}
        className="resizable-wrapper" 
        style={{ width: defaultSize.width === '100%' && size.width !== 'auto' && typeof size.width !== 'number' ? '100%' : `${numericWidth}px` }}
      >
        <Resizable
          width={numericWidth}
          height={numericHeight}
          minConstraints={[minWidth, minHeight]}
          onResize={handleResize}
          onResizeStart={handleResizeStart}
          onResizeStop={handleResizeStop}
          handle={
            <span
              className="react-resizable-handle react-resizable-handle-se"
              onClick={(e) => {
                e.stopPropagation();
              }}
            />
          }
        >
          <div 
            style={{ 
              width: `${numericWidth}px`, 
              height: `${numericHeight}px`,
              position: 'relative'
            }}
          >
            {contentDiv}
          </div>
        </Resizable>
      </div>
    );
  } else {
    resizableContent = (
      <div 
        className={`draggable-resizable-content ${className}`}
        style={{
          width: defaultSize.width === '100%' ? '100%' : `${numericWidth}px`,
          height: `${numericHeight}px`,
        }}
      >
        {children}
      </div>
    );
  }

  // Обертка для перетаскивания (только если включено)
  if (isDraggable) {
    return (
      <Draggable
        position={position}
        onDrag={handleDrag}
        onStart={handleDragStart}
        onStop={handleDragStop}
        handle=".draggable-handle"
      >
        <div ref={wrapperRef} className="draggable-resizable-wrapper">
          <div className="draggable-handle">
            <span className="drag-icon">⋮⋮</span>
            <span className="drag-label">Перетащить</span>
          </div>
          {resizableContent}
        </div>
      </Draggable>
    );
  }

  return resizableContent;
}

export default DraggableResizable;
