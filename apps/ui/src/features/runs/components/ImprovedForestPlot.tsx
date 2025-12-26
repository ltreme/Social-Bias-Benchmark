import { Paper, Text, Title, Group, ThemeIcon, Badge, Tooltip, ActionIcon, Stack, SegmentedControl, Button } from '@mantine/core';
import { IconChartDots3, IconInfoCircle, IconDownload } from '@tabler/icons-react';
import { useState, useMemo, useRef } from 'react';
import { ChartPanel } from '../../../components/ChartPanel';
import { translateCategory } from './GroupComparisonHeatmap';
import html2canvas from 'html2canvas-pro';
import { notifications } from '@mantine/notifications';

type ForestRow = {
  case_id: string | number;
  label?: string;
  delta?: number | null;
  ci_low?: number | null;
  ci_high?: number | null;
  se?: number | null;
  p_value?: number | null;
  q_value?: number | null;  // FDR-corrected p-value
  cliffs_delta?: number | null;  // Cliff's Delta effect size
  significant?: boolean;  // FDR-corrected significance from backend
  significant_uncorrected?: boolean;  // Uncorrected significance
  valence?: number | null;  // -1 = negative trait, 0 = neutral, 1 = positive
};

export type ForestDataset = {
  target: string;
  color?: string;
  rows: ForestRow[];
  overall?: { mean?: number | null; ci_low?: number | null; ci_high?: number | null };
};

const DEFAULT_COLORS = ['#228be6', '#fa5252', '#40c057', '#fab005', '#7950f2', '#20c997', '#fd7e14', '#e64980'];

type FilterMode = 'all' | 'significant' | 'top10';

function isSignificant(row: ForestRow): boolean {
  // Prefer backend FDR-corrected significance
  if (row.significant !== undefined && row.significant !== null) {
    return row.significant;
  }
  // Fallback: Check q-value (FDR-corrected)
  if (row.q_value !== undefined && row.q_value !== null && row.q_value < 0.05) {
    return true;
  }
  // Fallback: Check p-value (uncorrected)
  if (row.p_value !== undefined && row.p_value !== null && row.p_value < 0.05) {
    return true;
  }
  // Fallback: Check if CI doesn't cross zero
  if (row.ci_low !== undefined && row.ci_high !== undefined && 
      row.ci_low !== null && row.ci_high !== null) {
    return row.ci_low > 0 || row.ci_high < 0;
  }
  return false;
}

// Get significance level for display
function getSignificanceLevel(row: ForestRow): { level: 'none' | 'uncorrected' | 'fdr'; stars: string } {
  if (row.significant === true || (row.q_value != null && row.q_value < 0.05)) {
    if (row.q_value != null && row.q_value < 0.001) return { level: 'fdr', stars: '***' };
    if (row.q_value != null && row.q_value < 0.01) return { level: 'fdr', stars: '**' };
    return { level: 'fdr', stars: '*' };
  }
  if (row.significant_uncorrected === true || (row.p_value != null && row.p_value < 0.05)) {
    return { level: 'uncorrected', stars: '†' };
  }
  return { level: 'none', stars: '' };
}

