import { Card, Table, Badge, Text, Group, Stack, ThemeIcon, Tooltip, Paper, Skeleton, Title, Button, Checkbox } from '@mantine/core';
import { IconChartBar, IconInfoCircle, IconDownload, IconCopy } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { fetchKruskalWallis, type KruskalWallisResponse } from '../api';
import { useThemedColor } from '../../../lib/useThemeColors';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';

const ATTR_LABELS: Record<string, string> = {
  gender: 'Geschlecht',
  age_group: 'Altersgruppe',
  religion: 'Religion',
  sexuality: 'Sexualität',
  marriage_status: 'Familienstand',
  education: 'Bildung',
  origin_subregion: 'Herkunft',
  migration_status: 'Migration',
};

/**
 * Format p-value with scientific notation for very small values.
 */
function formatPValue(p: number | null | undefined): string {
  if (p == null) return '—';
  if (p < 0.001) return p.toExponential(2);
  return p.toFixed(4);
}

/**
 * Get significance stars based on p-value.
 */
function getSignificanceStars(p: number | null | undefined): string {
  if (p == null) return '';
  if (p < 0.001) return '***';
  if (p < 0.01) return '**';
  if (p < 0.05) return '*';
  return '';
}

/**
 * Get effect size color based on eta_squared.
 */
function getEffectColor(eta_squared: number | null | undefined): string {
  if (eta_squared == null) return 'gray';
  if (eta_squared >= 0.14) return 'red';
  if (eta_squared >= 0.06) return 'orange';
  if (eta_squared >= 0.01) return 'yellow';
  return 'gray';
}

type KruskalWallisCardProps = {
  runId: number;
};

type ColumnKey = 'attribute' | 'h_stat' | 'p_value' | 'sig' | 'eta_squared' | 'effect' | 'n_groups' | 'n_total';

