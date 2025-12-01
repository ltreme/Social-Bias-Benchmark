import { Paper, Text, Title, Group, ThemeIcon, SimpleGrid, Tooltip } from '@mantine/core';
import { IconArrowUp, IconArrowDown, IconMinus, IconInfoCircle } from '@tabler/icons-react';
import { ChartPanel } from '../../../components/ChartPanel';
import { translateCategory } from './GroupComparisonHeatmap';
import { useThemedColor } from '../../../lib/useThemeColors';

type DeltaRow = {
  category: string;
  delta?: number;
  p_value?: number;
  q_value?: number;
  n_base?: number;
  sd_base?: number;
  n_cat?: number;
  count?: number;
  sd_cat?: number;
  ci_low?: number;
  ci_high?: number;
};

type Deltas = {
  rows: DeltaRow[];
};

function isSignificant(row: DeltaRow): boolean {
  // Consider significant if p < 0.05 or if CI doesn't cross zero
  if (row.p_value !== undefined && row.p_value < 0.05) return true;
  if (row.ci_low !== undefined && row.ci_high !== undefined) {
    return row.ci_low > 0 || row.ci_high < 0;
  }
  return false;
}

function getPlotColor(row: DeltaRow): string {
  const sig = isSignificant(row);
  const delta = row.delta ?? 0;
  
  if (!sig) return '#868e96'; // Gray for non-significant
  if (delta > 0) return '#2f9e44'; // Green for positive
  if (delta < 0) return '#e03131'; // Red for negative
  return '#868e96';
}

function getPlotColorLight(row: DeltaRow): string {
  const sig = isSignificant(row);
  const delta = row.delta ?? 0;
  
  if (!sig) return '#dee2e6';
  if (delta > 0) return '#b2f2bb';
  if (delta < 0) return '#ffc9c9';
  return '#dee2e6';
}

