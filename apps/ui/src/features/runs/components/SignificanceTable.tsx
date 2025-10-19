import { useState, Fragment } from 'react';
import { Table, Group, ActionIcon, Collapse, Text, Badge } from '@mantine/core';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';

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

function fmt(num: number | null | undefined, digits = 2) {
  return Number.isFinite(num as number) ? (num as number).toFixed(digits) : '—';
}

export function SignificanceTable({ rows }: { rows: Row[] }) {
  const [open, setOpen] = useState<Record<string, boolean>>({});
  if (!rows || rows.length === 0) return <div>—</div>;

  return (
    <Table striped withTableBorder withColumnBorders highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th style={{ width: 340 }}>Kategorie</Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>n</Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>Mittel</Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>Delta</Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>p</Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>q</Table.Th>
          <Table.Th style={{ textAlign: 'right' }}>Cliff’s δ</Table.Th>
          <Table.Th style={{ textAlign: 'center' }}>Sig</Table.Th>
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
  );
}
