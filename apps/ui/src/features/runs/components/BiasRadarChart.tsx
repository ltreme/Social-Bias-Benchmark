import { Paper, Text, Title, Group, ThemeIcon, Tooltip, ActionIcon, Badge, Stack, Table, Collapse, Button, Alert, Box, SimpleGrid, Skeleton, useComputedColorScheme, SegmentedControl, Modal, Checkbox } from '@mantine/core';
import { IconRadar2, IconInfoCircle, IconChevronDown, IconChevronUp, IconAlertCircle, IconFilter, IconTable, IconDownload, IconCopy } from '@tabler/icons-react';
import { useState } from 'react';
import React from 'react';
import { ChartPanel } from '../../../components/ChartPanel';
import { translateCategory } from '../utils/kruskalWallisHelpers';
import { InlineMath, BlockMath } from 'react-katex';
import { notifications } from '@mantine/notifications';

// Dark/Light mode chart colors
const chartColors = {
  light: {
    gridcolor: '#e9ecef',
    bgcolor: 'rgba(255,255,255,0)',
    tickcolor: '#495057',
  },
  dark: {
    gridcolor: 'rgba(255,255,255,0.15)',
    bgcolor: 'rgba(0,0,0,0)',
    tickcolor: '#c1c2c5',
  },
};

// ============================================================================
// Normalization Constants for Cliff's Delta
// ============================================================================
//
// Cliff's Delta is a non-parametric effect size measure, standardized to [-1, +1].
// Benefits for benchmarking:
// - Standardized scale makes scores comparable across runs
// - Non-parametric: no distribution assumptions
// - Robust to outliers
// - Established interpretation guidelines
//
// BIAS-SPECIFIC THRESHOLDS (stricter than Vargha & Delaney):
// In fairness/bias contexts, even "small" effects matter due to:
// - Cumulative impact across many decisions
// - High-stakes applications (HR, justice, healthcare)
// - Ethical requirements for algorithmic fairness
// ============================================================================

// Cliff's Delta: Scale up since effect sizes are typically small in bias research
// Factor of 4.0 for better visualization of small but meaningful effects
const CLIFFS_SCALE_FACTOR = 4.0;

// Color thresholds (stricter for bias research context)
// These reflect that even small biases can be practically significant
const COLOR_THRESHOLDS = {
  minimal: 10,    // 0-10: Minimal/negligible bias
  low: 25,        // 10-25: Low but detectable - worth monitoring
  moderate: 45,   // 25-45: Moderate - requires investigation  
  high: 100,      // 45+: High - significant concern
};

// Bias-specific Cliff's Delta thresholds (stricter than Vargha & Delaney 2000)
// |d| < 0.05: Minimal (truly negligible)
// |d| < 0.15: Gering (small but potentially relevant)
// |d| < 0.30: Moderat (clearly relevant for fairness)
// |d| >= 0.30: Stark (significant fairness concern)

// Color palette for bias levels
const BIAS_COLORS = {
  minimal: '#40c057',   // Green
  low: '#228be6',       // Blue  
  moderate: '#fab005',  // Yellow/Orange
  high: '#e03131',      // Red
};

// Helper function to get color based on score
function getBiasColor(score: number): string {
  if (score <= COLOR_THRESHOLDS.minimal) return BIAS_COLORS.minimal;
  if (score <= COLOR_THRESHOLDS.low) return BIAS_COLORS.low;
  if (score <= COLOR_THRESHOLDS.moderate) return BIAS_COLORS.moderate;
  return BIAS_COLORS.high;
}

// Helper function to get Mantine color name based on score
function getBiasColorName(score: number): 'green' | 'blue' | 'yellow' | 'red' {
  if (score <= COLOR_THRESHOLDS.minimal) return 'green';
  if (score <= COLOR_THRESHOLDS.low) return 'blue';
  if (score <= COLOR_THRESHOLDS.moderate) return 'yellow';
  return 'red';
}

// Attribute labels
const ATTR_LABELS: Record<string, string> = {
  gender: 'Geschlecht',
  age_group: 'Altersgruppe',
  religion: 'Religion',
  sexuality: 'Sexualität',
  marriage_status: 'Familienstand',
  education: 'Bildung',
  occupation: 'Beruf',
  occupation_category: 'Berufskategorie',
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
  maxAbsCliffsD: number;
  avgAbsCliffsD: number;
  significantCount: number;
  totalCategories: number;
  biasScore: number;
  maxDeltaCategory: string;
  baseline: string;
  hasData: boolean;
};

/**
 * Calculate bias metrics for each attribute using Cliff's Delta
 * 
 * METHODOLOGY:
 * ═══════════════════════════════════════════════════════════════════════════
 * CLIFF'S DELTA BASED SCORING
 * ═══════════════════════════════════════════════════════════════════════════
 * 
 * Uses Cliff's Delta effect size which is already standardized to [-1, +1].
 * This is statistically robust, non-parametric, and ideal for benchmarking.
 * 
 * Formula:
 *   Score = 100 × (0.6 × min(Max|d| × scale, 1) + 0.4 × min(Avg|d| × scale, 1))
 * 
 * Where:
 *   - d is Cliff's Delta (normalized to [-1, +1])
 *   - scale = 4.0 (amplifies small but meaningful effects)
 *   - 60% weight on maximum effect (worst-case focus)
 *   - 40% weight on average effect (overall picture)
 * 
 * Bias-specific interpretation (stricter than Vargha & Delaney 2000):
 *   - |d| < 0.05: Minimal
 *   - |d| < 0.15: Gering (Low)
 *   - |d| < 0.30: Moderat (Moderate)
 *   - |d| ≥ 0.30: Stark (High)
 * 
 * ═══════════════════════════════════════════════════════════════════════════
 */