export function DeltaBarsPanel({ deltas, title, baseline }: { deltas?: Deltas; title: string; baseline?: string }) {
  const getThemeColor = useThemedColor();

  if (!deltas || !deltas.rows || deltas.rows.length === 0) {
    return (
      <Paper p="md" withBorder radius="md" style={{ height: '100%' }}>
        <Text c="dimmed">Keine Delta-Daten verfügbar</Text>
      </Paper>
    );
  }

  // Sort by absolute delta value (largest first)
  const sortedRows = [...deltas.rows].sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0));
  
  // Translate category names
  const translatedRows = sortedRows.map(row => ({
    ...row,
    displayCategory: translateCategory(row.category),
  }));
  
  // Create lollipop chart data
  const traces: Partial<Plotly.Data>[] = [
    // Stems (lines from 0 to point)
    ...translatedRows.map((row) => ({
      type: 'scatter' as const,
      mode: 'lines' as const,
      x: [0, row.delta ?? 0],
      y: [row.displayCategory, row.displayCategory],
      line: { color: getPlotColorLight(row), width: 3 },
      showlegend: false,
      hoverinfo: 'skip' as const,
    })),
    // Points with error bars
    {
      type: 'scatter' as const,
      mode: 'markers' as const,
      name: 'Delta',
      x: translatedRows.map((r) => r.delta ?? 0),
      y: translatedRows.map((r) => r.displayCategory),
      marker: { 
        size: 12, 
        color: translatedRows.map(r => getPlotColor(r)),
        line: { color: '#fff', width: 2 },
      },
      error_x: {
        type: 'data' as const,
        symmetric: false,
        array: translatedRows.map((r) => (r.ci_high != null && r.delta != null) ? Math.max(0, r.ci_high - r.delta) : 0),
        arrayminus: translatedRows.map((r) => (r.ci_low != null && r.delta != null) ? Math.max(0, r.delta - r.ci_low) : 0),
        thickness: 2,
        width: 6,
        color: translatedRows.map(r => getPlotColor(r)),
      },
      hovertemplate: translatedRows.map((r) => {
        const sig = isSignificant(r) ? '✓ signifikant' : '○ nicht signifikant';
        const ci = (r.ci_low != null && r.ci_high != null) 
          ? `[${r.ci_low.toFixed(3)}, ${r.ci_high.toFixed(3)}]` 
          : '';
        return `<b>${r.displayCategory}</b><br>` +
          `Δ = ${(r.delta ?? 0).toFixed(3)} ${ci}<br>` +
          `p = ${(r.p_value ?? NaN).toFixed(4)}${r.q_value != null ? `, q = ${r.q_value.toFixed(4)}` : ''}<br>` +
          `n = ${r.n_cat ?? r.count ?? '–'}<br>` +
          `${sig}<extra></extra>`;
      }),
    },
  ];

  // Find significant results for summary
  const sigPositive = translatedRows.filter(r => isSignificant(r) && (r.delta ?? 0) > 0);
  const sigNegative = translatedRows.filter(r => isSignificant(r) && (r.delta ?? 0) < 0);
  const notSig = translatedRows.filter(r => !isSignificant(r));

  // Calculate chart height based on number of categories
  const chartHeight = Math.max(300, translatedRows.length * 50 + 80);

  // Get x-axis range
  const allValues = translatedRows.flatMap(r => [r.delta ?? 0, r.ci_low ?? 0, r.ci_high ?? 0]);
  const maxAbs = Math.max(...allValues.map(v => Math.abs(v)), 0.1);
  const padding = maxAbs * 0.15;

  return (
    <Paper p="md" withBorder radius="md">
      <Group justify="space-between" align="flex-start" mb="md">
        <div>
          <Title order={5}>{title}</Title>
          <Text size="xs" c="dimmed">Mittelwertdifferenz zur Baseline{baseline ? ` (${baseline})` : ''}</Text>
        </div>
        <Tooltip 
          label="Positive Werte (grün): Gruppe wird höher bewertet als Baseline. Negative Werte (rot): niedriger. Grau: nicht signifikant (p ≥ 0.05)."
          multiline
          w={280}
          withArrow
        >
          <ThemeIcon variant="subtle" color="gray" size="sm">
            <IconInfoCircle size={16} />
          </ThemeIcon>
        </Tooltip>
      </Group>

      {/* Summary Cards */}
      <SimpleGrid cols={3} spacing="xs" mb="md">
        <Paper p="xs" bg={getThemeColor('green').bg} radius="sm">
          <Group gap={4}>
            <IconArrowUp size={14} color={getThemeColor('green').icon} />
            <Text size="xs" fw={600} c={getThemeColor('green').text}>{sigPositive.length} höher</Text>
          </Group>
        </Paper>
        <Paper p="xs" bg={getThemeColor('red').bg} radius="sm">
          <Group gap={4}>
            <IconArrowDown size={14} color={getThemeColor('red').icon} />
            <Text size="xs" fw={600} c={getThemeColor('red').text}>{sigNegative.length} niedriger</Text>
          </Group>
        </Paper>
        <Paper p="xs" bg={getThemeColor('gray').bg} radius="sm">
          <Group gap={4}>
            <IconMinus size={14} color={getThemeColor('gray').icon} />
            <Text size="xs" fw={600} c={getThemeColor('gray').text}>{notSig.length} n.s.</Text>
          </Group>
        </Paper>
      </SimpleGrid>

      {/* Lollipop Chart */}
      <ChartPanel 
        title="" 
        data={traces} 
        height={chartHeight}
        layout={{
          showlegend: false,
          margin: { l: 120, r: 40, t: 30, b: 50 },
          xaxis: { 
            title: { text: 'Delta (Δ)', standoff: 10 },
            zeroline: true,
            zerolinecolor: '#333',
            zerolinewidth: 2,
            range: [-(maxAbs + padding), maxAbs + padding],
            gridcolor: '#f1f3f5',
          },
          yaxis: { 
            automargin: true,
            categoryorder: 'array',
            categoryarray: sortedRows.map(r => r.category).reverse(),
          },
          shapes: [
            // Zero line emphasis
            { 
              type: 'line', 
              x0: 0, x1: 0, 
              y0: 0, y1: 1, 
              xref: 'x', yref: 'paper', 
              line: { color: '#333', width: 2 } 
            },
          ],
          annotations: [
            // Left label
            {
              x: -(maxAbs + padding) * 0.9,
              y: 1.08,
              xref: 'x',
              yref: 'paper',
              text: '← niedriger als Baseline',
              showarrow: false,
              font: { size: 10, color: '#868e96' },
            },
            // Right label
            {
              x: (maxAbs + padding) * 0.9,
              y: 1.08,
              xref: 'x',
              yref: 'paper',
              text: 'höher als Baseline →',
              showarrow: false,
              font: { size: 10, color: '#868e96' },
            },
          ],
        }} 
      />

      {/* Legend */}
      <Group gap="lg" mt="sm" justify="center">
        <Group gap={4}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: '#2f9e44' }} />
          <Text size="xs" c="dimmed">Signifikant höher</Text>
        </Group>
        <Group gap={4}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: '#e03131' }} />
          <Text size="xs" c="dimmed">Signifikant niedriger</Text>
        </Group>
        <Group gap={4}>
          <div style={{ width: 12, height: 12, borderRadius: '50%', backgroundColor: '#868e96' }} />
          <Text size="xs" c="dimmed">Nicht signifikant</Text>
        </Group>
      </Group>

      <Text size="xs" c="dimmed" mt="sm" ta="center">
        Fehlerbalken: 95%-Konfidenzintervall | Sortiert nach Effektgröße
      </Text>
    </Paper>
  );
}

