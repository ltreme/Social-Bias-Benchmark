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
                    <Group gap="xs" align="center" wrap="nowrap">
                        <img
                            src="/equibench-icon-48x48.png"
                            alt="EquiBench logo"
                            width={32}
                            height={32}
                            style={{ display: 'block' }}
                        />
                        <strong>Equi-Bench</strong>
                    </Group>
                </Group>
            </AppShell.Header>
            <AppShell.Navbar p="md">
                <NavLink label="Datasets" component={Link} to="/" active={state.location.pathname === '/'} />
                <NavLink label="Compare" component={Link} to="/compare" active={state.location.pathname === '/compare'} />
                <NavLink label="Cases" component={Link} to="/cases" active={state.location.pathname === '/cases'} />
                <NavLink label="Models" component={Link} to="/models" active={state.location.pathname === '/models'} />
            </AppShell.Navbar>
            <AppShell.Main>
                <Outlet />
            </AppShell.Main>
        </AppShell>
    );
}
