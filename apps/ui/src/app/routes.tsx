import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router';
import { PageShell } from '../components/PageShell';
import { DatasetsPage } from '../features/datasets/DatasetsPage';
import { RunsPage } from '../features/runs/RunsPage';
import { ComparePage } from '../features/compare/ComparePage';

export const rootRoute = createRootRoute({
    component: () => <PageShell />,
});

const datasetsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: DatasetsPage,
});

const runsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/runs',
    component: RunsPage,
});

const compareRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/compare',
    component: ComparePage,
});

export const routeTree = rootRoute.addChildren([datasetsRoute, runsRoute, compareRoute]);
export const router = createRouter({ routeTree });