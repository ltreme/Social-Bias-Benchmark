import axios from 'axios';
import { notifications } from '@mantine/notifications';

export const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8765',
    timeout: 30000,
});

api.interceptors.response.use(
    (r) => r,
    (error) => {
        const msg = error?.response?.data?.detail || error.message;
        notifications.show({ color: 'red', title: 'API Error', message: String(msg) });
        return Promise.reject(error);
    }
);