import { useState, Fragment } from 'react';
import { Table, Group, ActionIcon, Collapse, Text, Badge, Button, Tooltip, Checkbox, Paper } from '@mantine/core';
import { IconChevronDown, IconChevronRight, IconDownload, IconCopy } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';

type Row = {
  category: string;
  count?: number;
  mean?: number;
  delta?: number;
  p_value?: number;
  significant?: boolean;
  // optional fields present in some responses
  q_value?: number | null;
  cliffs_delta?: number | null;
  // details for collapsible section (if available)
  n_base?: number; sd_base?: number | null; mean_base?: number | null;
  n_cat?: number; sd_cat?: number | null; mean_cat?: number | null;
  se_delta?: number | null; ci_low?: number | null; ci_high?: number | null;
};

type ColumnKey = 'category' | 'n' | 'mean' | 'delta' | 'p_value' | 'q_value' | 'cliffs_delta' | 'sig';

function fmt(num: number | null | undefined, digits = 2) {
  return Number.isFinite(num as number) ? (num as number).toFixed(digits) : '—';
}

export function SignificanceTable({ 
  rows, 
  runId, 
  attribute, 
  baseline, 
  traitCategory 
}: { 
  rows: Row[];
  runId?: number;
  attribute?: string;
  baseline?: string;
  traitCategory?: string;
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [selectedColumns, setSelectedColumns] = useState<Set<ColumnKey>>(
    new Set(['category', 'n', 'mean', 'delta', 'p_value', 'q_value', 'cliffs_delta', 'sig'])
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
  
  const handleDownloadCSV = () => {
    if (!runId || !attribute) return;
    
    // Build CSV with selected columns
    const csvRows: string[][] = [];
    
    // Header
    const header: string[] = [];
    if (selectedColumns.has('category')) header.push('Kategorie');
    if (selectedColumns.has('n')) header.push('n');
    if (selectedColumns.has('mean')) header.push('Mittel');
    if (selectedColumns.has('delta')) header.push('Delta');
    if (selectedColumns.has('p_value')) header.push('p-Wert');
    if (selectedColumns.has('q_value')) header.push('q-Wert');
    if (selectedColumns.has('cliffs_delta')) header.push("Cliff's δ");
    if (selectedColumns.has('sig')) header.push('Signifikant');
    csvRows.push(header);

    // Data rows
    rows.forEach(r => {
      const row: string[] = [];
      if (selectedColumns.has('category')) row.push(r.category || '');
      if (selectedColumns.has('n')) row.push(String(r.count ?? ''));
      if (selectedColumns.has('mean')) row.push(fmt(r.mean));
      if (selectedColumns.has('delta')) row.push(fmt(r.delta, 3));
      if (selectedColumns.has('p_value')) row.push(fmt(r.p_value, 6));
      if (selectedColumns.has('q_value')) row.push(fmt(r.q_value, 6));
      if (selectedColumns.has('cliffs_delta')) row.push(fmt(r.cliffs_delta, 3));
      if (selectedColumns.has('sig')) row.push(r.significant ? 'Ja' : 'Nein');
      csvRows.push(row);
    });

    // Generate CSV
    const csvContent = csvRows.map(row => row.map(cell => {
      if (cell.includes(',') || cell.includes('"') || cell.includes('\n')) {
        return `"${cell.replace(/"/g, '""')}"`;
      }
      return cell;
    }).join(',')).join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    const trait_suffix = traitCategory ? `_${traitCategory}` : '';
    const baseline_suffix = baseline ? `_vs_${baseline}` : '';
    link.download = `deltas_${attribute}_run_${runId}${trait_suffix}${baseline_suffix}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  };

  const handleCopyLatex = async () => {
    if (!runId || !attribute) return;
    
    try {
      // Build LaTeX table with selected columns
      const lines: string[] = [
        '\\begin{table}[htbp]',
        '\\centering',
      ];

      const trait_suffix = traitCategory ? ` (${traitCategory})` : '';
      const baseline_suffix = baseline ? ` vs. ${baseline}` : '';
      lines.push(`\\caption{Signifikanztabelle: ${attribute}${trait_suffix}${baseline_suffix} (Run ${runId})}`);
      lines.push(`\\label{tab:deltas_${attribute}_run_${runId}}`);

      // Column spec
      const colSpec: string[] = [];
      if (selectedColumns.has('category')) colSpec.push('l');
      if (selectedColumns.has('n')) colSpec.push('r');
      if (selectedColumns.has('mean')) colSpec.push('r');
      if (selectedColumns.has('delta')) colSpec.push('r');
      if (selectedColumns.has('p_value')) colSpec.push('r');
      if (selectedColumns.has('q_value')) colSpec.push('r');
      if (selectedColumns.has('cliffs_delta')) colSpec.push('r');
      if (selectedColumns.has('sig')) colSpec.push('l');

      lines.push(`\\begin{tabular}{${colSpec.join('')}}`);
      lines.push('\\toprule');

      // Header
      const headerCols: string[] = [];
      if (selectedColumns.has('category')) headerCols.push('Kategorie');
      if (selectedColumns.has('n')) headerCols.push('n');
      if (selectedColumns.has('mean')) headerCols.push('Mittel');
      if (selectedColumns.has('delta')) headerCols.push('$\\Delta$');
      if (selectedColumns.has('p_value')) headerCols.push('p-Wert');
      if (selectedColumns.has('q_value')) headerCols.push('q-Wert');
      if (selectedColumns.has('cliffs_delta')) headerCols.push("Cliff's $\\delta$");
      if (selectedColumns.has('sig')) headerCols.push('Signifikant');
      lines.push(headerCols.join(' & ') + ' \\\\');
      lines.push('\\midrule');

      // Data rows
      rows.forEach(r => {
        const cols: string[] = [];
        if (selectedColumns.has('category')) cols.push(r.category || '');
        if (selectedColumns.has('n')) cols.push(String(r.count ?? '—'));
        if (selectedColumns.has('mean')) cols.push(fmt(r.mean));
        if (selectedColumns.has('delta')) cols.push(fmt(r.delta, 3));
        if (selectedColumns.has('p_value')) cols.push(fmt(r.p_value, 6));
        if (selectedColumns.has('q_value')) cols.push(fmt(r.q_value, 6));
        if (selectedColumns.has('cliffs_delta')) cols.push(fmt(r.cliffs_delta, 3));
        if (selectedColumns.has('sig')) cols.push(r.significant ? 'Ja' : 'Nein');
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
  
  if (!rows || rows.length === 0) return <div>—</div>;

  return (
    <div>
      {runId && attribute && (
        <Group justify="flex-end" mb="xs">
          <Tooltip label="Als CSV herunterladen" withArrow>
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconDownload size={14} />}
              onClick={handleDownloadCSV}
            >
              CSV
            </Button>
          </Tooltip>
          <Tooltip label="LaTeX-Tabelle in Zwischenablage kopieren" withArrow>
            <Button
              variant="subtle"
              size="xs"
              leftSection={<IconCopy size={14} />}
              onClick={handleCopyLatex}
            >
              LaTeX
            </Button>
          </Tooltip>
        </Group>
      )}
      {runId && attribute && (
        <Paper p="xs" mb="xs" bg="blue.0" style={{ backgroundColor: 'var(--mantine-color-blue-0)' }}>
          <Text size="xs" c="dimmed">
            💡 Tipp: Nutze die Checkboxen in den Spaltenüberschriften, um Spalten für den Export auszuwählen.
          </Text>
        </Paper>
      )}
      <Table striped withTableBorder withColumnBorders highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th style={{ width: 340 }}>
            <Group gap={4}>
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('category')}
                onChange={() => toggleColumn('category')}
                aria-label="Spalte Kategorie für Export auswählen"
              />
              <span>Kategorie</span>
            </Group>
          </Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>
            <Group gap={4} justify="flex-end">
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('n')}
                onChange={() => toggleColumn('n')}
                aria-label="Spalte n für Export auswählen"
              />
              <span>n</span>
            </Group>
          </Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>
            <Group gap={4} justify="flex-end">
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('mean')}
                onChange={() => toggleColumn('mean')}
                aria-label="Spalte Mittel für Export auswählen"
              />
              <span>Mittel</span>
            </Group>
          </Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>
            <Group gap={4} justify="flex-end">
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('delta')}
                onChange={() => toggleColumn('delta')}
                aria-label="Spalte Delta für Export auswählen"
              />
              <span>Delta</span>
            </Group>
          </Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>
            <Group gap={4} justify="flex-end">
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('p_value')}
                onChange={() => toggleColumn('p_value')}
                aria-label="Spalte p für Export auswählen"
              />
              <span>p</span>
            </Group>
          </Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>
            <Group gap={4} justify="flex-end">
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('q_value')}
                onChange={() => toggleColumn('q_value')}
                aria-label="Spalte q für Export auswählen"
              />
              <span>q</span>
            </Group>
          </Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>
            <Group gap={4} justify="flex-end">
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('cliffs_delta')}
                onChange={() => toggleColumn('cliffs_delta')}
                aria-label="Spalte Cliff's δ für Export auswählen"
              />
              <span>Cliff's δ</span>
            </Group>
          </Table.Th>
          <Table.Th style={{ textAlign: 'center' }}>
            <Group gap={4} justify="center">
              <Checkbox 
                size="xs" 
                checked={selectedColumns.has('sig')}
                onChange={() => toggleColumn('sig')}
                aria-label="Spalte Sig für Export auswählen"
              />
              <span>Sig</span>
            </Group>
          </Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {rows.map((r) => {
          const isOpen = !!open[r.category];
          return (
            <Fragment key={r.category}>
              <Table.Tr>
                <Table.Td>
                  <Group gap="xs">
                    <ActionIcon
                      size="sm"
                      variant="subtle"
                      onClick={() => setOpen((s) => ({ ...s, [r.category]: !s[r.category] }))}
                      aria-label={isOpen ? 'Details verbergen' : 'Details anzeigen'}
                    >
                      {isOpen ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
                    </ActionIcon>
                    <Text>{r.category}</Text>
                  </Group>
                </Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>{r.count ?? '—'}</Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>{fmt(r.mean)}</Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>{fmt(r.delta)}</Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>{fmt(r.p_value, 3)}</Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>{fmt(r.q_value, 3)}</Table.Td>
                <Table.Td style={{ textAlign: 'right' }}>{fmt(r.cliffs_delta)}</Table.Td>
                <Table.Td style={{ textAlign: 'center' }}>{r.significant ? <Badge color="green" variant="light" size="sm">sig</Badge> : ''}</Table.Td>
              </Table.Tr>
              <Table.Tr style={{ display: isOpen ? undefined : 'none' }}>
                <Table.Td colSpan={8}>
                  <Collapse in={isOpen}>
                    <div style={{ padding: '8px 4px' }}>
                      <Text size="sm" c="dimmed" mb={6}>Details</Text>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(140px, 1fr))', gap: 8 }}>
                        <div>
                          <Text size="xs" fw={600}>Baseline</Text>
                          <Text size="xs">n: {r.n_base ?? '—'}</Text>
                          <Text size="xs">Mittel: {fmt(r.mean_base)}</Text>
                          <Text size="xs">SD: {fmt(r.sd_base)}</Text>
                        </div>
                        <div>
                          <Text size="xs" fw={600}>Kategorie</Text>
                          <Text size="xs">n: {r.n_cat ?? '—'}</Text>
                          <Text size="xs">Mittel: {fmt(r.mean_cat)}</Text>
                          <Text size="xs">SD: {fmt(r.sd_cat)}</Text>
                        </div>
                        <div>
                          <Text size="xs" fw={600}>Effekt</Text>
                          <Text size="xs">Δ: {fmt(r.delta)}</Text>
                          <Text size="xs">SE: {fmt(r.se_delta)}</Text>
                          <Text size="xs">95% CI: {Number.isFinite(r.ci_low as number) || Number.isFinite(r.ci_high as number) ? `[${fmt(r.ci_low)}, ${fmt(r.ci_high)}]` : '—'}</Text>
                        </div>
                      </div>
                    </div>
                  </Collapse>
                </Table.Td>
              </Table.Tr>
            </Fragment>
          );
        })}
      </Table.Tbody>
    </Table>
    </div>
  );
}
