import { Paper, Text, Title, Group, ThemeIcon, Tooltip, ActionIcon, Badge, Stack, Table, Collapse, Button, Alert, SegmentedControl, Box, SimpleGrid, Skeleton } from '@mantine/core';
import { IconRadar2, IconInfoCircle, IconChevronDown, IconChevronUp, IconAlertCircle, IconFilter } from '@tabler/icons-react';
import { useState } from 'react';
import { ChartPanel } from '../../../components/ChartPanel';
import { translateCategory } from './GroupComparisonHeatmap';

// Attribute labels
const ATTR_LABELS: Record<string, string> = {
  gender: 'Geschlecht',
  religion: 'Religion',
  sexuality: 'Sexualität',
  marriage_status: 'Familienstand',
  education: 'Bildung',
  origin_subregion: 'Herkunft',
  migration_status: 'Migration',
};

type DeltaRow = {
  category: string;
  delta: number;
  p_value: number;
  significant: boolean;
  count?: number;
  cliffs_delta?: number | null;
};

type DeltasData = {
  rows: DeltaRow[];
  baseline?: string | null;
};

type BiasRadarProps = {
  /** Delta data for all attributes: { attribute: { rows: [...], baseline: ... } } */
  deltasData: Array<{ 
    a: string; 
    q: { 
      data?: DeltasData; 
      isLoading: boolean; 
      isError: boolean; 
    } 
  }>;
  /** Available trait categories for filtering */
  traitCategories?: string[];
  /** Currently selected trait category */
  selectedTraitCategory?: string;
  /** Callback when trait category changes */
  onTraitCategoryChange?: (category: string) => void;
};

type AttributeScore = {
  attribute: string;
  label: string;
  maxAbsDelta: number;
  avgAbsDelta: number;
  significantCount: number;
  totalCategories: number;
  significantRate: number;
  biasScore: number;
  maxDeltaCategory: string;
  baseline: string;
  hasData: boolean;
};

/**
 * Calculate bias metrics for each attribute
 * 
 * METHODOLOGY (transparent documentation):
 * 
 * For each demographic attribute, we calculate:
 * 
 * 1. Max |Δ| (Maximum Absolute Delta):
 *    - The largest absolute difference between any category and the baseline
 *    - Formula: max(|Δᵢ|) for all categories i
 *    - Interpretation: "How large is the biggest bias found?"
 * 
 * 2. Avg |Δ| (Average Absolute Delta):
 *    - Mean of all absolute delta values
 *    - Formula: Σ|Δᵢ| / n
 *    - Interpretation: "What is the typical bias magnitude?"
 * 
 * 3. Significance Rate:
 *    - Proportion of categories with statistically significant differences (p < 0.05)
 *    - Formula: count(pᵢ < 0.05) / total_categories
 *    - Interpretation: "How often do we find systematic bias?"
 * 
 * 4. Bias Score (Combined Metric for Radar):
 *    - Weighted combination: 50% Max|Δ| + 30% Avg|Δ| + 20% SignificanceRate
 *    - Scaled to 0-100 for visualization
 *    - Formula: 50 * (maxDelta/maxOverall) + 30 * (avgDelta/maxAvgOverall) + 20 * sigRate
 */
