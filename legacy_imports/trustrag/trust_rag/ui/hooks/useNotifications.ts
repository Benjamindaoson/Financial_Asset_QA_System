"use client";

import { useState, useCallback, useEffect } from 'react';
import { Notification } from '@/types';

let notificationId = 0;

export function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const addNotification = useCallback((notification: Omit<Notification, 'id' | 'timestamp'>) => {
    const id = `notification_${++notificationId}`;
    const fullNotification: Notification = {
      id,
      timestamp: Date.now(),
      duration: 4000, // Default 4 seconds
      ...notification
    };

    setNotifications(prev => [fullNotification, ...prev]);

    // Auto-remove after duration
    if (fullNotification.duration && fullNotification.duration > 0) {
      setTimeout(() => {
        removeNotification(id);
      }, fullNotification.duration);
    }

    return id;
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const clearNotificationsByType = useCallback((type: Notification['type']) => {
    setNotifications(prev => prev.filter(n => n.type !== type));
  }, []);

  // Success notification helper
  const showSuccess = useCallback((title: string, message?: string, duration?: number) => {
    return addNotification({
      type: 'success',
      title,
      message: message || '',
      duration
    });
  }, [addNotification]);

  // Error notification helper
  const showError = useCallback((title: string, message?: string, duration?: number) => {
    return addNotification({
      type: 'error',
      title,
      message: message || '',
      duration: duration || 7000 // Longer for errors
    });
  }, [addNotification]);

  // Warning notification helper
  const showWarning = useCallback((title: string, message?: string, duration?: number) => {
    return addNotification({
      type: 'warning',
      title,
      message: message || '',
      duration
    });
  }, [addNotification]);

  // Info notification helper
  const showInfo = useCallback((title: string, message?: string, duration?: number) => {
    return addNotification({
      type: 'info',
      title,
      message: message || '',
      duration
    });
  }, [addNotification]);

  return {
    notifications,
    addNotification,
    removeNotification,
    clearAllNotifications,
    clearNotificationsByType,
    showSuccess,
    showError,
    showWarning,
    showInfo
  };
}







