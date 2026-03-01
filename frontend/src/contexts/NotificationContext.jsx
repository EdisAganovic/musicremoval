import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const NotificationContext = createContext();

export const useNotifications = () => {
    const context = useContext(NotificationContext);
    if (!context) {
        throw new Error('useNotifications must be used within NotificationProvider');
    }
    return context;
};

export const NotificationProvider = ({ children }) => {
    const [notifications, setNotifications] = useState([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [isOpen, setIsOpen] = useState(false);

    // Fetch notifications
    const fetchNotifications = useCallback(async () => {
        try {
            const response = await axios.get('http://localhost:8000/api/notifications');
            setNotifications(response.data.notifications || []);
            setUnreadCount(response.data.unread_count || 0);
        } catch (err) {
            console.error("Failed to fetch notifications", err);
        }
    }, []);

    // Initial fetch and polling
    useEffect(() => {
        fetchNotifications();
        const interval = setInterval(fetchNotifications, 3000);
        return () => clearInterval(interval);
    }, [fetchNotifications]);

    // Mark all as read
    const markAllRead = async () => {
        try {
            await axios.post('http://localhost:8000/api/notifications/mark-read');
            setUnreadCount(0);
            setNotifications(prev => prev.map(n => ({ ...n, read: true })));
        } catch (err) {
            console.error("Failed to mark notifications as read", err);
        }
    };

    // Mark single as read
    const markSingleRead = async (id) => {
        try {
            await axios.post('http://localhost:8000/api/notifications/mark-single-read', { id });
            setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
            setUnreadCount(prev => Math.max(0, prev - 1));
        } catch (err) {
            console.error("Failed to mark notification as read", err);
        }
    };

    // Clear all notifications
    const clearAll = async () => {
        try {
            await axios.post('http://localhost:8000/api/notifications/clear');
            setNotifications([]);
            setUnreadCount(0);
        } catch (err) {
            console.error("Failed to clear notifications", err);
        }
    };

    // Get notification icon based on type
    const getNotificationIcon = (type) => {
        switch (type) {
            case 'success': return '✅';
            case 'error': return '❌';
            case 'warning': return '⚠️';
            default: return 'ℹ️';
        }
    };

    // Get notification color based on type
    const getNotificationColor = (type) => {
        switch (type) {
            case 'success': return 'border-emerald-500/30 bg-emerald-500/5';
            case 'error': return 'border-red-500/30 bg-red-500/5';
            case 'warning': return 'border-amber-500/30 bg-amber-500/5';
            default: return 'border-blue-500/30 bg-blue-500/5';
        }
    };

    return (
        <NotificationContext.Provider value={{
            notifications,
            unreadCount,
            isOpen,
            setIsOpen,
            fetchNotifications,
            markAllRead,
            markSingleRead,
            clearAll,
            getNotificationIcon,
            getNotificationColor
        }}>
            {children}
        </NotificationContext.Provider>
    );
};
