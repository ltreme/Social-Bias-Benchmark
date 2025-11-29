import { Alert, Center, Loader, Text } from '@mantine/core';
import type { ReactNode } from 'react';

type Props = {
  isLoading?: boolean;
  isError?: boolean;
  error?: unknown;
  children: ReactNode;
  loadingLabel?: string;
};

export function AsyncContent({ isLoading, isError, error, children, loadingLabel = 'Laden…' }: Props) {
  if (isLoading) {
    return (
      <Center style={{ minHeight: 80 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Loader size="sm" />
          <Text size="sm" c="dimmed">{loadingLabel}</Text>
        </div>
      </Center>
    );
  }
  if (isError) {
    const msg = (error as any)?.message ?? String(error ?? 'Fehler');
    return <Alert color="red" title="Fehler">{msg}</Alert>;
  }
  return <>{children}</>;
}