function calculateAttributeScores(
  deltasData: BiasRadarProps['deltasData']
): AttributeScore[] {
  const scores: AttributeScore[] = [];
  
  for (const { a, q } of deltasData) {
    if (!q.data?.rows?.length) {
      scores.push({
        attribute: a,
        label: ATTR_LABELS[a] || a,
        maxAbsCliffsD: 0,
        avgAbsCliffsD: 0,
        significantCount: 0,
        totalCategories: 0,
        biasScore: 0,
        maxDeltaCategory: '–',
        baseline: q.data?.baseline || 'Auto',
        hasData: false,
      });
      continue;
    }
    
    const rows = q.data.rows;
    
    // Cliff's Delta metrics
    const cliffsDeltas = rows
      .map(r => r.cliffs_delta != null ? Math.abs(r.cliffs_delta) : null)
      .filter((d): d is number => d !== null);
    const maxAbsCliffsD = cliffsDeltas.length > 0 ? Math.max(...cliffsDeltas) : 0;
    const avgAbsCliffsD = cliffsDeltas.length > 0 
      ? cliffsDeltas.reduce((a, b) => a + b, 0) / cliffsDeltas.length 
      : 0;
    
    // Significance metrics (for display purposes)
    const significantCount = rows.filter(r => r.significant).length;
    
    // Find category with max Cliff's delta
    const maxRow = cliffsDeltas.length > 0
      ? rows.reduce((max, r) => 
          (r.cliffs_delta != null && Math.abs(r.cliffs_delta) > Math.abs(max.cliffs_delta || 0)) ? r : max
        , rows[0])
      : rows[0];
    
    // Calculate Cliff's Delta score
    // Scale up since typical effect sizes are small (0.1-0.3)
    const scaledMaxCliffsD = Math.min(maxAbsCliffsD * CLIFFS_SCALE_FACTOR, 1);
    const scaledAvgCliffsD = Math.min(avgAbsCliffsD * CLIFFS_SCALE_FACTOR, 1);
    const biasScore = cliffsDeltas.length > 0
      ? (0.6 * scaledMaxCliffsD + 0.4 * scaledAvgCliffsD) * 100
      : 0;
    
    scores.push({
      attribute: a,
      label: ATTR_LABELS[a] || a,
      maxAbsCliffsD,
      avgAbsCliffsD,
      significantCount,
      totalCategories: rows.length,
      biasScore,
      maxDeltaCategory: maxRow.category,
      baseline: q.data.baseline || 'Auto',
      hasData: true,
    });
  }
  
  return scores;
}

