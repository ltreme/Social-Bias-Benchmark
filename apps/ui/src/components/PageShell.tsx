import { AppShell, Group, Tabs } from '@mantine/core';
import { Outlet, Link, useRouterState, useNavigate } from '@tanstack/react-router';
import { IconDatabase, IconList, IconCpu, IconListCheck } from '@tabler/icons-react';

export function PageShell() {
    const state = useRouterState();
    const navigate = useNavigate();
    
    // Determine active tab based on current path
    const getActiveTab = () => {
        const path = state.location.pathname;
        if (path.startsWith('/traits')) return 'traits';
        if (path.startsWith('/models')) return 'models';
        if (path.startsWith('/queue')) return 'queue';
        return 'datasets';
    };

    return (
        <AppShell
            header={{ height: 56 }}
            padding="md"
        >
            <AppShell.Header>
                <Group h="100%" px="md" justify="space-between">
                    <Group gap="xs" align="center" wrap="nowrap" component={Link} to="/" style={{ textDecoration: 'none', color: 'inherit' }}>
                        <img
                            src="/equibench-icon-48x48.png"
                            alt="EquiBench logo"
                            width={32}
                            height={32}
                            style={{ display: 'block' }}
                        />
                        <strong>Equi-Bench</strong>
                    </Group>
                    <Tabs 
                        value={getActiveTab()} 
                        onChange={(value) => {
                            if (value === 'datasets') navigate({ to: '/' });
                            else if (value === 'traits') navigate({ to: '/traits' });
                            else if (value === 'models') navigate({ to: '/models' });
                            else if (value === 'queue') navigate({ to: '/queue' });
                        }}
                        variant="pills"
                    >
                        <Tabs.List>
                            <Tabs.Tab value="datasets" leftSection={<IconDatabase size={16} />}>
                                Datasets
                            </Tabs.Tab>
                            <Tabs.Tab value="traits" leftSection={<IconList size={16} />}>
                                Traits
                            </Tabs.Tab>
                            <Tabs.Tab value="models" leftSection={<IconCpu size={16} />}>
                                Models
                            </Tabs.Tab>
                            <Tabs.Tab value="queue" leftSection={<IconListCheck size={16} />}>
                                Queue
                            </Tabs.Tab>
                        </Tabs.List>
                    </Tabs>
                </Group>
            </AppShell.Header>
            <AppShell.Main>
                <Outlet />
            </AppShell.Main>
        </AppShell>
    );
}
