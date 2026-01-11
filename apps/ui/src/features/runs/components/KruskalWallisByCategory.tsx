import { Card, Table, Badge, Text, Group, Stack, ThemeIcon, Tooltip, Paper, Skeleton, Title, Tabs, Button, Checkbox } from '@mantine/core';
import { IconChartBar, IconInfoCircle, IconDownload, IconCopy } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { 
  fetchKruskalWallisByCategory, 
  fetchKruskalWallis,
  type KruskalWallisByCategoryResponse,
  type KruskalWallisResponse 
} from '../api';
import { useThemedColor } from '../../../lib/useThemeColors';
import { notifications } from '@mantine/notifications';
import { useState } from 'react';
import { 
  ATTR_LABELS, 
  CATEGORY_LABELS,
  formatPValue,
  formatPValueForLatex, 
  getSignificanceStars, 
  getEffectColor,
  type ColumnKey,
  LATEX_COLUMN_DEFS,
  LATEX_COLUMN_HEADERS
} from '../utils/kruskalWallisHelpers';

type KruskalWallisByCategoryProps = {
  runId: number;
};

type CategoryResults = {
  attributes: Array<{
    attribute: string;
    h_stat: number | null;
    p_value: number | null;
    eta_squared: number | null;
    n_groups: number | null;
    n_total: number | null;
    significant: boolean;
    effect_interpretation: string;
  }>;
  summary: {
    significant_count: number;
    total: number;
  };
};

function KruskalTable({ 
  data, 
  selectedColumns, 
  onToggleColumn 
}: { 
  data: CategoryResults;
  selectedColumns: Set<ColumnKey>;
  onToggleColumn: (col: ColumnKey) => void;
}) {
  const { attributes } = data;

  if (attributes.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="md">
        Keine Daten verfügbar
      </Text>
    );
  }

  return (
    <Table striped withTableBorder withColumnBorders highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>
            <Group gap={4}>
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('attribute')}
                onChange={() => onToggleColumn('attribute')}
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
                onChange={() => onToggleColumn('h_stat')}
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
                onChange={() => onToggleColumn('p_value')}
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
                onChange={() => onToggleColumn('sig')}
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
                onChange={() => onToggleColumn('eta_squared')}
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
                onChange={() => onToggleColumn('effect')}
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
                onChange={() => onToggleColumn('n_groups')}
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
                onChange={() => onToggleColumn('n_total')}
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
  );
}

