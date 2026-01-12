import { useState } from 'react';

/**
 * Хук для работы с localStorage
 * @param {string} key - ключ в localStorage
 * @param {*} initialValue - начальное значение
 * @returns {[*, function]} - значение и функция для обновления
 */
function useLocalStorage(key, initialValue) {
  // Инициализация состояния с значением из localStorage или начальным значением
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.localStorage.getItem(key);
      return item ? JSON.parse(item) : initialValue;
    } catch (error) {
      console.error(`Ошибка при чтении из localStorage для ключа "${key}":`, error);
      return initialValue;
    }
  });

  // Функция для обновления значения
  const setValue = (value) => {
    try {
      // Позволяем value быть функцией, чтобы иметь такую же логику, как useState
      const valueToStore = value instanceof Function ? value(storedValue) : value;
      setStoredValue(valueToStore);
      window.localStorage.setItem(key, JSON.stringify(valueToStore));
    } catch (error) {
      console.error(`Ошибка при записи в localStorage для ключа "${key}":`, error);
    }
  };

  return [storedValue, setValue];
}

export default useLocalStorage;