function calculateAttributeScores(deltasData: BiasRadarProps['deltasData']): AttributeScore[] {
  const scores: AttributeScore[] = [];
  
  for (const { a, q } of deltasData) {
    if (!q.data?.rows?.length) {
      scores.push({
        attribute: a,
        label: ATTR_LABELS[a] || a,
        maxAbsDelta: 0,
        avgAbsDelta: 0,
        significantCount: 0,
        totalCategories: 0,
        significantRate: 0,
        biasScore: 0,
        maxDeltaCategory: '–',
        baseline: q.data?.baseline || 'Auto',
        hasData: false,
      });
      continue;
    }
    
    const rows = q.data.rows;
    const deltas = rows.map(r => Math.abs(r.delta));
    const maxAbsDelta = Math.max(...deltas);
    const avgAbsDelta = deltas.reduce((a, b) => a + b, 0) / deltas.length;
    const significantCount = rows.filter(r => r.significant).length;
    const significantRate = significantCount / rows.length;
    
    // Find category with max delta
    const maxRow = rows.reduce((max, r) => 
      Math.abs(r.delta) > Math.abs(max.delta) ? r : max
    , rows[0]);
    
    scores.push({
      attribute: a,
      label: ATTR_LABELS[a] || a,
      maxAbsDelta,
      avgAbsDelta,
      significantCount,
      totalCategories: rows.length,
      significantRate,
      biasScore: 0, // Will be calculated after normalization
      maxDeltaCategory: maxRow.category,
      baseline: q.data.baseline || 'Auto',
      hasData: true,
    });
  }
  
  // Normalize and calculate final bias score
  const maxDeltaOverall = Math.max(...scores.filter(s => s.hasData).map(s => s.maxAbsDelta), 0.001);
  const maxAvgOverall = Math.max(...scores.filter(s => s.hasData).map(s => s.avgAbsDelta), 0.001);
  
  for (const score of scores) {
    if (!score.hasData) continue;
    
    // Weighted combination: 50% maxDelta + 30% avgDelta + 20% significanceRate
    // All normalized to 0-1 range, then scaled to 0-100
    const normalizedMax = score.maxAbsDelta / maxDeltaOverall;
    const normalizedAvg = score.avgAbsDelta / maxAvgOverall;
    
    score.biasScore = (
      0.5 * normalizedMax + 
      0.3 * normalizedAvg + 
      0.2 * score.significantRate
    ) * 100;
  }
  
  return scores;
}

