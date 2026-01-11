import { Paper, Text, Title, Group, ThemeIcon, Tooltip, ActionIcon, Badge, Progress, Stack } from '@mantine/core';
import { IconGridDots, IconInfoCircle, IconArrowUp, IconArrowDown } from '@tabler/icons-react';
import { useThemeColors } from '../../../lib/useThemeColors';
import { translateCategory } from '../utils/kruskalWallisHelpers';

type DeltaRow = {
  category: string;
  delta?: number;
  mean?: number;
  count?: number;
  p_value?: number;
  significant?: boolean;
};

type ComparisonCardProps = {
  /** Delta rows for the current attribute */
  rows: DeltaRow[];
  /** Current attribute display label */
  attributeLabel: string;
  /** Baseline category */
  baseline?: string;
};

function isSignificant(row: DeltaRow): boolean {
  if (row.significant !== undefined) return row.significant;
  if (row.p_value !== undefined && row.p_value < 0.05) return true;
  return false;
}

function getDeltaColor(delta: number, significant: boolean): string {
  if (!significant) return 'gray';
  if (delta > 0) return 'green';
  if (delta < 0) return 'red';
  return 'gray';
}

/**
 * Visual comparison cards showing each category's delta vs baseline
 * with progress bars and clear indicators
 */
export function GroupComparisonCards({ rows, attributeLabel, baseline }: ComparisonCardProps) {
  const { bgSubtle, bgGraySubtle } = useThemeColors();

  if (!rows || rows.length === 0) {
    return (
      <Paper p="md" withBorder radius="md">
        <Text c="dimmed" ta="center">Keine Daten verfügbar.</Text>
      </Paper>
    );
  }

  // Sort by absolute delta
  const sortedRows = [...rows].sort((a, b) => 
    Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0)
  );

  // Find max absolute delta for scaling
  const maxAbsDelta = Math.max(...rows.map(r => Math.abs(r.delta ?? 0)), 0.01);

  // Count stats
  const significantCount = rows.filter(r => isSignificant(r)).length;
  const positiveCount = rows.filter(r => isSignificant(r) && (r.delta ?? 0) > 0).length;
  const negativeCount = rows.filter(r => isSignificant(r) && (r.delta ?? 0) < 0).length;

  return (
    <Paper p="md" withBorder radius="md">
      <Group justify="space-between" align="flex-start" mb="lg">
        <Group gap="xs">
          <ThemeIcon size="lg" radius="md" variant="light" color="grape">
            <IconGridDots size={20} />
          </ThemeIcon>
          <div>
            <Group gap="xs">
              <Title order={4}>Gruppenvergleich: {attributeLabel}</Title>
              <Tooltip 
                label={`Zeigt den Unterschied (Delta) jeder Gruppe zur Baseline "${translateCategory(baseline || 'Auto')}". Grüne Balken = höhere Werte, rote Balken = niedrigere Werte.`}
                withArrow
                multiline
                w={300}
              >
                <ActionIcon variant="subtle" color="gray" size="sm">
                  <IconInfoCircle size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>
            <Text size="sm" c="dimmed">
              Delta-Werte vs. Baseline: {translateCategory(baseline || 'Auto')}
            </Text>
          </div>
        </Group>

        <Group gap="xs">
          <Badge size="sm" variant="light" color="gray">
            {rows.length} Gruppen
          </Badge>
          {significantCount > 0 && (
            <Badge size="sm" variant="light" color="blue">
              {significantCount} signifikant
            </Badge>
          )}
          {positiveCount > 0 && (
            <Badge size="sm" variant="light" color="green">
              {positiveCount} ↑
            </Badge>
          )}
          {negativeCount > 0 && (
            <Badge size="sm" variant="light" color="red">
              {negativeCount} ↓
            </Badge>
          )}
        </Group>
      </Group>

      <Stack gap="sm">
        {sortedRows.map((row) => {
          const delta = row.delta ?? 0;
          const significant = isSignificant(row);
          const color = getDeltaColor(delta, significant);
          const percentage = Math.abs(delta) / maxAbsDelta * 100;
          const translatedCategory = translateCategory(row.category);

          return (
            <Paper key={row.category} p="sm" bg={significant ? bgSubtle(color) : bgGraySubtle} radius="md">
              <Group justify="space-between" mb={4}>
                <Group gap="xs">
                  <Text fw={500} size="sm">{translatedCategory}</Text>
                  {significant && (
                    <ThemeIcon size="xs" radius="xl" color={color} variant="filled">
                      {delta > 0 ? <IconArrowUp size={10} /> : <IconArrowDown size={10} />}
                    </ThemeIcon>
                  )}
                </Group>
                <Group gap="xs">
                  <Text size="xs" c="dimmed">
                    n={row.count?.toLocaleString('de-DE') ?? '—'}
                  </Text>
                  <Badge 
                    size="sm" 
                    variant={significant ? 'filled' : 'light'} 
                    color={color}
                  >
                    {delta >= 0 ? '+' : ''}{delta.toFixed(3)}
                  </Badge>
                </Group>
              </Group>
              
              <Group gap="xs" align="center">
                {/* Left bar for negative values */}
                <div style={{ flex: 1, display: 'flex', justifyContent: 'flex-end' }}>
                  {delta < 0 && (
                    <Progress
                      value={percentage}
                      color={significant ? 'red' : 'gray'}
                      size="md"
                      radius="xl"
                      style={{ width: `${percentage}%`, minWidth: 10 }}
                    />
                  )}
                </div>
                
                {/* Center line */}
                <div style={{ 
                  width: 2, 
                  height: 20, 
                  backgroundColor: '#495057',
                  borderRadius: 1,
                }} />
                
                {/* Right bar for positive values */}
                <div style={{ flex: 1 }}>
                  {delta > 0 && (
                    <Progress
                      value={percentage}
                      color={significant ? 'green' : 'gray'}
                      size="md"
                      radius="xl"
                      style={{ width: `${percentage}%`, minWidth: 10 }}
                    />
                  )}
                </div>
              </Group>

              {/* Additional details on hover/click */}
              {row.p_value !== undefined && (
                <Text size="xs" c="dimmed" mt={4}>
                  Mittelwert: {row.mean?.toFixed(2) ?? '—'} | p = {row.p_value.toFixed(4)}
                  {significant ? ' ✓' : ''}
                </Text>
              )}
            </Paper>
          );
        })}
      </Stack>

      {/* Legend */}
      <Group gap="lg" mt="lg" justify="center">
        <Group gap="xs">
          <Progress value={50} color="green" size="sm" radius="xl" style={{ width: 40 }} />
          <Text size="xs" c="dimmed">Höher als Baseline</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 2, height: 14, backgroundColor: '#495057', borderRadius: 1 }} />
          <Text size="xs" c="dimmed">Baseline (Δ=0)</Text>
        </Group>
        <Group gap="xs">
          <Progress value={50} color="red" size="sm" radius="xl" style={{ width: 40 }} />
          <Text size="xs" c="dimmed">Niedriger als Baseline</Text>
        </Group>
      </Group>
    </Paper>
  );
}

// Re-export for backwards compatibility
export { GroupComparisonCards as GroupComparisonHeatmap };
