import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router';
import { PageShell } from '../components/PageShell';
import { DatasetsPage } from '../features/datasets/DatasetsPage';
import { DatasetDetailPage } from '../features/datasets/DatasetDetailPage';
import { RunsPage } from '../features/runs/RunsPage';
import { RunDetailPage } from '../features/runs/RunDetailPage';
import { TraitsPage } from '../features/traits/TraitsPage';
import { PersonaBrowserPage } from '../features/personas/PersonaBrowserPage';
import { ModelsPage } from '../features/models/ModelsPage';
import { QueuePage } from '../features/queue/QueuePage';

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

const runsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/runs',
    component: RunsPage,
});

const traitsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/traits',
    component: TraitsPage,
});

const datasetPersonasRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/datasets/$datasetId/personas',
    component: PersonaBrowserPage,
});

const modelsRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/models',
    component: ModelsPage,
});

const queueRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/queue',
    component: QueuePage,
});

export const routeTree = rootRoute.addChildren([datasetsRoute, datasetDetailRoute, runsRoute, runDetailRoute, traitsRoute, datasetPersonasRoute, modelsRoute, queueRoute]);
export const router = createRouter({ routeTree });
