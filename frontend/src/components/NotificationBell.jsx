import { motion, AnimatePresence } from 'framer-motion';
import { Bell, Check, CheckCheck, Trash2, X, Download } from 'lucide-react';
import axios from 'axios';
import { useNotifications } from '../contexts/NotificationContext';

const NotificationBell = () => {
    const {
        notifications,
        unreadCount,
        isOpen,
        setIsOpen,
        markAllRead,
        markSingleRead,
        clearAll,
        getNotificationIcon,
        getNotificationColor
    } = useNotifications();

    const getTimeAgo = (timestamp) => {
        if (!timestamp) return '';
        const seconds = Math.floor(Date.now() / 1000 - timestamp);
        if (seconds < 60) return 'just now';
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        const days = Math.floor(hours / 24);
        return `${days}d ago`;
    };

    return (
        <div className="relative">
            {/* Bell Button */}
            <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => setIsOpen(!isOpen)}
                className="relative p-3 bg-dark-800/80 hover:bg-dark-700 rounded-xl border border-white/10 transition-all group"
            >
                <Bell className={`w-5 h-5 transition-colors ${
                    unreadCount > 0 
                        ? 'text-red-400 group-hover:text-red-300' 
                        : 'text-gray-400 group-hover:text-white'
                }`} />
                
                {/* Unread Badge */}
                {unreadCount > 0 && (
                    <motion.div
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full flex items-center justify-center"
                    >
                        <span className="text-[10px] font-bold text-white">{unreadCount > 9 ? '9+' : unreadCount}</span>
                    </motion.div>
                )}
            </motion.button>

            {/* Notification Panel */}
            <AnimatePresence>
                {isOpen && (
                    <>
                        {/* Backdrop */}
                        <motion.div
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            exit={{ opacity: 0 }}
                            onClick={() => setIsOpen(false)}
                            className="fixed inset-0 z-40"
                        />

                        {/* Dropdown Panel */}
                        <motion.div
                            initial={{ opacity: 0, y: -10, scale: 0.95 }}
                            animate={{ opacity: 1, y: 0, scale: 1 }}
                            exit={{ opacity: 0, y: -10, scale: 0.95 }}
                            className="absolute right-0 mt-2 w-96 max-h-[500px] bg-dark-900/95 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl z-50 overflow-hidden"
                        >
                            {/* Header */}
                            <div className="p-4 border-b border-white/10 flex items-center justify-between">
                                <div className="flex items-center space-x-2">
                                    <Bell className="w-5 h-5 text-gray-400" />
                                    <h3 className="text-white font-bold">Notifications</h3>
                                    {unreadCount > 0 && (
                                        <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs font-bold rounded-full">
                                            {unreadCount} new
                                        </span>
                                    )}
                                </div>
                                <div className="flex items-center space-x-1">
                                    <button
                                        onClick={async () => {
                                            try {
                                                await axios.post('http://localhost:8000/api/notifications/test');
                                                fetchNotifications();
                                            } catch (err) {
                                                console.error("Failed to send test notification", err);
                                            }
                                        }}
                                        className="p-1.5 hover:bg-primary-500/20 text-gray-400 hover:text-primary-400 rounded-lg transition-all"
                                        title="Send test notification"
                                    >
                                        <Bell className="w-4 h-4" />
                                    </button>
                                    {unreadCount > 0 && (
                                        <button
                                            onClick={markAllRead}
                                            className="p-1.5 hover:bg-white/5 text-gray-400 hover:text-white rounded-lg transition-all"
                                            title="Mark all as read"
                                        >
                                            <CheckCheck className="w-4 h-4" />
                                        </button>
                                    )}
                                    {notifications.length > 0 && (
                                        <button
                                            onClick={clearAll}
                                            className="p-1.5 hover:bg-red-500/20 text-gray-400 hover:text-red-400 rounded-lg transition-all"
                                            title="Clear all"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    )}
                                    <button
                                        onClick={() => setIsOpen(false)}
                                        className="p-1.5 hover:bg-white/5 text-gray-400 hover:text-white rounded-lg transition-all"
                                    >
                                        <X className="w-4 h-4" />
                                    </button>
                                </div>
                            </div>

                            {/* Notifications List */}
                            <div className="overflow-y-auto max-h-[400px]">
                                {notifications.length === 0 ? (
                                    <div className="p-8 text-center">
                                        <div className="w-16 h-16 bg-dark-800 rounded-full flex items-center justify-center mx-auto mb-3">
                                            <Bell className="w-8 h-8 text-gray-600" />
                                        </div>
                                        <p className="text-gray-500 text-sm">No notifications yet</p>
                                    </div>
                                ) : (
                                    <div className="divide-y divide-white/5">
                                        {notifications.map((notification) => (
                                            <motion.div
                                                key={notification.id}
                                                initial={{ opacity: 0, x: -20 }}
                                                animate={{ opacity: 1, x: 0 }}
                                                className={`p-4 transition-all cursor-pointer ${
                                                    notification.read 
                                                        ? 'bg-transparent' 
                                                        : getNotificationColor(notification.type)
                                                } hover:bg-white/5`}
                                                onClick={() => markSingleRead(notification.id)}
                                            >
                                                <div className="flex items-start space-x-3">
                                                    <span className="text-xl flex-shrink-0">
                                                        {getNotificationIcon(notification.type)}
                                                    </span>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-start justify-between">
                                                            <p className={`text-sm font-semibold truncate ${
                                                                notification.read ? 'text-gray-400' : 'text-white'
                                                            }`}>
                                                                {notification.title}
                                                            </p>
                                                            {!notification.read && (
                                                                <div className="w-2 h-2 bg-red-500 rounded-full flex-shrink-0 mt-1" />
                                                            )}
                                                        </div>
                                                        <p className="text-xs text-gray-500 mt-1">
                                                            {notification.message}
                                                        </p>
                                                        <div className="flex items-center space-x-2 mt-2">
                                                            <span className="text-[10px] text-gray-600">
                                                                {getTimeAgo(notification.created_at)}
                                                            </span>
                                                            {notification.data?.file_path && (
                                                                <>
                                                                    <span className="text-gray-700">•</span>
                                                                    <button
                                                                        onClick={async (e) => {
                                                                            e.stopPropagation();
                                                                            try {
                                                                                await axios.post('http://localhost:8000/api/open-file', { 
                                                                                    path: notification.data.file_path 
                                                                                });
                                                                            } catch (err) {
                                                                                console.error("Failed to open file", err);
                                                                            }
                                                                        }}
                                                                        className="text-[10px] text-primary-400 hover:text-primary-300 transition-colors flex items-center space-x-1"
                                                                    >
                                                                        <Download className="w-2.5 h-2.5" />
                                                                        <span>Open file</span>
                                                                    </button>
                                                                </>
                                                            )}
                                                        </div>
                                                    </div>
                                                </div>
                                            </motion.div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </motion.div>
                    </>
                )}
            </AnimatePresence>
        </div>
    );
};

export default NotificationBell;
