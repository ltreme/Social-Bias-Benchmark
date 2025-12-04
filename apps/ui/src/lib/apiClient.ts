import axios from 'axios';
import { notifications } from '@mantine/notifications';

// Allow overriding the Axios timeout via env; default to 10 minutes for heavy queries
const DEFAULT_TIMEOUT_MS = 600_000;
const timeoutMs = Number(import.meta.env.VITE_API_TIMEOUT_MS ?? DEFAULT_TIMEOUT_MS);

export const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8765',
    timeout: Number.isFinite(timeoutMs) && timeoutMs > 0 ? timeoutMs : DEFAULT_TIMEOUT_MS,
});

api.interceptors.response.use(
    (r) => r,
    (error) => {
        const msg = error?.response?.data?.detail || error.message;
        notifications.show({ color: 'red', title: 'API Error', message: String(msg) });
        return Promise.reject(error);
    }
);