export function KruskalWallisCard({ runId }: KruskalWallisCardProps) {
  const getColor = useThemedColor();

  const [selectedColumns, setSelectedColumns] = useState<Set<ColumnKey>>(
    new Set(['attribute', 'h_stat', 'p_value', 'sig', 'eta_squared', 'effect', 'n_groups', 'n_total'])
  );

  const toggleColumn = (col: ColumnKey) => {
    const newSet = new Set(selectedColumns);
    if (newSet.has(col)) {
      newSet.delete(col);
    } else {
      newSet.add(col);
    }
    setSelectedColumns(newSet);
  };

  const { data, isLoading, error } = useQuery<KruskalWallisResponse>({
    queryKey: ['run', runId, 'kruskal'],
    queryFn: () => fetchKruskalWallis(runId),
    staleTime: 1000 * 60 * 5, // 5 min
  });

  if (isLoading) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Stack gap="md">
          <Skeleton height={28} width={250} />
          <Skeleton height={200} />
        </Stack>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Text c="dimmed">Fehler beim Laden der Kruskal-Wallis-Daten</Text>
      </Card>
    );
  }

  const { attributes, summary } = data;

  const attr_labels = {
    gender: 'Geschlecht',
    age_group: 'Altersgruppe',
    religion: 'Religion',
    sexuality: 'Sexualität',
    marriage_status: 'Familienstand',
    education: 'Bildung',
    origin_subregion: 'Herkunft',
    migration_status: 'Migration',
  };

  const handleDownloadCSV = () => {
    // Build CSV with selected columns
    const rows: string[][] = [];
    
    // Header row
    const header: string[] = [];
    if (selectedColumns.has('attribute')) header.push('Attribut');
    if (selectedColumns.has('h_stat')) header.push('H-Statistik');
    if (selectedColumns.has('p_value')) header.push('p-Wert');
    if (selectedColumns.has('eta_squared')) header.push('η² (Eta-Quadrat)');
    if (selectedColumns.has('effect')) header.push('Effektgröße');
    if (selectedColumns.has('sig')) header.push('Signifikant (p < 0.05)');
    if (selectedColumns.has('n_groups')) header.push('Anzahl Gruppen');
    if (selectedColumns.has('n_total')) header.push('n Total');
    rows.push(header);

    // Data rows
    attributes.forEach(attr => {
      const row: string[] = [];
      if (selectedColumns.has('attribute')) row.push(attr_labels[attr.attribute as keyof typeof attr_labels] || attr.attribute);
      if (selectedColumns.has('h_stat')) row.push((attr.h_stat?.toFixed(3) || ''));
      if (selectedColumns.has('p_value')) row.push((attr.p_value?.toFixed(6) || ''));
      if (selectedColumns.has('eta_squared')) row.push((attr.eta_squared?.toFixed(4) || ''));
      if (selectedColumns.has('effect')) row.push(attr.effect_interpretation || '');
      if (selectedColumns.has('sig')) row.push(attr.significant ? 'Ja' : 'Nein');
      if (selectedColumns.has('n_groups')) row.push(String(attr.n_groups || ''));
      if (selectedColumns.has('n_total')) row.push(String(attr.n_total || ''));
      rows.push(row);
    });

    // Generate CSV
    const csvContent = rows.map(row => row.map(cell => {
      // Escape quotes and wrap in quotes if contains comma or quote
      if (cell.includes(',') || cell.includes('"') || cell.includes('\n')) {
        return `"${cell.replace(/"/g, '""')}"`;
      }
      return cell;
    }).join(',')).join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `kruskal_wallis_run_${runId}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const handleCopyLatex = async () => {
    try {
      // Build LaTeX table with selected columns
      const lines: string[] = [
        '\\begin{table}[htbp]',
        '\\centering',
        `\\caption{Kruskal-Wallis H-Test Ergebnisse (Run ${runId})}`,
        `\\label{tab:kruskal_run_${runId}}`,
      ];

      // Determine column spec
      const colSpec: string[] = [];
      if (selectedColumns.has('attribute')) colSpec.push('l');
      if (selectedColumns.has('h_stat')) colSpec.push('r');
      if (selectedColumns.has('p_value')) colSpec.push('r');
      if (selectedColumns.has('eta_squared')) colSpec.push('r');
      if (selectedColumns.has('effect')) colSpec.push('l');
      if (selectedColumns.has('sig')) colSpec.push('l');
      if (selectedColumns.has('n_groups')) colSpec.push('r');
      if (selectedColumns.has('n_total')) colSpec.push('r');
      
      lines.push(`\\begin{tabular}{${colSpec.join('')}}`);
      lines.push('\\toprule');

      // Header row
      const headerCols: string[] = [];
      if (selectedColumns.has('attribute')) headerCols.push('Attribut');
      if (selectedColumns.has('h_stat')) headerCols.push('H-Statistik');
      if (selectedColumns.has('p_value')) headerCols.push('p-Wert');
      if (selectedColumns.has('eta_squared')) headerCols.push('$\\eta^2$');
      if (selectedColumns.has('effect')) headerCols.push('Effektgröße');
      if (selectedColumns.has('sig')) headerCols.push('Signifikant');
      if (selectedColumns.has('n_groups')) headerCols.push('n Gruppen');
      if (selectedColumns.has('n_total')) headerCols.push('n Total');
      lines.push(headerCols.join(' & ') + ' \\\\');
      lines.push('\\midrule');

      // Data rows
      attributes.forEach(attr => {
        const cols: string[] = [];
        if (selectedColumns.has('attribute')) cols.push(attr_labels[attr.attribute as keyof typeof attr_labels] || attr.attribute);
        if (selectedColumns.has('h_stat')) cols.push(attr.h_stat?.toFixed(3) || '—');
        if (selectedColumns.has('p_value')) cols.push(attr.p_value?.toFixed(6) || '—');
        if (selectedColumns.has('eta_squared')) cols.push(attr.eta_squared?.toFixed(4) || '—');
        if (selectedColumns.has('effect')) cols.push(attr.effect_interpretation || 'vernachlässigbar');
        if (selectedColumns.has('sig')) cols.push(attr.significant ? 'Ja' : 'Nein');
        if (selectedColumns.has('n_groups')) cols.push(String(attr.n_groups || 0));
        if (selectedColumns.has('n_total')) cols.push(String(attr.n_total || 0));
        lines.push(cols.join(' & ') + ' \\\\');
      });

      lines.push('\\bottomrule');
      lines.push('\\end{tabular}');
      lines.push('\\end{table}');

      const latex = lines.join('\n');
      await navigator.clipboard.writeText(latex);
      notifications.show({
        title: 'LaTeX kopiert',
        message: 'Die LaTeX-Tabelle wurde in die Zwischenablage kopiert.',
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Fehler',
        message: 'LaTeX konnte nicht in die Zwischenablage kopiert werden.',
        color: 'red',
      });
    }
  };

  return (
    <Card shadow="sm" radius="md" withBorder>
      <Stack gap="md">
        {/* Header */}
        <Group justify="space-between" align="flex-start">
          <Group gap="xs">
            <ThemeIcon size="lg" radius="md" variant="light" color="grape">
              <IconChartBar size={20} />
            </ThemeIcon>
            <div>
              <Title order={5}>Kruskal-Wallis Omnibus-Test</Title>
              <Text size="sm" c="dimmed">
                Gruppenunterschiede pro demografischem Merkmal
              </Text>
            </div>
          </Group>
          <Group gap="xs">
            <Tooltip label="Als CSV herunterladen" withArrow>
              <Button
                variant="light"
                size="xs"
                leftSection={<IconDownload size={16} />}
                onClick={handleDownloadCSV}
              >
                CSV
              </Button>
            </Tooltip>
            <Tooltip label="LaTeX-Tabelle in Zwischenablage kopieren" withArrow>
              <Button
                variant="light"
                size="xs"
                leftSection={<IconCopy size={16} />}
                onClick={handleCopyLatex}
              >
                LaTeX
              </Button>
            </Tooltip>
            <Tooltip 
              label="Der Kruskal-Wallis H-Test prüft, ob sich die Antwortverteilungen zwischen den Gruppen eines Attributs signifikant unterscheiden. η² gibt die Effektstärke an."
              withArrow 
              multiline 
              w={300}
            >
              <ThemeIcon variant="subtle" color="gray" size="sm">
                <IconInfoCircle size={16} />
              </ThemeIcon>
            </Tooltip>
          </Group>
        </Group>

        {/* Summary Badge */}
        <Group>
          <Badge 
            color={summary.significant_count > 0 ? 'green' : 'gray'} 
            variant="light" 
            size="lg"
          >
            {summary.significant_count} / {summary.total} Attribute signifikant
          </Badge>
          <Text size="xs" c="dimmed">
            (p &lt; 0.05)
          </Text>
        </Group>

        {/* Column Selection Hint */}
        <Paper p="xs" bg={getColor('blue').bg} radius="sm">
          <Text size="xs" c="dimmed">
            💡 Tipp: Klicke auf die Checkboxen in den Spaltenüberschriften, um Spalten für den CSV/LaTeX-Export auszuwählen.
          </Text>
        </Paper>

        {/* Results Table */}
        {attributes.length === 0 ? (
          <Text c="dimmed" ta="center" py="md">
            Keine Daten verfügbar
          </Text>
        ) : (
          <Table striped withTableBorder withColumnBorders highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>
                  <Group gap={4}>
                    <Checkbox 
                      size="xs" 
                      checked={selectedColumns.has('attribute')}
                      onChange={() => toggleColumn('attribute')}
                      aria-label="Spalte Attribut für Export auswählen"
                    />
                    <span>Attribut</span>
                  </Group>
                </Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  <Group gap={4} justify="flex-end">
                    <Checkbox 
                      size="xs" 
                      checked={selectedColumns.has('h_stat')}
                      onChange={() => toggleColumn('h_stat')}
                      aria-label="Spalte H-Statistik für Export auswählen"
                    />
                    <span>H-Statistik</span>
                  </Group>
                </Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  <Group gap={4} justify="flex-end">
                    <Checkbox 
                      size="xs" 
                      checked={selectedColumns.has('p_value')}
                      onChange={() => toggleColumn('p_value')}
                      aria-label="Spalte p-Wert für Export auswählen"
                    />
                    <span>p-Wert</span>
                  </Group>
                </Table.Th>
                <Table.Th style={{ textAlign: 'center' }}>
                  <Group gap={4} justify="center">
                    <Checkbox 
                      size="xs" 
                      checked={selectedColumns.has('sig')}
                      onChange={() => toggleColumn('sig')}
                      aria-label="Spalte Signifikanz für Export auswählen"
                    />
                    <span>Sig.</span>
                  </Group>
                </Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  <Group gap={4} justify="flex-end">
                    <Checkbox 
                      size="xs" 
                      checked={selectedColumns.has('eta_squared')}
                      onChange={() => toggleColumn('eta_squared')}
                      aria-label="Spalte Eta-Quadrat für Export auswählen"
                    />
                    <Tooltip label="Eta-Quadrat Effektstärke (klein ≥ 0.01, mittel ≥ 0.06, groß ≥ 0.14)" withArrow>
                      <span>η²</span>
                    </Tooltip>
                  </Group>
                </Table.Th>
                <Table.Th>
                  <Group gap={4}>
                    <Checkbox 
                      size="xs" 
                      checked={selectedColumns.has('effect')}
                      onChange={() => toggleColumn('effect')}
                      aria-label="Spalte Effekt für Export auswählen"
                    />
                    <span>Effekt</span>
                  </Group>
                </Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  <Group gap={4} justify="flex-end">
                    <Checkbox 
                      size="xs" 
                      checked={selectedColumns.has('n_groups')}
                      onChange={() => toggleColumn('n_groups')}
                      aria-label="Spalte n Gruppen für Export auswählen"
                    />
                    <span>n Gruppen</span>
                  </Group>
                </Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  <Group gap={4} justify="flex-end">
                    <Checkbox 
                      size="xs" 
                      checked={selectedColumns.has('n_total')}
                      onChange={() => toggleColumn('n_total')}
                      aria-label="Spalte n Total für Export auswählen"
                    />
                    <span>n Total</span>
                  </Group>
                </Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {attributes.map((row) => (
                <Table.Tr key={row.attribute}>
                  <Table.Td>
                    <Text fw={row.significant ? 600 : 400}>
                      {ATTR_LABELS[row.attribute] || row.attribute}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {row.h_stat?.toFixed(2) ?? '—'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <Text 
                      size="sm" 
                      fw={row.significant ? 600 : 400}
                      c={row.significant ? 'green' : undefined}
                    >
                      {formatPValue(row.p_value)}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'center' }}>
                    {row.significant ? (
                      <Badge color="green" variant="light" size="sm">
                        {getSignificanceStars(row.p_value)}
                      </Badge>
                    ) : (
                      <Text size="xs" c="dimmed">n.s.</Text>
                    )}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <Text 
                      size="sm"
                      fw={(row.eta_squared ?? 0) >= 0.06 ? 600 : 400}
                      c={getEffectColor(row.eta_squared)}
                    >
                      {row.eta_squared?.toFixed(4) ?? '—'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge 
                      color={getEffectColor(row.eta_squared)} 
                      variant="outline" 
                      size="sm"
                    >
                      {row.effect_interpretation}
                    </Badge>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {row.n_groups ?? '—'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {row.n_total?.toLocaleString('de-DE') ?? '—'}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}

        {/* Legend */}
        <Paper p="xs" bg={getColor('gray').bg} radius="sm">
          <Group gap="xl">
            <Group gap="xs">
              <Text size="xs" c="dimmed">Signifikanz:</Text>
              <Text size="xs">*** p &lt; 0.001</Text>
              <Text size="xs">** p &lt; 0.01</Text>
              <Text size="xs">* p &lt; 0.05</Text>
              <Text size="xs" c="dimmed">n.s. nicht signifikant</Text>
            </Group>
            <Group gap="xs">
              <Text size="xs" c="dimmed">Effekt η²:</Text>
              <Badge color="yellow" variant="outline" size="xs">klein ≥ 0.01</Badge>
              <Badge color="orange" variant="outline" size="xs">mittel ≥ 0.06</Badge>
              <Badge color="red" variant="outline" size="xs">groß ≥ 0.14</Badge>
            </Group>
          </Group>
        </Paper>
      </Stack>
    </Card>
  );
}
