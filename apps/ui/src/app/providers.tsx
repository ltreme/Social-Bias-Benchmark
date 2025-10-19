import { MantineProvider } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { QueryClientProvider } from '@tanstack/react-query';
import { RouterProvider } from '@tanstack/react-router';
import { queryClient } from '../lib/queryClient';
import { createRouter } from '@tanstack/react-router';
import { routeTree } from './routes';
import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import '../print.css';

const router = createRouter({ routeTree });

export function AppProviders() {
    return (
        <MantineProvider defaultColorScheme="auto">
            <Notifications position="top-right" limit={3} />
            <QueryClientProvider client={queryClient}>
                <RouterProvider router={router} />
            </QueryClientProvider>
        </MantineProvider>
    );
}