export function BiasRadarChart({ deltasData, traitCategories, selectedTraitCategory, onTraitCategoryChange }: BiasRadarProps) {
  const [showMethodology, setShowMethodology] = useState(false);
  const [showDetails, setShowDetails] = useState(false);
  
  // Check if data is still loading
  const isLoading = deltasData.some(d => d.q.isLoading);
  const hasErrors = deltasData.some(d => d.q.isError);
  const hasAnyData = deltasData.some(d => d.q.data?.rows?.length);
  
  if (isLoading) {
    return (
      <Paper p="md" withBorder radius="md">
        <Text c="dimmed" ta="center">Lade Bias-Daten...</Text>
      </Paper>
    );
  }
  
  if (!hasAnyData) {
    return (
      <Paper p="md" withBorder radius="md">
        <Text c="dimmed" ta="center">Keine Bias-Daten verfügbar. Bitte warte auf die Cache-Erwärmung.</Text>
      </Paper>
    );
  }
  
  const scores = calculateAttributeScores(deltasData);
  const validScores = scores.filter(s => s.hasData);
  
  // Prepare radar chart data
  const categories = validScores.map(s => s.label);
  const values = validScores.map(s => s.biasScore);
  
  // Close the radar polygon
  const radarCategories = [...categories, categories[0]];
  const radarValues = [...values, values[0]];
  
  // Calculate average bias for badge
  const avgBias = values.reduce((a, b) => a + b, 0) / values.length;

  // Prepare trait category options for SegmentedControl
  const hasCategoryFilter = traitCategories && traitCategories.length > 0 && onTraitCategoryChange;
  const categoryOptions = hasCategoryFilter ? [
    { value: '__all', label: '🔍 Alle Traits' },
    ...traitCategories.map(c => ({ value: c, label: c }))
  ] : [];
  
  return (
    <Paper p="md" withBorder radius="md">
      <Group justify="space-between" align="flex-start" mb="md" wrap="wrap">
        <Group gap="xs">
          <ThemeIcon size="lg" radius="md" variant="light" color="indigo">
            <IconRadar2 size={20} />
          </ThemeIcon>
          <div>
            <Group gap="xs">
              <Title order={4}>Bias-Intensität pro Merkmal</Title>
              <Tooltip 
                label="Kombinierte Metrik aus Effektgröße und Signifikanz-Rate. Höhere Werte = stärkere systematische Unterschiede gefunden."
                withArrow
                multiline
                w={280}
              >
                <ActionIcon variant="subtle" color="gray" size="sm">
                  <IconInfoCircle size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>
            <Text size="sm" c="dimmed">Überblick über Bias-Tendenzen</Text>
          </div>
        </Group>
        
        <Group gap="md">
          <Badge 
            size="lg" 
            variant="light" 
            color={avgBias > 60 ? 'red' : avgBias > 40 ? 'yellow' : avgBias > 20 ? 'blue' : 'green'}
          >
            Ø {avgBias.toFixed(0)} / 100
          </Badge>
        </Group>
      </Group>

      {/* Trait Category Filter */}
      {hasCategoryFilter && (
        <Box mb="md">
          <Group gap="xs" mb="xs">
            <IconFilter size={14} color="gray" />
            <Text size="sm" fw={500} c="dimmed">Trait-Kategorie filtern:</Text>
            <Tooltip 
              label="Filtere die Bias-Analyse nach Trait-Kategorien. Z.B. zeigt 'kompetenz' nur Traits wie intelligent, fähig etc. Dies hilft, spezifische Bias-Muster zu erkennen (z.B. Bildung → Kompetenz-Traits)."
              withArrow
              multiline
              w={320}
            >
              <ActionIcon variant="subtle" color="gray" size="xs">
                <IconInfoCircle size={12} />
              </ActionIcon>
            </Tooltip>
          </Group>
          <SegmentedControl
            value={selectedTraitCategory || '__all'}
            onChange={(val) => onTraitCategoryChange(val)}
            data={categoryOptions}
            size="xs"
            fullWidth
          />
          {selectedTraitCategory && selectedTraitCategory !== '__all' && (
            <Text size="xs" c="blue" mt="xs">
              ℹ️ Nur Traits der Kategorie „{selectedTraitCategory}" werden analysiert
            </Text>
          )}
        </Box>
      )}
      
      {hasErrors && (
        <Alert color="yellow" icon={<IconAlertCircle size={16} />} mb="md">
          Einige Attribute konnten nicht geladen werden. Die Darstellung ist möglicherweise unvollständig.
        </Alert>
      )}
      
      {/* Radar Chart */}
      <ChartPanel
        data={[
          // Neutraler Füllbereich
          {
            type: 'scatterpolar',
            r: radarValues,
            theta: radarCategories,
            fill: 'toself',
            fillcolor: 'rgba(173, 181, 189, 0.15)', // Neutral gray fill
            line: { color: '#adb5bd', width: 1.5, dash: 'dot' },
            marker: { size: 0 }, // Keine Marker für die Füllung
            name: 'Bias-Bereich',
            hoverinfo: 'skip',
            showlegend: false,
          } as Partial<Plotly.Data>,
          // Individuell gefärbte Punkte pro Attribut
          {
            type: 'scatterpolar',
            r: radarValues,
            theta: radarCategories,
            mode: 'markers',
            marker: { 
              size: 12, 
              color: radarValues.map(v => 
                v > 60 ? '#e03131' : v > 40 ? '#fab005' : v > 20 ? '#228be6' : '#40c057'
              ),
              line: { color: '#fff', width: 2 },
            },
            name: 'Bias-Score',
            hovertemplate: '<b>%{theta}</b><br>Score: %{r:.1f}/100<extra></extra>',
          } as unknown as Partial<Plotly.Data>,
        ]}
        height={350}
        layout={{
          polar: {
            radialaxis: {
              visible: true,
              range: [0, 100],
              tickvals: [0, 25, 50, 75, 100],
              ticktext: ['0', '25', '50', '75', '100'],
              gridcolor: '#e9ecef',
            },
            angularaxis: {
              tickfont: { size: 11 },
              gridcolor: '#e9ecef',
            },
            bgcolor: '#fff',
          },
          margin: { l: 60, r: 60, t: 30, b: 30 },
          showlegend: false,
        }}
      />
      
      {/* Interpretation Guide */}
      <Group gap="lg" mt="md" justify="center" wrap="wrap">
        <Group gap="xs">
          <div style={{ width: 12, height: 12, backgroundColor: '#40c057', borderRadius: 3 }} />
          <Text size="xs" c="dimmed">0-20: Minimal</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 12, height: 12, backgroundColor: '#228be6', borderRadius: 3 }} />
          <Text size="xs" c="dimmed">20-40: Gering</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 12, height: 12, backgroundColor: '#fab005', borderRadius: 3 }} />
          <Text size="xs" c="dimmed">40-60: Moderat</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 12, height: 12, backgroundColor: '#e03131', borderRadius: 3 }} />
          <Text size="xs" c="dimmed">60-100: Stark</Text>
        </Group>
      </Group>
      
      {/* Methodology Toggle */}
      <Stack gap="xs" mt="lg">
        <Button 
          variant="subtle" 
          size="xs" 
          color="gray"
          leftSection={showMethodology ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
          onClick={() => setShowMethodology(!showMethodology)}
        >
          {showMethodology ? 'Methodik verbergen' : 'Berechnungsmethodik anzeigen'}
        </Button>
        
        <Collapse in={showMethodology}>
          <Paper p="md" bg="gray.0" radius="md">
            <Title order={5} mb="sm">Berechnungsmethodik</Title>
            <Text size="sm" mb="md">
              Der <b>Bias-Score</b> ist eine kombinierte Metrik, die pro demografischem Merkmal berechnet wird:
            </Text>
            
            <Stack gap="xs">
              <Paper p="sm" withBorder>
                <Text size="sm" fw={600}>1. Maximale Effektgröße (Max |Δ|) – Gewicht: 50%</Text>
                <Text size="xs" c="dimmed">
                  Der größte absolute Unterschied zwischen einer Kategorie und der Baseline.
                  Formel: max(|Δᵢ|) für alle Kategorien i
                </Text>
              </Paper>
              
              <Paper p="sm" withBorder>
                <Text size="sm" fw={600}>2. Durchschnittliche Effektgröße (Avg |Δ|) – Gewicht: 30%</Text>
                <Text size="xs" c="dimmed">
                  Mittelwert aller absoluten Delta-Werte.
                  Formel: Σ|Δᵢ| / n
                </Text>
              </Paper>
              
              <Paper p="sm" withBorder>
                <Text size="sm" fw={600}>3. Signifikanz-Rate – Gewicht: 20%</Text>
                <Text size="xs" c="dimmed">
                  Anteil der Kategorien mit statistisch signifikantem Unterschied (p &lt; 0.05).
                  Formel: count(pᵢ &lt; 0.05) / Anzahl Kategorien
                </Text>
              </Paper>
              
              <Paper p="sm" bg="blue.0" withBorder>
                <Text size="sm" fw={600}>Gesamtformel:</Text>
                <Text size="xs" ff="monospace">
                  Score = 50% × (Max|Δ| / Max|Δ|_gesamt) + 30% × (Avg|Δ| / Avg|Δ|_gesamt) + 20% × Signifikanz-Rate
                </Text>
                <Text size="xs" c="dimmed" mt="xs">
                  Alle Komponenten werden auf 0-1 normalisiert und dann auf 0-100 skaliert.
                </Text>
              </Paper>
            </Stack>
            
            <Text size="xs" c="dimmed" mt="md">
              <b>Interpretation:</b> Der Score zeigt, wie stark das Modell bei einem Merkmal differenziert. 
              Ein hoher Score bedeutet nicht automatisch "schlecht" – er zeigt lediglich, dass es messbare 
              Unterschiede gibt. Die Ursachen (z.B. gesellschaftliche Realität vs. Modell-Bias) erfordern 
              tiefergehende Analyse.
            </Text>
          </Paper>
        </Collapse>
        
        {/* Detailed Values Toggle */}
        <Button 
          variant="subtle" 
          size="xs" 
          color="gray"
          leftSection={showDetails ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
          onClick={() => setShowDetails(!showDetails)}
        >
          {showDetails ? 'Details verbergen' : 'Detaillierte Werte anzeigen'}
        </Button>
        
        <Collapse in={showDetails}>
          <Table striped withTableBorder withColumnBorders>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Merkmal</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>Max |Δ|</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>Avg |Δ|</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>Sig. Rate</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>Score</Table.Th>
                <Table.Th>Größter Unterschied</Table.Th>
                <Table.Th>Baseline</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {scores.map((s) => (
                <Table.Tr key={s.attribute}>
                  <Table.Td fw={500}>{s.label}</Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {s.hasData ? s.maxAbsDelta.toFixed(3) : '–'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {s.hasData ? s.avgAbsDelta.toFixed(3) : '–'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {s.hasData ? `${(s.significantRate * 100).toFixed(0)}%` : '–'}
                    {s.hasData && (
                      <Text size="xs" c="dimmed" component="span">
                        {' '}({s.significantCount}/{s.totalCategories})
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <Badge 
                      size="sm"
                      color={s.biasScore > 60 ? 'red' : s.biasScore > 40 ? 'yellow' : s.biasScore > 20 ? 'blue' : 'green'}
                    >
                      {s.hasData ? s.biasScore.toFixed(0) : '–'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {s.hasData ? translateCategory(s.maxDeltaCategory) : '–'}
                  </Table.Td>
                  <Table.Td>
                    {s.hasData ? translateCategory(s.baseline) : '–'}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Collapse>
      </Stack>
    </Paper>
  );
}

// ============================================================================
// Compact Mini Radar Chart for Grid Display
// ============================================================================

type MiniRadarProps = {
  deltasData: BiasRadarProps['deltasData'];
  title: string;
  isLoading?: boolean;
};

function MiniRadarChart({ deltasData, title, isLoading }: MiniRadarProps) {
  const hasErrors = deltasData.some(d => d.q.isError);
  const hasAnyData = deltasData.some(d => d.q.data?.rows?.length);
  
  if (isLoading) {
    return (
      <Paper p="sm" withBorder radius="md" h={360}>
        <Text size="sm" fw={600} mb="xs" ta="center">{title}</Text>
        <Skeleton height={300} radius="md" />
      </Paper>
    );
  }
  
  if (!hasAnyData) {
    return (
      <Paper p="sm" withBorder radius="md" h={360}>
        <Text size="sm" fw={600} mb="xs" ta="center">{title}</Text>
        <Text size="xs" c="dimmed" ta="center" mt="xl">Keine Daten</Text>
      </Paper>
    );
  }
  
  const scores = calculateAttributeScores(deltasData);
  const validScores = scores.filter(s => s.hasData);
  
  if (validScores.length === 0) {
    return (
      <Paper p="sm" withBorder radius="md" h={360}>
        <Text size="sm" fw={600} mb="xs" ta="center">{title}</Text>
        <Text size="xs" c="dimmed" ta="center" mt="xl">Keine validen Daten</Text>
      </Paper>
    );
  }
  
  const categories = validScores.map(s => s.label);
  const values = validScores.map(s => s.biasScore);
  const radarCategories = [...categories, categories[0]];
  const radarValues = [...values, values[0]];
  const avgBias = values.reduce((a, b) => a + b, 0) / values.length;
  
  return (
    <Paper p="sm" withBorder radius="md">
      <Group justify="space-between" align="center" mb="xs">
        <Text size="sm" fw={600}>{title}</Text>
        <Badge 
          size="sm" 
          variant="light" 
          color={avgBias > 60 ? 'red' : avgBias > 40 ? 'yellow' : avgBias > 20 ? 'blue' : 'green'}
        >
          Ø {avgBias.toFixed(0)}
        </Badge>
      </Group>
      
      {hasErrors && (
        <Text size="xs" c="orange" mb="xs">⚠️ Teildaten</Text>
      )}
      
      <ChartPanel
        data={[
          {
            type: 'scatterpolar',
            r: radarValues,
            theta: radarCategories,
            fill: 'toself',
            fillcolor: 'rgba(173, 181, 189, 0.15)',
            line: { color: '#adb5bd', width: 1, dash: 'dot' },
            marker: { size: 0 },
            hoverinfo: 'skip',
            showlegend: false,
          } as Partial<Plotly.Data>,
          {
            type: 'scatterpolar',
            r: radarValues,
            theta: radarCategories,
            mode: 'markers',
            marker: { 
              size: 10, 
              color: radarValues.map(v => 
                v > 60 ? '#e03131' : v > 40 ? '#fab005' : v > 20 ? '#228be6' : '#40c057'
              ),
              line: { color: '#fff', width: 1.5 },
            },
            hovertemplate: '<b>%{theta}</b><br>Score: %{r:.1f}<extra></extra>',
          } as unknown as Partial<Plotly.Data>,
        ]}
        height={280}
        layout={{
          polar: {
            radialaxis: {
              visible: true,
              range: [0, 100],
              tickvals: [0, 50, 100],
              ticktext: ['0', '50', '100'],
              tickfont: { size: 10 },
              gridcolor: '#e9ecef',
            },
            angularaxis: {
              tickfont: { size: 10 },
              gridcolor: '#e9ecef',
            },
            bgcolor: '#fff',
          },
          margin: { l: 50, r: 50, t: 20, b: 40 },
          showlegend: false,
        }}
      />
    </Paper>
  );
}

// ============================================================================
// Grid Component showing multiple Radar Charts side by side
// ============================================================================

type BiasRadarGridProps = {
  /** Run ID for fetching data */
  runId: number;
  /** Available trait categories */
  traitCategories: string[];
  /** Map of category -> deltasData */
  categoryDeltasMap: Record<string, BiasRadarProps['deltasData']>;
  /** Loading states per category */
  loadingStates?: Record<string, boolean>;
};

export function BiasRadarGrid({ runId, traitCategories, categoryDeltasMap, loadingStates }: BiasRadarGridProps) {
  const [showMethodology, setShowMethodology] = useState(false);
  
  // Categories to show (all + individual categories)
  const categoriesToShow = ['__all', ...traitCategories.slice(0, 2)]; // Show max 3: All + 2 categories
  
  const getCategoryLabel = (cat: string) => {
    if (cat === '__all') return '🔍 Alle Traits';
    return cat.charAt(0).toUpperCase() + cat.slice(1);
  };
  
  return (
    <Paper p="md" withBorder radius="md">
      <Group justify="space-between" align="flex-start" mb="md">
        <Group gap="xs">
          <ThemeIcon size="lg" radius="md" variant="light" color="indigo">
            <IconRadar2 size={20} />
          </ThemeIcon>
          <div>
            <Group gap="xs">
              <Title order={4}>Bias-Intensität pro Merkmal</Title>
              <Tooltip 
                label="Vergleiche Bias-Muster über verschiedene Trait-Kategorien. Z.B. zeigt 'Kompetenz' nur Traits wie intelligent, fähig etc."
                withArrow
                multiline
                w={300}
              >
                <ActionIcon variant="subtle" color="gray" size="sm">
                  <IconInfoCircle size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>
            <Text size="sm" c="dimmed">Vergleich nach Trait-Kategorien</Text>
          </div>
        </Group>
      </Group>
      
      {/* Grid of Mini Radar Charts */}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
        {categoriesToShow.map(cat => (
          <MiniRadarChart
            key={cat}
            title={getCategoryLabel(cat)}
            deltasData={categoryDeltasMap[cat] || []}
            isLoading={loadingStates?.[cat]}
          />
        ))}
      </SimpleGrid>
      
      {/* Legend */}
      <Group gap="lg" mt="md" justify="center" wrap="wrap">
        <Group gap="xs">
          <div style={{ width: 10, height: 10, backgroundColor: '#40c057', borderRadius: 2 }} />
          <Text size="xs" c="dimmed">0-20</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 10, height: 10, backgroundColor: '#228be6', borderRadius: 2 }} />
          <Text size="xs" c="dimmed">20-40</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 10, height: 10, backgroundColor: '#fab005', borderRadius: 2 }} />
          <Text size="xs" c="dimmed">40-60</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 10, height: 10, backgroundColor: '#e03131', borderRadius: 2 }} />
          <Text size="xs" c="dimmed">60-100</Text>
        </Group>
      </Group>
      
      {/* Methodology Toggle */}
      <Stack gap="xs" mt="md">
        <Button 
          variant="subtle" 
          size="xs" 
          color="gray"
          leftSection={showMethodology ? <IconChevronUp size={14} /> : <IconChevronDown size={14} />}
          onClick={() => setShowMethodology(!showMethodology)}
        >
          {showMethodology ? 'Methodik verbergen' : 'Berechnungsmethodik anzeigen'}
        </Button>
        
        <Collapse in={showMethodology}>
          <Paper p="md" bg="gray.0" radius="md">
            <Title order={5} mb="sm">Berechnungsmethodik</Title>
            <Text size="sm" mb="sm">
              Der <b>Bias-Score</b> kombiniert drei Metriken pro demografischem Merkmal:
            </Text>
            <Text size="xs" c="dimmed">
              • <b>Max |Δ|</b> (50%): Größter absoluter Unterschied zur Baseline<br/>
              • <b>Avg |Δ|</b> (30%): Durchschnittlicher absoluter Unterschied<br/>
              • <b>Signifikanz-Rate</b> (20%): Anteil signifikanter Unterschiede (p &lt; 0.05)
            </Text>
            <Text size="xs" c="dimmed" mt="sm">
              <b>Interpretation:</b> Höhere Werte zeigen stärkere systematische Unterschiede. 
              Die Filterung nach Trait-Kategorie hilft, spezifische Zusammenhänge zu erkennen 
              (z.B. Bildung → Kompetenz-Traits, Religion → Wärme-Traits).
            </Text>
          </Paper>
        </Collapse>
      </Stack>
    </Paper>
  );
}