export function ImprovedForestPlot({
  datasets,
  attr,
  baseline,
  defaultBaseline,
  heightPerRow = 35,
}: {
  datasets: ForestDataset[];
  attr: string;
  baseline?: string;
  defaultBaseline?: string;
  heightPerRow?: number;
}) {
  const [filterMode, setFilterMode] = useState<FilterMode>('all');
  const containerRef = useRef<HTMLDivElement>(null);
  
  const handleExportImage = async () => {
    if (!containerRef.current) return;
    
    try {
      // Hide any remaining Plotly controls temporarily
      const plotlyModebar = containerRef.current.querySelector('.modebar');
      const modebarDisplay = plotlyModebar ? (plotlyModebar as HTMLElement).style.display : null;
      if (plotlyModebar) {
        (plotlyModebar as HTMLElement).style.display = 'none';
      }
      
      const canvas = await html2canvas(containerRef.current, {
        backgroundColor: '#ffffff',
        scale: 2,
        logging: false,
        useCORS: true,
      });
      
      // Restore Plotly controls
      if (plotlyModebar && modebarDisplay !== null) {
        (plotlyModebar as HTMLElement).style.display = modebarDisplay;
      }
      
      canvas.toBlob((blob) => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `forest_plot_${attr}.png`;
        link.click();
        URL.revokeObjectURL(url);
      });
      
      notifications.show({
        title: 'Export erfolgreich',
        message: 'Forest Plot wurde als PNG heruntergeladen',
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Export fehlgeschlagen',
        message: 'Konnte das Bild nicht exportieren',
        color: 'red',
      });
    }
  };
  
  const primary = datasets[0];
  
  // Filter and sort rows based on mode
  const processedData = useMemo(() => {
    if (!primary?.rows) return { datasets: [], labels: [] };
    
    // Get valence indicator for label
    const getValenceIndicator = (valence?: number | null) => {
      if (valence === -1) return '⊖';  // Negative trait
      if (valence === 1) return '⊕';   // Positive trait
      return '○';                       // Neutral/unknown
    };
    
    // Get all row indices and their significance/effect size
    const rowInfo = primary.rows.map((row, idx) => ({
      idx,
      delta: Math.abs(row.delta ?? 0),
      significant: isSignificant(row),
      label: `${row.label || row.case_id}`,
      valence: row.valence,
    }));
    
    let filteredIndices: number[];
    
    switch (filterMode) {
      case 'significant':
        filteredIndices = rowInfo
          .filter(r => r.significant)
          .sort((a, b) => b.delta - a.delta)
          .map(r => r.idx);
        break;
      case 'top10':
        filteredIndices = rowInfo
          .sort((a, b) => b.delta - a.delta)
          .slice(0, 10)
          .map(r => r.idx);
        break;
      default:
        filteredIndices = rowInfo
          .sort((a, b) => b.delta - a.delta)
          .map(r => r.idx);
    }
    
    // Apply filter to all datasets
    const filteredDatasets = datasets.map(ds => ({
      ...ds,
      rows: filteredIndices.map(idx => ds.rows[idx]).filter(Boolean),
    }));
    
    // Labels with valence indicator
    const labels = filteredIndices
      .map(idx => primary.rows[idx])
      .filter(Boolean)
      .map(r => `${getValenceIndicator(r.valence)} ${r.label || String(r.case_id)}`);
    
    return { datasets: filteredDatasets, labels };
  }, [datasets, primary, filterMode]);
  
  const { datasets: filteredDatasets, labels: forestLabels } = processedData;
  const filteredPrimary = filteredDatasets[0];
  
  // Count stats
  const totalCount = primary?.rows?.length || 0;
  const significantCount = primary?.rows?.filter(r => isSignificant(r)).length || 0;
  const significantUncorrectedCount = primary?.rows?.filter(r => 
    r.significant_uncorrected === true || (r.p_value != null && r.p_value < 0.05)
  ).length || 0;
  const displayedCount = forestLabels.length;
  
  // Build traces
  const traces: Partial<Plotly.Data>[] = filteredDatasets.map((d, i) => {
    const color = d.color || DEFAULT_COLORS[i % DEFAULT_COLORS.length];
    const rows = d.rows || [];
    
    // Determine marker colors based on significance
    const markerColors = rows.map(r => {
      const sig = isSignificant(r);
      const delta = r.delta ?? 0;
      if (!sig) return '#adb5bd'; // Gray
      return delta > 0 ? '#2f9e44' : '#e03131'; // Green or Red
    });
    
    const markerSizes = rows.map(r => isSignificant(r) ? 10 : 7);
    
    // Build custom hover text with all statistics
    const hoverTexts = rows.map(r => {
      const sigLevel = getSignificanceLevel(r);
      const parts = [
        `<b>${r.label || r.case_id}</b>`,
        `Δ = ${r.delta?.toFixed(3) ?? 'n/a'}`,
        `CI: [${r.ci_low?.toFixed(3) ?? '?'}, ${r.ci_high?.toFixed(3) ?? '?'}]`,
      ];
      if (r.cliffs_delta != null) {
        parts.push(`Cliff's δ = ${r.cliffs_delta.toFixed(3)}`);
      }
      if (r.p_value != null) {
        parts.push(`p = ${r.p_value < 0.001 ? '<0.001' : r.p_value.toFixed(4)}`);
      }
      if (r.q_value != null) {
        parts.push(`q (FDR) = ${r.q_value < 0.001 ? '<0.001' : r.q_value.toFixed(4)}`);
      }
      if (sigLevel.level !== 'none') {
        parts.push(sigLevel.level === 'fdr' ? `<b>Signifikant (FDR)</b> ${sigLevel.stars}` : `Signifikant (unkorrigiert) ${sigLevel.stars}`);
      }
      return parts.join('<br>');
    });
    
    return {
      name: d.target,
      type: 'scatter',
      mode: 'markers',
      x: rows.map(r => r.delta ?? null),
      y: forestLabels,
      error_x: {
        type: 'data',
        symmetric: false,
        array: rows.map(r => (r.ci_high != null && r.delta != null) 
          ? Math.max(0, r.ci_high - r.delta) : 0),
        arrayminus: rows.map(r => (r.ci_low != null && r.delta != null) 
          ? Math.max(0, r.delta - r.ci_low) : 0),
        thickness: 1.5,
        width: 0,
        color: color,
      },
      marker: { 
        size: markerSizes, 
        color: datasets.length > 1 ? color : markerColors,
        line: { width: 1, color: '#fff' },
        symbol: 'circle',
      },
      hovertext: hoverTexts,
      hoverinfo: 'text',
    };
  });
  
  // Add overall effect if available
  if (filteredPrimary?.overall?.mean !== null && filteredPrimary?.overall?.mean !== undefined) {
    const overall = filteredPrimary.overall;
    traces.push({
      name: 'Overall Effect',
      type: 'scatter',
      mode: 'markers',
      x: [overall.mean],
      y: ['◆ OVERALL'],
      error_x: {
        type: 'data',
        symmetric: false,
        array: [(overall.ci_high ?? 0) - (overall.mean ?? 0)],
        arrayminus: [(overall.mean ?? 0) - (overall.ci_low ?? 0)],
        thickness: 2,
        width: 0,
        color: '#1c7ed6',
      },
      marker: { 
        size: 14, 
        color: '#1c7ed6',
        symbol: 'diamond',
        line: { width: 2, color: '#fff' },
      },
      hovertemplate: '<b>Overall Effect</b><br>Δ = %{x:.3f}<extra></extra>',
    } as Partial<Plotly.Data>);
  }
  
  // Calculate axis range
  const allVals: number[] = [];
  filteredDatasets.forEach(d => {
    d.rows?.forEach(r => {
      if (r.delta != null) allVals.push(r.delta);
      if (r.ci_low != null) allVals.push(r.ci_low);
      if (r.ci_high != null) allVals.push(r.ci_high);
    });
  });
  if (filteredPrimary?.overall) {
    const o = filteredPrimary.overall;
    if (o.mean != null) allVals.push(o.mean);
    if (o.ci_low != null) allVals.push(o.ci_low);
    if (o.ci_high != null) allVals.push(o.ci_high);
  }
  const maxAbs = allVals.length ? Math.max(...allVals.map(v => Math.abs(v))) : 1;
  const pad = Math.max(0.3, maxAbs * 0.15);
  
  // Dynamic height
  const yCount = forestLabels.length + (filteredPrimary?.overall?.mean != null ? 1 : 0);
  const height = Math.max(300, yCount * heightPerRow + 100);
  
  const haveData = traces.length > 0 && forestLabels.length > 0;
  
  // Shapes: zero line and significance threshold lines
  const shapes: Partial<Plotly.Shape>[] = [
    { 
      type: 'line', 
      x0: 0, x1: 0, 
      y0: 0, y1: 1, 
      xref: 'x', yref: 'paper', 
      line: { color: '#495057', width: 2, dash: 'solid' },
    },
  ];
  
  // Add significance region shading
  shapes.push({
    type: 'rect',
    x0: -0.1, x1: 0.1,
    y0: 0, y1: 1,
    xref: 'x', yref: 'paper',
    fillcolor: 'rgba(206, 212, 218, 0.3)',
    line: { width: 0 },
    layer: 'below',
  } as Partial<Plotly.Shape>);

  return (
    <Paper p="md" withBorder radius="md">
      <Stack gap="md">
        {/* Header with Export Button */}
        <Group justify="space-between" align="flex-start">
          <Group gap="xs">
            <ThemeIcon size="lg" radius="md" variant="light" color="blue">
              <IconChartDots3 size={20} />
            </ThemeIcon>
            <div>
              <Group gap="xs">
                <Title order={4}>Forest Plot – {attr}</Title>
                <Tooltip 
                  label="Zeigt Effektgrößen (Delta) mit Konfidenzintervallen. Punkte außerhalb der grauen Zone (±0.1) sind praktisch bedeutsam."
                  withArrow
                  multiline
                  w={280}
                >
                  <ActionIcon variant="subtle" color="gray" size="sm">
                    <IconInfoCircle size={16} />
                  </ActionIcon>
                </Tooltip>
              </Group>
              <Text size="sm" c="dimmed">
                Delta vs. Baseline ({translateCategory(baseline || defaultBaseline || 'Auto')})
              </Text>
            </div>
          </Group>
          
          <Group gap="xs" align="flex-start">
            <Stack gap="xs" align="flex-end">
              <SegmentedControl
                size="xs"
                value={filterMode}
                onChange={(v) => setFilterMode(v as FilterMode)}
                data={[
                  { value: 'all', label: 'Alle' },
                  { value: 'significant', label: 'Nur Sig.' },
                  { value: 'top10', label: 'Top 10' },
                ]}
              />
              <Group gap="xs">
                <Badge size="xs" variant="light" color="gray">
                  {displayedCount} / {totalCount} Traits
                </Badge>
                <Tooltip label={`${significantUncorrectedCount} unkorrigiert signifikant`} withArrow>
                  <Badge size="xs" variant="light" color="green">
                    {significantCount} sig. (FDR)
                  </Badge>
                </Tooltip>
              </Group>
            </Stack>
            <Button
              leftSection={<IconDownload size={16} />}
              variant="light"
              size="sm"
              onClick={handleExportImage}
            >
              PNG Export
            </Button>
          </Group>
        </Group>
        
        {/* Exportable Content */}
        <div ref={containerRef} style={{ padding: '16px', backgroundColor: 'var(--mantine-color-body)' }}>
          {haveData ? (
            <ChartPanel
              data={traces}
              height={height}
              layout={{
                shapes,
                margin: { l: 200, r: 40, t: 10, b: 60 },
                yaxis: { 
                  title: { text: '' }, 
                  automargin: true, 
                  categoryorder: 'array', 
                  categoryarray: [...forestLabels.slice().reverse(), '◆ OVERALL'],
                  tickfont: { size: 11 },
                  gridcolor: '#f1f3f5',
                },
                xaxis: { 
                  title: { text: 'Delta (Effektgröße)', standoff: 10 }, 
                  range: [-(maxAbs + pad), (maxAbs + pad)],
                  zeroline: false,
                  gridcolor: '#e9ecef',
                  tickformat: '+.2f',
                },
                showlegend: datasets.length > 1,
                legend: { 
                  orientation: 'h', 
                  y: -0.15,
                  xanchor: 'center',
                  x: 0.5,
                },
                plot_bgcolor: '#fff',
                paper_bgcolor: '#fff',
              }}
              config={{
                displayModeBar: false,
                responsive: true,
              }}
            />
          ) : (
            <Text c="dimmed" ta="center" py="xl">
              Keine Daten für Forest-Plot verfügbar.
              {filterMode === 'significant' && ' Versuche "Alle" anzuzeigen.'}
            </Text>
          )}
          
          {/* Legend */}
          <Group gap="lg" mt="md" justify="center" wrap="wrap">
            <Group gap="xs">
              <Text size="xs" fw={600}>⊕</Text>
              <Text size="xs" c="dimmed">positiver Trait</Text>
            </Group>
            <Group gap="xs">
              <Text size="xs" fw={600}>⊖</Text>
              <Text size="xs" c="dimmed">negativer Trait</Text>
            </Group>
            <Group gap="xs">
              <div style={{ 
                width: 12, height: 12, 
                backgroundColor: '#2f9e44', 
                borderRadius: '50%',
                border: '1px solid #fff',
                boxShadow: '0 0 0 1px #2f9e44',
              }} />
              <Text size="xs" c="dimmed">Signifikant höher</Text>
            </Group>
            <Group gap="xs">
              <div style={{ 
                width: 12, height: 12, 
                backgroundColor: '#e03131', 
                borderRadius: '50%',
                border: '1px solid #fff',
                boxShadow: '0 0 0 1px #e03131',
              }} />
              <Text size="xs" c="dimmed">Signifikant niedriger</Text>
            </Group>
            <Group gap="xs">
              <div style={{ 
                width: 12, height: 12, 
                backgroundColor: '#adb5bd', 
                borderRadius: '50%',
                border: '1px solid #fff',
                boxShadow: '0 0 0 1px #adb5bd',
              }} />
              <Text size="xs" c="dimmed">Nicht signifikant</Text>
            </Group>
            <Group gap="xs">
              <div style={{ 
                width: 14, height: 14, 
                backgroundColor: 'rgba(206, 212, 218, 0.5)', 
                border: '1px solid #ced4da',
              }} />
              <Text size="xs" c="dimmed">±0.1 Zone</Text>
            </Group>
            {filteredPrimary?.overall?.mean != null && (
              <Group gap="xs">
                <div style={{ 
                  width: 12, height: 12, 
                  backgroundColor: '#1c7ed6', 
                  transform: 'rotate(45deg)',
                }} />
                <Text size="xs" c="dimmed">Overall Effect</Text>
              </Group>
            )}
          </Group>
          
          {/* Significance notation */}
          <Group gap="md" mt="xs" justify="center">
            <Text size="xs" c="dimmed">
              <b>Signifikanz:</b> * p &lt; 0.05, ** p &lt; 0.01, *** p &lt; 0.001 (FDR-korrigiert) | † p &lt; 0.05 (unkorrigiert)
            </Text>
          </Group>
        </div>
      </Stack>
    </Paper>
  );
}