export function BiasRadarChart({ deltasData, traitCategories, selectedTraitCategory, onTraitCategoryChange }: BiasRadarProps) {
  const colorScheme = useComputedColorScheme('light');
  const isDark = colorScheme === 'dark';
  const colors = isDark ? chartColors.dark : chartColors.light;
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
            color={getBiasColorName(avgBias)}
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
            onChange={(val: string) => onTraitCategoryChange?.(val)}
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
              color: radarValues.map(v => getBiasColor(v)),
              line: { color: isDark ? '#25262b' : '#fff', width: 2 },
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
              gridcolor: colors.gridcolor,
              tickfont: { color: colors.tickcolor },
            },
            angularaxis: {
              tickfont: { size: 11, color: colors.tickcolor },
              gridcolor: colors.gridcolor,
            },
            bgcolor: colors.bgcolor,
          },
          margin: { l: 60, r: 60, t: 30, b: 30 },
          showlegend: false,
        }}
      />
      
      {/* Interpretation Guide */}
      <Group gap="lg" mt="md" justify="center" wrap="wrap">
        <Group gap="xs">
          <div style={{ width: 12, height: 12, backgroundColor: BIAS_COLORS.minimal, borderRadius: 3 }} />
          <Text size="xs" c="dimmed">0-{COLOR_THRESHOLDS.minimal}: Minimal</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 12, height: 12, backgroundColor: BIAS_COLORS.low, borderRadius: 3 }} />
          <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.minimal}-{COLOR_THRESHOLDS.low}: Gering</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 12, height: 12, backgroundColor: BIAS_COLORS.moderate, borderRadius: 3 }} />
          <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.low}-{COLOR_THRESHOLDS.moderate}: Moderat</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 12, height: 12, backgroundColor: BIAS_COLORS.high, borderRadius: 3 }} />
          <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.moderate}+: Stark</Text>
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
          <Paper p="md" radius="md" withBorder>
            <Title order={4} mb="xs">📐 Berechnungsmethodik</Title>
            <Text size="sm" c="dimmed" mb="md">
              Der Bias-Score <InlineMath math="S_m" /> quantifiziert systematische Unterschiede in Bewertungen 
              pro demografischem Merkmal <InlineMath math="m" /> mittels Cliff's Delta – einer non-parametrischen, 
              standardisierten Effektgröße.
            </Text>
            
            <Stack gap="md">
              {/* Header */}
              <Paper p="md" withBorder bg="var(--mantine-color-violet-light)">
                <Group gap="xs" mb="xs">
                  <Text size="lg">📐</Text>
                  <Text size="md" fw={700}>Cliff's Delta (Effektgröße)</Text>
                </Group>
                <Text size="sm" c="dimmed">
                  Non-parametrische Effektgröße. Standardisiert auf [−1, +1]. Robust gegenüber Ausreißern und Verteilungsannahmen.
                </Text>
              </Paper>

              {/* Definition Cliff's Delta */}
              <Paper p="md" withBorder>
                <Text size="sm" fw={700} mb="sm" c="violet">1. Definition: Cliff's Delta</Text>
                <Paper p="lg" radius="md" withBorder>
                  <BlockMath math="d = \frac{\#\{(x,y) : x > y\} - \#\{(x,y) : x < y\}}{n_1 \cdot n_2}" />
                </Paper>
                <Stack gap="xs" mt="sm">
                  <Text size="sm" c="dimmed">
                    <InlineMath math="x \in" /> <b>Gruppe₁</b> (Baseline-Ratings), <InlineMath math="y \in" /> <b>Gruppe₂</b> (Kategorie i Ratings)
                  </Text>
                  <Text size="sm" c="dimmed">
                    Ergebnis: <InlineMath math="d \in [-1, +1]" />, wobei <InlineMath math="|d| = 1" /> perfekte Separation bedeutet
                  </Text>
                </Stack>
              </Paper>
              
              {/* Komponenten */}
              <Paper p="md" withBorder>
                <Text size="sm" fw={700} mb="sm" c="violet">2. Score-Komponenten</Text>
                <Stack gap="xs">
                  <Group gap="md" wrap="nowrap" align="center">
                    <Box w={100}><Text size="sm" fw={600}>Max |d|</Text></Box>
                    <Box style={{ flex: 1 }}><InlineMath math="= \max_i(|d_i|)" /></Box>
                    <Text size="sm" c="dimmed" w={180}>Größte Effektgröße</Text>
                  </Group>
                  <Group gap="md" wrap="nowrap" align="center">
                    <Box w={100}><Text size="sm" fw={600}>Avg |d|</Text></Box>
                    <Box style={{ flex: 1 }}><InlineMath math="= \frac{1}{n} \sum_i |d_i|" /></Box>
                    <Text size="sm" c="dimmed" w={180}>Mittlere Effektgröße</Text>
                  </Group>
                </Stack>
              </Paper>
              
              {/* Hauptformel */}
              <Paper p="md" withBorder bg="var(--mantine-color-violet-light)">
                <Text size="sm" fw={700} mb="sm" c="violet">3. Bias-Score Formel</Text>
                <Paper p="lg" radius="md" withBorder>
                  <BlockMath math={`S_m = 100 \\cdot \\left( \\textcolor{#7950f2}{0.6} \\cdot \\min\\left(\\text{Max}|d| \\times ${CLIFFS_SCALE_FACTOR}, 1\\right) + \\textcolor{#e64980}{0.4} \\cdot \\min\\left(\\text{Avg}|d| \\times ${CLIFFS_SCALE_FACTOR}, 1\\right) \\right)`} />
                </Paper>
                <Text size="xs" c="dimmed" mt="sm" ta="center">
                  Skalierungsfaktor <InlineMath math={`\\times ${CLIFFS_SCALE_FACTOR}`} /> für bessere Visualisierung (typische Effekte: 0.1–0.3)
                </Text>
              </Paper>

              {/* Interpretation - Bias-spezifische Schwellen */}
              <Paper p="md" withBorder>
                <Text size="sm" fw={700} mb="xs" c="violet">4. Bias-spezifische Interpretation</Text>
                <Text size="xs" c="dimmed" mb="sm">
                  Strengere Schwellen als Vargha & Delaney (2000), da in Fairness-Kontexten auch kleine Effekte relevant sind.
                </Text>
                <Table fz="sm" verticalSpacing="sm">
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th w={120}>|d| Bereich</Table.Th>
                      <Table.Th w={140}>Bias-Level</Table.Th>
                      <Table.Th>Bedeutung für Fairness</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    <Table.Tr>
                      <Table.Td><InlineMath math="< 0.05" /></Table.Td>
                      <Table.Td><Badge color="green" variant="light">Minimal</Badge></Table.Td>
                      <Table.Td c="dimmed">Kein praktisch relevanter Bias</Table.Td>
                    </Table.Tr>
                    <Table.Tr>
                      <Table.Td><InlineMath math="< 0.15" /></Table.Td>
                      <Table.Td><Badge color="blue" variant="light">Gering</Badge></Table.Td>
                      <Table.Td c="dimmed">Monitoring empfohlen, potentiell relevant</Table.Td>
                    </Table.Tr>
                    <Table.Tr>
                      <Table.Td><InlineMath math="< 0.30" /></Table.Td>
                      <Table.Td><Badge color="yellow" variant="light">Moderat</Badge></Table.Td>
                      <Table.Td c="dimmed">Untersuchung erforderlich, klar messbar</Table.Td>
                    </Table.Tr>
                    <Table.Tr>
                      <Table.Td><InlineMath math="\geq 0.30" /></Table.Td>
                      <Table.Td><Badge color="red" variant="light">Stark</Badge></Table.Td>
                      <Table.Td c="dimmed">Signifikantes Fairness-Problem</Table.Td>
                    </Table.Tr>
                  </Table.Tbody>
                </Table>
                <Alert variant="light" color="gray" mt="sm" p="xs">
                  <Text size="xs" c="dimmed">
                    <b>Vergleich:</b> Vargha & Delaney (2000) Standard: vernachlässigbar &lt;0.147, klein &lt;0.33, mittel &lt;0.474
                  </Text>
                </Alert>
              </Paper>

              {/* Gewichtung */}
              <Paper p="md" withBorder>
                <Text size="sm" fw={700} mb="sm" c="violet">5. Gewichtungsrationale</Text>
                <Stack gap="xs">
                  <Group gap="sm">
                    <Badge color="violet" variant="filled" w={50}>60%</Badge>
                    <Text size="sm"><b>Max |d|</b> — Fokus auf stärksten Effekt (worst-case)</Text>
                  </Group>
                  <Group gap="sm">
                    <Badge color="pink" variant="filled" w={50}>40%</Badge>
                    <Text size="sm"><b>Avg |d|</b> — Berücksichtigt Gesamtverteilung der Effekte</Text>
                  </Group>
                </Stack>
                <Text size="xs" c="dimmed" mt="sm">
                  Keine Signifikanz-Komponente, da Cliff's Delta bereits als Effektgröße interpretierbar ist.
                </Text>
              </Paper>
            </Stack>
            
            {/* Vergleichbarkeitshinweis */}
            <Alert color="blue" mt="md" variant="light" title="✓ Run-übergreifende Vergleichbarkeit">
              <Text size="sm">
                Die Normalisierung basiert auf der <b>festen Skala</b> von Cliff's Delta <InlineMath math="d \in [-1, +1]" />. 
                Ein Score von 40 bedeutet in <b>allen Runs</b> dasselbe Bias-Niveau – ideal für Benchmarking.
              </Text>
            </Alert>

            {/* Farbskala */}
            <Paper p="md" mt="md" withBorder>
              <Text size="sm" fw={700} mb="sm">🎨 Farbskala & Interpretation</Text>
              <Table fz="sm" verticalSpacing="sm">
                <Table.Tbody>
                  <Table.Tr>
                    <Table.Td w={40}>
                      <div style={{ width: 20, height: 20, backgroundColor: BIAS_COLORS.minimal, borderRadius: 4 }} />
                    </Table.Td>
                    <Table.Td fw={600} w={80} ff="monospace">0–{COLOR_THRESHOLDS.minimal}</Table.Td>
                    <Table.Td fw={600} c="green">Minimal</Table.Td>
                    <Table.Td c="dimmed">Kein nennenswerter Bias nachweisbar</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td>
                      <div style={{ width: 20, height: 20, backgroundColor: BIAS_COLORS.low, borderRadius: 4 }} />
                    </Table.Td>
                    <Table.Td fw={600} ff="monospace">{COLOR_THRESHOLDS.minimal}–{COLOR_THRESHOLDS.low}</Table.Td>
                    <Table.Td fw={600} c="blue">Gering</Table.Td>
                    <Table.Td c="dimmed">Erkennbar, aber statistisch klein</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td>
                      <div style={{ width: 20, height: 20, backgroundColor: BIAS_COLORS.moderate, borderRadius: 4 }} />
                    </Table.Td>
                    <Table.Td fw={600} ff="monospace">{COLOR_THRESHOLDS.low}–{COLOR_THRESHOLDS.moderate}</Table.Td>
                    <Table.Td fw={600} c="yellow">Moderat</Table.Td>
                    <Table.Td c="dimmed">Untersuchungswürdig, praktisch relevant</Table.Td>
                  </Table.Tr>
                  <Table.Tr>
                    <Table.Td>
                      <div style={{ width: 20, height: 20, backgroundColor: BIAS_COLORS.high, borderRadius: 4 }} />
                    </Table.Td>
                    <Table.Td fw={600} ff="monospace">{COLOR_THRESHOLDS.moderate}+</Table.Td>
                    <Table.Td fw={600} c="red">Stark</Table.Td>
                    <Table.Td c="dimmed">Signifikantes Bias-Problem</Table.Td>
                  </Table.Tr>
                </Table.Tbody>
              </Table>
            </Paper>
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
                <Table.Th style={{ textAlign: 'right' }}>Max |d|</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>Avg |d|</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  <Tooltip label="Anzahl signifikanter Kategorien (p < 0.05)" withArrow>
                    <Text component="span" size="sm">Sig.</Text>
                  </Tooltip>
                </Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  <Tooltip label="Cliff's Delta basierter Bias-Score" withArrow>
                    <Text component="span" size="sm">Score</Text>
                  </Tooltip>
                </Table.Th>
                <Table.Th>Größter Unterschied</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {scores.map((s) => (
                <Table.Tr key={s.attribute}>
                  <Table.Td fw={500}>{s.label}</Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {s.hasData && s.maxAbsCliffsD > 0 ? s.maxAbsCliffsD.toFixed(3) : '–'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {s.hasData && s.avgAbsCliffsD > 0 ? s.avgAbsCliffsD.toFixed(3) : '–'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {s.hasData ? `${s.significantCount}/${s.totalCategories}` : '–'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <Badge 
                      size="sm"
                      variant="filled"
                      color={getBiasColorName(s.biasScore)}
                    >
                      {s.hasData ? s.biasScore.toFixed(0) : '–'}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    {s.hasData ? translateCategory(s.maxDeltaCategory) : '–'}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Text size="xs" c="dimmed" mt="xs">
            <b>Legende:</b> |d| = Cliff's Delta Effektgröße, Sig. = Anzahl signifikanter Kategorien (p &lt; 0.05)
          </Text>
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
  const colorScheme = useComputedColorScheme('light');
  const isDark = colorScheme === 'dark';
  const colors = isDark ? chartColors.dark : chartColors.light;
  
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
          color={getBiasColorName(avgBias)}
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
              color: radarValues.map(v => getBiasColor(v)),
              line: { color: isDark ? '#25262b' : '#fff', width: 1.5 },
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
              tickfont: { size: 10, color: colors.tickcolor },
              gridcolor: colors.gridcolor,
            },
            angularaxis: {
              tickfont: { size: 10, color: colors.tickcolor },
              gridcolor: colors.gridcolor,
            },
            bgcolor: colors.bgcolor,
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

export function BiasRadarGrid({ traitCategories, categoryDeltasMap, loadingStates }: BiasRadarGridProps) {
  const [showMethodology, setShowMethodology] = useState(false);
  const [showTableModal, setShowTableModal] = useState(false);
  const [selectedColumns, setSelectedColumns] = useState(new Set(['attribute', 'maxAbsCliffsD', 'avgAbsCliffsD', 'significantCount', 'biasScore', 'maxDeltaCategory']));
  const [selectedCategories, setSelectedCategories] = useState(new Set(['__all', ...traitCategories.slice(0, 2)]));
  
  // Categories to show (all + individual categories)
  const categoriesToShow = ['__all', ...traitCategories.slice(0, 2)]; // Show max 3: All + 2 categories
  
  const getCategoryLabel = (cat: string) => {
    if (cat === '__all') return '🔍 Alle Traits';
    return cat.charAt(0).toUpperCase() + cat.slice(1);
  };
  
  // Calculate scores for all categories for table display
  const allScoresByCategory = categoriesToShow.reduce((acc, cat) => {
    const deltasData = categoryDeltasMap[cat] || [];
    acc[cat] = calculateAttributeScores(deltasData);
    return acc;
  }, {} as Record<string, AttributeScore[]>);
  
  // Generate CSV export
  const handleDownloadCSV = () => {
    const rows: string[] = [];
    
    // Filter categories for export
    const categoriesToExport = categoriesToShow.filter(cat => selectedCategories.has(cat));
    
    if (categoriesToExport.length === 0) {
      notifications.show({
        title: 'Keine Kategorien ausgewählt',
        message: 'Bitte wählen Sie mindestens eine Kategorie für den Export aus',
        color: 'orange',
      });
      return;
    }
    
    // Header
    const headers: string[] = [];
    if (selectedColumns.has('attribute')) headers.push('Merkmal');
    
    // Add category columns based on selection
    categoriesToExport.forEach(cat => {
      const label = getCategoryLabel(cat);
      if (selectedColumns.has('maxAbsCliffsD')) headers.push(`${label} - Max |d|`);
      if (selectedColumns.has('avgAbsCliffsD')) headers.push(`${label} - Avg |d|`);
      if (selectedColumns.has('significantCount')) headers.push(`${label} - Sig.`);
      if (selectedColumns.has('biasScore')) headers.push(`${label} - Score`);
      if (selectedColumns.has('maxDeltaCategory')) headers.push(`${label} - Max Kategorie`);
    });
    
    rows.push(headers.join(','));
    
    // Get all attributes (from first category)
    const firstCat = categoriesToExport[0];
    const attributes = allScoresByCategory[firstCat] || [];
    
    // Data rows
    attributes.forEach((_, idx) => {
      const cols: string[] = [];
      
      if (selectedColumns.has('attribute')) {
        cols.push(attributes[idx].label);
      }
      
      categoriesToExport.forEach(cat => {
        const scores = allScoresByCategory[cat] || [];
        const score = scores[idx];
        
        if (score) {
          if (selectedColumns.has('maxAbsCliffsD')) {
            cols.push(score.hasData ? score.maxAbsCliffsD.toFixed(3) : '–');
          }
          if (selectedColumns.has('avgAbsCliffsD')) {
            cols.push(score.hasData ? score.avgAbsCliffsD.toFixed(3) : '–');
          }
          if (selectedColumns.has('significantCount')) {
            cols.push(score.hasData ? `${score.significantCount}/${score.totalCategories}` : '–');
          }
          if (selectedColumns.has('biasScore')) {
            cols.push(score.hasData ? score.biasScore.toFixed(0) : '–');
          }
          if (selectedColumns.has('maxDeltaCategory')) {
            cols.push(score.hasData ? `"${translateCategory(score.maxDeltaCategory)}"` : '–');
          }
        }
      });
      
      rows.push(cols.join(','));
    });
    
    const csv = rows.join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'bias_intensity.csv';
    link.click();
    
    notifications.show({
      title: 'Export erfolgreich',
      message: 'CSV-Datei wurde heruntergeladen',
      color: 'green',
    });
  };
  
  // Generate LaTeX export and copy to clipboard
  const handleCopyLatex = async () => {
    const lines: string[] = [];
    
    // Filter categories for export
    const categoriesToExport = categoriesToShow.filter(cat => selectedCategories.has(cat));
    
    if (categoriesToExport.length === 0) {
      notifications.show({
        title: 'Keine Kategorien ausgewählt',
        message: 'Bitte wählen Sie mindestens eine Kategorie für den Export aus',
        color: 'orange',
      });
      return;
    }
    
    // Count columns for table format
    let colCount = selectedColumns.has('attribute') ? 1 : 0;
    colCount += categoriesToExport.length * (
      (selectedColumns.has('maxAbsCliffsD') ? 1 : 0) +
      (selectedColumns.has('avgAbsCliffsD') ? 1 : 0) +
      (selectedColumns.has('significantCount') ? 1 : 0) +
      (selectedColumns.has('biasScore') ? 1 : 0) +
      (selectedColumns.has('maxDeltaCategory') ? 1 : 0)
    );
    
    // LaTeX table start
    const colSpec = 'l' + 'r'.repeat(colCount - 1);
    lines.push('\\begin{table}[htbp]');
    lines.push('\\centering');
    lines.push('\\caption{Bias-Intensität pro Merkmal}');
    lines.push('\\label{tab:bias_intensity}');
    lines.push(`\\begin{tabular}{${colSpec}}`);
    lines.push('\\toprule');
    
    // Header
    const headers: string[] = [];
    if (selectedColumns.has('attribute')) headers.push('Merkmal');
    
    categoriesToExport.forEach(cat => {
      const label = getCategoryLabel(cat);
      if (selectedColumns.has('maxAbsCliffsD')) headers.push(`${label} - Max $|d|$`);
      if (selectedColumns.has('avgAbsCliffsD')) headers.push(`${label} - Avg $|d|$`);
      if (selectedColumns.has('significantCount')) headers.push(`${label} - Sig.`);
      if (selectedColumns.has('biasScore')) headers.push(`${label} - Score`);
      if (selectedColumns.has('maxDeltaCategory')) headers.push(`${label} - Max Kategorie`);
    });
    
    lines.push(headers.join(' & ') + ' \\\\');
    lines.push('\\midrule');
    
    // Data rows
    const firstCat = categoriesToExport[0];
    const attributes = allScoresByCategory[firstCat] || [];
    
    attributes.forEach((_, idx) => {
      const cols: string[] = [];
      
      if (selectedColumns.has('attribute')) {
        cols.push(attributes[idx].label);
      }
      
      categoriesToExport.forEach(cat => {
        const scores = allScoresByCategory[cat] || [];
        const score = scores[idx];
        
        if (score) {
          if (selectedColumns.has('maxAbsCliffsD')) {
            cols.push(score.hasData ? score.maxAbsCliffsD.toFixed(3) : '–');
          }
          if (selectedColumns.has('avgAbsCliffsD')) {
            cols.push(score.hasData ? score.avgAbsCliffsD.toFixed(3) : '–');
          }
          if (selectedColumns.has('significantCount')) {
            cols.push(score.hasData ? `${score.significantCount}/${score.totalCategories}` : '–');
          }
          if (selectedColumns.has('biasScore')) {
            cols.push(score.hasData ? score.biasScore.toFixed(0) : '–');
          }
          if (selectedColumns.has('maxDeltaCategory')) {
            cols.push(score.hasData ? translateCategory(score.maxDeltaCategory) : '–');
          }
        }
      });
      
      lines.push(cols.join(' & ') + ' \\\\');
    });
    
    lines.push('\\bottomrule');
    lines.push('\\end{tabular}');
    lines.push('\\end{table}');
    
    const latex = lines.join('\n');
    
    try {
      await navigator.clipboard.writeText(latex);
      notifications.show({
        title: 'LaTeX kopiert',
        message: 'Tabelle wurde in die Zwischenablage kopiert',
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Fehler',
        message: 'Konnte nicht in die Zwischenablage kopieren',
        color: 'red',
      });
    }
  };
  
  const toggleColumn = (col: string) => {
    setSelectedColumns(prev => {
      const newSet = new Set(prev);
      if (newSet.has(col)) {
        newSet.delete(col);
      } else {
        newSet.add(col);
      }
      return newSet;
    });
  };
  
  const toggleCategory = (cat: string) => {
    setSelectedCategories(prev => {
      const newSet = new Set(prev);
      if (newSet.has(cat)) {
        newSet.delete(cat);
      } else {
        newSet.add(cat);
      }
      return newSet;
    });
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
            <Text size="sm" c="dimmed">Vergleich nach Trait-Kategorien (Cliff's Delta)</Text>
          </div>
        </Group>
        <Button
          leftSection={<IconTable size={16} />}
          variant="light"
          size="sm"
          onClick={() => setShowTableModal(true)}
        >
          Tabelle anzeigen
        </Button>
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
          <div style={{ width: 10, height: 10, backgroundColor: BIAS_COLORS.minimal, borderRadius: 2 }} />
          <Text size="xs" c="dimmed">0-{COLOR_THRESHOLDS.minimal}</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 10, height: 10, backgroundColor: BIAS_COLORS.low, borderRadius: 2 }} />
          <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.minimal}-{COLOR_THRESHOLDS.low}</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 10, height: 10, backgroundColor: BIAS_COLORS.moderate, borderRadius: 2 }} />
          <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.low}-{COLOR_THRESHOLDS.moderate}</Text>
        </Group>
        <Group gap="xs">
          <div style={{ width: 10, height: 10, backgroundColor: BIAS_COLORS.high, borderRadius: 2 }} />
          <Text size="xs" c="dimmed">{COLOR_THRESHOLDS.moderate}+</Text>
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
          <Paper p="md" radius="md" withBorder>
            <Title order={4} mb="xs">📐 Berechnungsmethodik</Title>
            <Text size="sm" c="dimmed" mb="md">
              Der Bias-Score <InlineMath math="S_m" /> quantifiziert systematische Unterschiede pro Merkmal 
              mittels Cliff's Delta – einer non-parametrischen, standardisierten Effektgröße.
            </Text>

            <Stack gap="md">
              <Paper p="sm" withBorder bg="var(--mantine-color-violet-light)">
                <Group gap="xs" mb="xs">
                  <Text size="md">📐</Text>
                  <Text size="sm" fw={700}>Cliff's Delta (Effektgröße)</Text>
                </Group>
                <Text size="xs" c="dimmed">
                  Non-parametrische Effektgröße auf [−1, +1]. Robust gegenüber Ausreißern.
                </Text>
              </Paper>

              <Paper p="sm" withBorder>
                <Text size="sm" fw={700} mb="sm" c="violet">Definition: Cliff's Delta</Text>
                <Paper p="md" radius="sm" withBorder>
                  <BlockMath math="d = \frac{\#\{(x,y) : x > y\} - \#\{(x,y) : x < y\}}{n_1 \cdot n_2}" />
                </Paper>
                <Text size="xs" c="dimmed" mt="xs">
                  <InlineMath math="x \in" /> Baseline, <InlineMath math="y \in" /> Kategorie i → <InlineMath math="d \in [-1, +1]" />
                </Text>
              </Paper>

              <Paper p="sm" withBorder>
                <Text size="sm" fw={700} mb="sm" c="violet">Score-Komponenten</Text>
                <Stack gap="xs">
                  <Group gap="md" wrap="nowrap">
                    <Box w={100}><Text size="sm" fw={600}>Max |d|</Text></Box>
                    <Box style={{ flex: 1 }}><InlineMath math="= \max_i(|d_i|)" /></Box>
                    <Text size="xs" c="dimmed">Größte Effektgröße</Text>
                  </Group>
                  <Group gap="md" wrap="nowrap">
                    <Box w={100}><Text size="sm" fw={600}>Avg |d|</Text></Box>
                    <Box style={{ flex: 1 }}><InlineMath math="= \frac{1}{n} \sum_i |d_i|" /></Box>
                    <Text size="xs" c="dimmed">Mittlere Effektgröße</Text>
                  </Group>
                </Stack>
              </Paper>

              <Paper p="sm" withBorder bg="var(--mantine-color-violet-light)">
                <Text size="sm" fw={700} mb="sm" c="violet">Bias-Score Formel</Text>
                <Paper p="md" radius="sm" withBorder>
                  <BlockMath math={`S_m = 100 \\cdot \\left( \\textcolor{#7950f2}{0.6} \\cdot \\min\\left(\\text{Max}|d| \\times ${CLIFFS_SCALE_FACTOR}, 1\\right) + \\textcolor{#e64980}{0.4} \\cdot \\min\\left(\\text{Avg}|d| \\times ${CLIFFS_SCALE_FACTOR}, 1\\right) \\right)`} />
                </Paper>
              </Paper>

              <Paper p="sm" withBorder>
                <Text size="sm" fw={700} mb="xs" c="violet">Bias-spezifische Interpretation</Text>
                <Text size="xs" c="dimmed" mb="xs">Strengere Schwellen für Fairness-Kontexte</Text>
                <Table fz="xs" verticalSpacing="xs">
                  <Table.Tbody>
                    <Table.Tr>
                      <Table.Td w={90}><InlineMath math="|d| < 0.05" /></Table.Td>
                      <Table.Td><Badge color="green" variant="light" size="xs">Minimal</Badge></Table.Td>
                    </Table.Tr>
                    <Table.Tr>
                      <Table.Td><InlineMath math="|d| < 0.15" /></Table.Td>
                      <Table.Td><Badge color="blue" variant="light" size="xs">Gering</Badge></Table.Td>
                    </Table.Tr>
                    <Table.Tr>
                      <Table.Td><InlineMath math="|d| < 0.30" /></Table.Td>
                      <Table.Td><Badge color="yellow" variant="light" size="xs">Moderat</Badge></Table.Td>
                    </Table.Tr>
                    <Table.Tr>
                      <Table.Td><InlineMath math="|d| \geq 0.30" /></Table.Td>
                      <Table.Td><Badge color="red" variant="light" size="xs">Stark</Badge></Table.Td>
                    </Table.Tr>
                  </Table.Tbody>
                </Table>
              </Paper>

              <Paper p="sm" withBorder>
                <Text size="sm" fw={700} mb="sm" c="violet">Gewichtung</Text>
                <Stack gap="xs">
                  <Group gap="sm">
                    <Badge color="violet" variant="filled" size="sm" w={45}>60%</Badge>
                    <Text size="xs"><b>Max |d|</b> — Stärkster Effekt</Text>
                  </Group>
                  <Group gap="sm">
                    <Badge color="pink" variant="filled" size="sm" w={45}>40%</Badge>
                    <Text size="xs"><b>Avg |d|</b> — Gesamtverteilung</Text>
                  </Group>
                </Stack>
              </Paper>
            </Stack>

            <Alert color="blue" mt="md" variant="light" title="✓ Run-übergreifende Vergleichbarkeit">
              <Text size="xs">
                Normalisierung auf fester Skala: Cliff's <InlineMath math="d \in [-1,+1]" />. 
                Score 40 = gleiches Bias-Niveau in allen Runs.
              </Text>
            </Alert>

            <Paper p="sm" mt="md" withBorder>
              <Text size="sm" fw={700} mb="xs">🎨 Farbskala</Text>
              <Group gap="md">
                <Group gap="xs">
                  <div style={{ width: 16, height: 16, backgroundColor: BIAS_COLORS.minimal, borderRadius: 3 }} />
                  <Text size="xs" fw={600}>0–{COLOR_THRESHOLDS.minimal}</Text>
                </Group>
                <Group gap="xs">
                  <div style={{ width: 16, height: 16, backgroundColor: BIAS_COLORS.low, borderRadius: 3 }} />
                  <Text size="xs" fw={600}>{COLOR_THRESHOLDS.minimal}–{COLOR_THRESHOLDS.low}</Text>
                </Group>
                <Group gap="xs">
                  <div style={{ width: 16, height: 16, backgroundColor: BIAS_COLORS.moderate, borderRadius: 3 }} />
                  <Text size="xs" fw={600}>{COLOR_THRESHOLDS.low}–{COLOR_THRESHOLDS.moderate}</Text>
                </Group>
                <Group gap="xs">
                  <div style={{ width: 16, height: 16, backgroundColor: BIAS_COLORS.high, borderRadius: 3 }} />
                  <Text size="xs" fw={600}>{COLOR_THRESHOLDS.moderate}+</Text>
                </Group>
              </Group>
            </Paper>
          </Paper>
        </Collapse>
      </Stack>
      
      {/* Table Modal */}
      <Modal
        opened={showTableModal}
        onClose={() => setShowTableModal(false)}
        size="xl"
        title={
          <Group gap="xs">
            <IconTable size={20} />
            <Text fw={600}>Bias-Intensität Tabelle</Text>
          </Group>
        }
      >
        <Stack gap="md">
          {/* Export Controls */}
          <Paper p="sm" withBorder radius="sm">
            <Stack gap="sm">
              <div>
                <Text size="sm" fw={500} mb="xs">Kategorien für Export:</Text>
                <Group gap="xs">
                  {categoriesToShow.map(cat => (
                    <Checkbox
                      key={cat}
                      label={getCategoryLabel(cat)}
                      size="xs"
                      checked={selectedCategories.has(cat)}
                      onChange={() => toggleCategory(cat)}
                    />
                  ))}
                </Group>
              </div>
              <div>
                <Text size="sm" fw={500} mb="xs">Spalten für Export:</Text>
                <Group gap="xs">
                  <Checkbox
                    label="Max |d|"
                    size="xs"
                    checked={selectedColumns.has('maxAbsCliffsD')}
                    onChange={() => toggleColumn('maxAbsCliffsD')}
                  />
                  <Checkbox
                    label="Avg |d|"
                    size="xs"
                    checked={selectedColumns.has('avgAbsCliffsD')}
                    onChange={() => toggleColumn('avgAbsCliffsD')}
                  />
                  <Checkbox
                    label="Sig."
                    size="xs"
                    checked={selectedColumns.has('significantCount')}
                    onChange={() => toggleColumn('significantCount')}
                  />
                  <Checkbox
                    label="Score"
                    size="xs"
                    checked={selectedColumns.has('biasScore')}
                    onChange={() => toggleColumn('biasScore')}
                  />
                  <Checkbox
                    label="Max Kategorie"
                    size="xs"
                    checked={selectedColumns.has('maxDeltaCategory')}
                    onChange={() => toggleColumn('maxDeltaCategory')}
                  />
                </Group>
              </div>
            </Stack>
            <Group gap="xs" mt="sm">
              <Button
                leftSection={<IconDownload size={16} />}
                variant="light"
                size="sm"
                onClick={handleDownloadCSV}
              >
                CSV Download
              </Button>
              <Button
                leftSection={<IconCopy size={16} />}
                variant="light"
                size="sm"
                onClick={handleCopyLatex}
              >
                LaTeX kopieren
              </Button>
            </Group>
          </Paper>
          
          {/* Individual Tables for each Category */}
          {categoriesToShow.map(cat => {
            const scores = allScoresByCategory[cat] || [];
            const validScores = scores.filter(s => s.hasData);
            
            // Find max values for this category
            const maxVals = {
              maxAbsCliffsD: validScores.length > 0 ? Math.max(...validScores.map(s => s.maxAbsCliffsD)) : 0,
              avgAbsCliffsD: validScores.length > 0 ? Math.max(...validScores.map(s => s.avgAbsCliffsD)) : 0,
              significantCount: validScores.length > 0 ? Math.max(...validScores.map(s => s.significantCount)) : 0,
              biasScore: validScores.length > 0 ? Math.max(...validScores.map(s => s.biasScore)) : 0,
            };
            
            return (
              <Box key={cat}>
                <Title order={5} mb="xs">{getCategoryLabel(cat)}</Title>
                <Box style={{ overflowX: 'auto' }}>
                  <Table striped withTableBorder withColumnBorders highlightOnHover>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Merkmal</Table.Th>
                        {selectedColumns.has('maxAbsCliffsD') && <Table.Th style={{ textAlign: 'right' }}>Max |d|</Table.Th>}
                        {selectedColumns.has('avgAbsCliffsD') && <Table.Th style={{ textAlign: 'right' }}>Avg |d|</Table.Th>}
                        {selectedColumns.has('significantCount') && <Table.Th style={{ textAlign: 'right' }}>Sig.</Table.Th>}
                        {selectedColumns.has('biasScore') && <Table.Th style={{ textAlign: 'right' }}>Score</Table.Th>}
                        {selectedColumns.has('maxDeltaCategory') && <Table.Th>Max Kategorie</Table.Th>}
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {scores.map(score => {
                        // Check if this row has the max value for each metric
                        const isMaxAbsCliffsD = score?.hasData && score.maxAbsCliffsD === maxVals.maxAbsCliffsD && maxVals.maxAbsCliffsD > 0;
                        const isMaxAvgCliffsD = score?.hasData && score.avgAbsCliffsD === maxVals.avgAbsCliffsD && maxVals.avgAbsCliffsD > 0;
                        const isMaxSigCount = score?.hasData && score.significantCount === maxVals.significantCount && maxVals.significantCount > 0;
                        const isMaxScore = score?.hasData && score.biasScore === maxVals.biasScore && maxVals.biasScore > 0;
                        
                        return (
                          <Table.Tr key={score.attribute}>
                            <Table.Td fw={500}>{score.label}</Table.Td>
                            {selectedColumns.has('maxAbsCliffsD') && (
                              <Table.Td style={{ textAlign: 'right' }} fw={isMaxAbsCliffsD ? 700 : undefined}>
                                {score?.hasData ? score.maxAbsCliffsD.toFixed(3) : '–'}
                              </Table.Td>
                            )}
                            {selectedColumns.has('avgAbsCliffsD') && (
                              <Table.Td style={{ textAlign: 'right' }} fw={isMaxAvgCliffsD ? 700 : undefined}>
                                {score?.hasData ? score.avgAbsCliffsD.toFixed(3) : '–'}
                              </Table.Td>
                            )}
                            {selectedColumns.has('significantCount') && (
                              <Table.Td style={{ textAlign: 'right' }} fw={isMaxSigCount ? 700 : undefined}>
                                {score?.hasData ? `${score.significantCount}/${score.totalCategories}` : '–'}
                              </Table.Td>
                            )}
                            {selectedColumns.has('biasScore') && (
                              <Table.Td style={{ textAlign: 'right' }}>
                                {score?.hasData ? (
                                  <Badge
                                    size="sm"
                                    variant="filled"
                                    color={getBiasColorName(score.biasScore)}
                                    fw={isMaxScore ? 700 : 500}
                                  >
                                    {score.biasScore.toFixed(0)}
                                  </Badge>
                                ) : '–'}
                              </Table.Td>
                            )}
                            {selectedColumns.has('maxDeltaCategory') && (
                              <Table.Td>
                                {score?.hasData ? translateCategory(score.maxDeltaCategory) : '–'}
                              </Table.Td>
                            )}
                          </Table.Tr>
                        );
                      })}
                    </Table.Tbody>
                  </Table>
                </Box>
              </Box>
            );
          })}
          
          <Text size="xs" c="dimmed">
            <b>Legende:</b> Max |d| = Maximale Cliff's Delta Effektgröße, Avg |d| = Durchschnittliche Effektgröße, 
            Sig. = Anzahl signifikanter Kategorien (p &lt; 0.05), Score = Bias-Intensität Score (0-100)
          </Text>
        </Stack>
      </Modal>
    </Paper>
  );
}
