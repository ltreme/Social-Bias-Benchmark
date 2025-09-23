import { AppShell, Burger, Group, NavLink } from '@mantine/core';
import { Outlet, Link, useRouterState } from '@tanstack/react-router';
import { useState } from 'react';

export function PageShell() {
    const [opened, setOpened] = useState(false);
    const state = useRouterState();

    return (
        <AppShell
            header={{ height: 56 }}
            navbar={{ width: 260, breakpoint: 'sm', collapsed: { mobile: !opened } }}
            padding="md"
        >
            <AppShell.Header>
                <Group h="100%" px="md">
                    <Burger opened={opened} onClick={() => setOpened((v) => !v)} hiddenFrom="sm" size="sm" />
                    <strong>Benchmark UI</strong>
                </Group>
            </AppShell.Header>
            <AppShell.Navbar p="md">
                <NavLink label="Datasets" component={Link} to="/" active={state.location.pathname === '/'} />
                <NavLink label="Runs" component={Link} to="/runs" active={state.location.pathname === '/runs'} />
                <NavLink label="Compare" component={Link} to="/compare" active={state.location.pathname === '/compare'} />
            </AppShell.Navbar>
            <AppShell.Main>
                <Outlet />
            </AppShell.Main>
        </AppShell>
    );
}