import { Group, Paper, Text, ThemeIcon } from '@mantine/core';
import { IconChartBar } from '@tabler/icons-react';

interface TraitCategory {
  category: string;
  count: number;
  mean: number | null;
  std?: number | null;
}

interface TraitCategorySummaryProps {
  categories: TraitCategory[];
}

export function TraitCategorySummary({ categories }: TraitCategorySummaryProps) {
  if (!categories.length) return null;

  return (
    <Paper p="sm" withBorder radius="md">
      <Group gap="md" align="center">
        <Group gap="xs" wrap="nowrap">
          <ThemeIcon size="sm" radius="md" variant="light" color="grape">
            <IconChartBar size={14} />
          </ThemeIcon>
          <Text size="xs" fw={600} c="dimmed">Trait-Kategorien</Text>
        </Group>
        
        <Group gap="lg">
          {categories.map((cat) => (
            <Group key={cat.category} gap={6} wrap="nowrap">
              <Text size="sm" fw={600}>{cat.category}</Text>
              <Text size="xs" c="dimmed">
                μ={cat.mean?.toFixed(2)} · n={cat.count.toLocaleString('de-DE')}
                {typeof cat.std === 'number' && ` · σ=${cat.std.toFixed(2)}`}
              </Text>
            </Group>
          ))}
        </Group>
      </Group>
    </Paper>
  );
}
