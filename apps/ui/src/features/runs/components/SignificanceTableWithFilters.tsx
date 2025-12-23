import { useState, useEffect } from 'react';
import { Stack, Group, Select, Paper, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import { fetchRunDeltas, type RunDeltas } from '../api';
import { SignificanceTable } from './SignificanceTable';
import { AsyncContent } from '../../../components/AsyncContent';
import { translateCategory } from './GroupComparisonHeatmap';

type SignificanceTableWithFiltersProps = {
  runId: number;
  attribute: string;
  availableCategories?: Array<{ category: string; count: number; mean: number }>;
  traitCategoryOptions: string[];
  initialTraitCategory?: string;
  initialBaseline?: string;
};

export function SignificanceTableWithFilters({
  runId,
  attribute,
  availableCategories = [],
  traitCategoryOptions,
  initialTraitCategory = '__all',
  initialBaseline,
}: SignificanceTableWithFiltersProps) {
  const [traitCategory, setTraitCategory] = useState(initialTraitCategory);
  const [baseline, setBaseline] = useState<string | null>(initialBaseline || null);

  // Reset baseline when attribute changes
  useEffect(() => {
    setBaseline(initialBaseline || null);
  }, [attribute, initialBaseline]);

  // Fetch deltas with current filters
  const { data, isLoading, error } = useQuery<RunDeltas>({
    queryKey: ['run', runId, 'deltas', attribute, traitCategory, baseline],
    queryFn: () => fetchRunDeltas(runId, {
      attribute,
      trait_category: traitCategory === '__all' ? undefined : traitCategory,
      baseline: baseline || undefined,
    }),
    staleTime: 1000 * 60 * 5,
  });

  return (
    <Stack gap="sm">
      <Paper p="sm" withBorder radius="md" bg="gray.0" style={{ backgroundColor: 'var(--mantine-color-gray-0)' }}>
        <Group gap="md" wrap="wrap">
          <div style={{ flex: '1 1 200px' }}>
            <Text size="xs" fw={600} mb={4}>Trait-Kategorie</Text>
            <Select
              data={[
                { value: '__all', label: 'Alle Traits' },
                ...traitCategoryOptions.map(cat => ({
                  value: cat,
                  label: cat.charAt(0).toUpperCase() + cat.slice(1)
                }))
              ]}
              value={traitCategory}
              onChange={(v) => setTraitCategory(v || '__all')}
              size="xs"
            />
          </div>
          <div style={{ flex: '1 1 200px' }}>
            <Text size="xs" fw={600} mb={4}>Baseline-Gruppe</Text>
            <Select
              data={availableCategories.map((c) => ({
                value: c.category,
                label: `${translateCategory(c.category)} (n=${c.count.toLocaleString('de-DE')})`
              }))}
              value={baseline}
              onChange={setBaseline}
              clearable
              placeholder={data?.baseline ? `Auto: ${translateCategory(data.baseline)}` : 'Automatisch'}
              size="xs"
            />
          </div>
        </Group>
      </Paper>

      <AsyncContent isLoading={isLoading} isError={!!error} error={error}>
        <SignificanceTable
          rows={data?.rows || []}
          runId={runId}
          attribute={attribute}
          baseline={(baseline || data?.baseline) ?? undefined}
          traitCategory={traitCategory === '__all' ? undefined : traitCategory}
        />
      </AsyncContent>
    </Stack>
  );
}