export function KruskalWallisByCategory({ runId }: KruskalWallisByCategoryProps) {
  const getColor = useThemedColor();
  const [activeTab, setActiveTab] = useState<string | null>('alle');
  
  // Column selection state - all enabled by default
  const [selectedColumns, setSelectedColumns] = useState<Set<ColumnKey>>(
    new Set<ColumnKey>(['attribute', 'h_stat', 'p_value', 'sig', 'eta_squared', 'effect', 'n_groups', 'n_total'])
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

  // Fetch both omnibus and by-category data
  const { data: omnibusData, isLoading: omnibusLoading, error: omnibusError } = useQuery<KruskalWallisResponse>({
    queryKey: ['run', runId, 'kruskal'],
    queryFn: () => fetchKruskalWallis(runId),
    staleTime: 1000 * 60 * 5,
  });

  const { data, isLoading, error} = useQuery<KruskalWallisByCategoryResponse>({
    queryKey: ['run', runId, 'kruskal-by-category'],
    queryFn: () => fetchKruskalWallisByCategory(runId),
    staleTime: 1000 * 60 * 5, // 5 min
  });

  if (isLoading || omnibusLoading) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Stack gap="md">
          <Skeleton height={28} width={300} />
          <Skeleton height={40} />
          <Skeleton height={300} />
        </Stack>
      </Card>
    );
  }

  if (error || !data || !data.categories || omnibusError || !omnibusData) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Text c="dimmed">Fehler beim Laden der Kruskal-Wallis-Daten</Text>
      </Card>
    );
  }

  const { categories } = data;
  
  // Combine omnibus data with category data
  const allCategories: Record<string, CategoryResults> = {
    alle: {
      attributes: omnibusData.attributes,
      summary: omnibusData.summary,
    },
    ...categories,
  };
  
  const categoryKeys = ['alle', ...Object.keys(categories).sort()];

  if (categoryKeys.length === 1) { // Only 'alle' tab
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Text c="dimmed" ta="center">Keine Trait-Kategorien verfügbar</Text>
      </Card>
    );
  }

  // Calculate overall stats (from omnibus data)
  const totalSignificant = omnibusData.summary.significant_count;
  const totalTests = omnibusData.summary.total;

  const handleDownloadCSV = () => {
    if (!activeTab) return;
    
    const catData = allCategories[activeTab];
    if (!catData) return;
    
    // Build CSV rows
    const rows: string[][] = [];
    
    // Header row
    const header: string[] = [];
    if (selectedColumns.has('attribute')) header.push('Attribut');
    if (selectedColumns.has('h_stat')) header.push('H-Statistik');
    if (selectedColumns.has('p_value')) header.push('p-Wert');
    if (selectedColumns.has('sig')) header.push('Signifikanz');
    if (selectedColumns.has('eta_squared')) header.push('η²');
    if (selectedColumns.has('effect')) header.push('Effekt');
    if (selectedColumns.has('n_groups')) header.push('n Gruppen');
    if (selectedColumns.has('n_total')) header.push('n Total');
    
    if (header.length === 0) {
      notifications.show({
        title: 'Keine Spalten ausgewählt',
        message: 'Bitte wählen Sie mindestens eine Spalte für den Export aus.',
        color: 'orange',
      });
      return;
    }
    
    rows.push(header);

    // Data rows
    catData.attributes.forEach(attr => {
      const row: string[] = [];
      if (selectedColumns.has('attribute')) row.push(ATTR_LABELS[attr.attribute] || attr.attribute);
      if (selectedColumns.has('h_stat')) row.push(attr.h_stat?.toFixed(2) ?? '—');
      if (selectedColumns.has('p_value')) row.push(formatPValue(attr.p_value));
      if (selectedColumns.has('sig')) row.push(attr.significant ? getSignificanceStars(attr.p_value) : 'n.s.');
      if (selectedColumns.has('eta_squared')) row.push(attr.eta_squared?.toFixed(4) ?? '—');
      if (selectedColumns.has('effect')) row.push(attr.effect_interpretation);
      if (selectedColumns.has('n_groups')) row.push(String(attr.n_groups ?? '—'));
      if (selectedColumns.has('n_total')) row.push(String(attr.n_total ?? '—'));
      rows.push(row);
    });

    // Generate CSV
    const csvContent = rows.map(row => row.map(cell => {
      if (cell.includes(',') || cell.includes('"') || cell.includes('\n')) {
        return `"${cell.replace(/"/g, '""')}"`
;
      }
      return cell;
    }).join(',')).join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    const categoryLabel = CATEGORY_LABELS[activeTab] || activeTab;
    link.download = `kruskal_${categoryLabel}_run_${runId}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
    
    notifications.show({
      title: 'CSV heruntergeladen',
      message: `Die Kruskal-Wallis Tabelle für ${categoryLabel} wurde heruntergeladen.`,
      color: 'green',
    });
  };

  const handleCopyLatex = async () => {
    if (!activeTab) return;
    
    const catData = allCategories[activeTab];
    if (!catData) return;
    
    const selectedCols = Array.from(selectedColumns);
    
    if (selectedCols.length === 0) {
      notifications.show({
        title: 'Keine Spalten ausgewählt',
        message: 'Bitte wählen Sie mindestens eine Spalte für den Export aus.',
        color: 'orange',
      });
      return;
    }
    
    try {
      const categoryLabel = CATEGORY_LABELS[activeTab] || activeTab;
      
      const lines: string[] = [
        '\\begin{table}[htbp]',
        '\\centering',
        `\\caption{Kruskal-Wallis Tests: ${categoryLabel} (Run ${runId})}`,
        `\\label{tab:kruskal_${activeTab}_run_${runId}}`,
      ];

      // Column spec
      const colSpec: string[] = selectedCols.map(col => LATEX_COLUMN_DEFS[col]);
      lines.push(`\\begin{tabular}{${colSpec.join('')}}`);
      lines.push('\\toprule');

      // Header row
      const headerCols: string[] = selectedCols.map(col => LATEX_COLUMN_HEADERS[col]);
      lines.push(headerCols.join(' & ') + ' \\\\');
      lines.push('\\midrule');

      // Data rows
      catData.attributes.forEach(attr => {
        const cols: string[] = [];
        if (selectedColumns.has('attribute')) cols.push(ATTR_LABELS[attr.attribute] || attr.attribute);
        if (selectedColumns.has('h_stat')) cols.push(attr.h_stat?.toFixed(2) ?? '—');
        if (selectedColumns.has('p_value')) cols.push(formatPValueForLatex(attr.p_value));
        if (selectedColumns.has('sig')) cols.push(attr.significant ? getSignificanceStars(attr.p_value) : 'n.s.');
        if (selectedColumns.has('eta_squared')) cols.push(attr.eta_squared?.toFixed(4) ?? '—');
        if (selectedColumns.has('effect')) cols.push(attr.effect_interpretation);
        if (selectedColumns.has('n_groups')) cols.push(String(attr.n_groups ?? '—'));
        if (selectedColumns.has('n_total')) cols.push(String(attr.n_total ?? '—'));
        lines.push(cols.join(' & ') + ' \\\\');
      });

      lines.push('\\bottomrule');
      lines.push('\\end{tabular}');
      lines.push('\\end{table}');

      const latex = lines.join('\n');
      await navigator.clipboard.writeText(latex);
      
      notifications.show({
        title: 'LaTeX kopiert',
        message: `Die LaTeX-Tabelle für ${categoryLabel} wurde kopiert.`,
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
              <Title order={5}>Kruskal-Wallis Tests</Title>
              <Text size="sm" c="dimmed">
                Gruppenunterschiede nach demografischen Merkmalen
              </Text>
            </div>
          </Group>
          <Group gap="xs">
            <Tooltip label="CSV der aktiven Kategorie herunterladen" withArrow>
              <Button
                variant="light"
                size="xs"
                leftSection={<IconDownload size={16} />}
                onClick={handleDownloadCSV}
              >
                CSV
              </Button>
            </Tooltip>
            <Tooltip label="LaTeX-Tabelle der aktiven Kategorie kopieren" withArrow>
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

        {/* Column Selection Hint */}
        <Paper p="xs" bg={getColor('blue').bg} radius="sm">
          <Text size="xs" c="dimmed">
            💡 Tipp: Klicke auf die Checkboxen in den Spaltenüberschriften, um Spalten für den CSV/LaTeX-Export auszuwählen.
          </Text>
        </Paper>

        {/* Overall Summary Badge */}
        <Group>
          <Badge 
            color={totalSignificant > 0 ? 'green' : 'gray'} 
            variant="light" 
            size="lg"
          >
            Gesamt: {totalSignificant} / {totalTests} Tests signifikant
          </Badge>
          <Text size="xs" c="dimmed">
            über alle Kategorien
          </Text>
        </Group>

        {/* Tabs per Trait Category */}
        <Tabs value={activeTab || categoryKeys[0]} onChange={setActiveTab}>
          <Tabs.List>
            {categoryKeys.map((catKey) => {
              const catData = allCategories[catKey];
              const label = CATEGORY_LABELS[catKey] || catKey;
              const hasSignificant = catData.summary.significant_count > 0;
              
              return (
                <Tabs.Tab 
                  key={catKey} 
                  value={catKey}
                  rightSection={
                    hasSignificant ? (
                      <Badge color="green" variant="filled" size="xs" circle>
                        {catData.summary.significant_count}
                      </Badge>
                    ) : undefined
                  }
                >
                  {label}
                </Tabs.Tab>
              );
            })}
          </Tabs.List>

          {categoryKeys.map((catKey) => {
            const catData = allCategories[catKey];
            return (
              <Tabs.Panel key={catKey} value={catKey} pt="md">
                <Stack gap="md">
                  {/* Category Summary */}
                  <Group>
                    <Badge 
                      color={catData.summary.significant_count > 0 ? 'green' : 'gray'} 
                      variant="light"
                    >
                      {catData.summary.significant_count} / {catData.summary.total} signifikant
                    </Badge>
                    <Text size="sm" c="dimmed">
                      (p &lt; 0.05)
                    </Text>
                  </Group>

                  {/* Table */}
                  <KruskalTable 
                    data={catData} 
                    selectedColumns={selectedColumns}
                    onToggleColumn={toggleColumn}
                  />
                </Stack>
              </Tabs.Panel>
            );
          })}
        </Tabs>

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
