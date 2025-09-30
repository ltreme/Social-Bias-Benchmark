import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router';
import { PageShell } from '../components/PageShell';
import { DatasetsPage } from '../features/datasets/DatasetsPage';
import { DatasetDetailPage } from '../features/datasets/DatasetDetailPage';
import { RunDetailPage } from '../features/runs/RunDetailPage';
import { ComparePage } from '../features/compare/ComparePage';
import { CasesPage } from '../features/cases/CasesPage';

export const rootRoute = createRootRoute({
    component: () => <PageShell />,
});

const datasetsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: DatasetsPage,
});

const datasetDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/datasets/$datasetId',
    component: DatasetDetailPage,
});


const runDetailRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/runs/$runId',
    component: RunDetailPage,
});

const compareRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/compare',
    component: ComparePage,
});

const casesRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/cases',
    component: CasesPage,
});

export const routeTree = rootRoute.addChildren([datasetsRoute, datasetDetailRoute, runDetailRoute, compareRoute, casesRoute]);
export const router = createRouter({ routeTree });
