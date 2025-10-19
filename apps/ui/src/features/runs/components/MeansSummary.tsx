import { Table } from '@mantine/core';

type MeanRow = { category: string; count: number; mean: number };

export function MeansSummary({
  items,
  getLabel,
}: {
  items: Array<{ key: string; rows?: MeanRow[] }>;
  getLabel: (key: string) => string;
}) {
  return (
    <>
      {items.map(({ key, rows }) => (
        <div key={key} style={{ marginTop: 12 }}>
          <b>{getLabel(key)}</b>
          {rows && rows.length > 0 ? (
            <div style={{ overflowX: 'auto', marginTop: 6 }}>
              <Table striped withTableBorder withColumnBorders highlightOnHover>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Kategorie</Table.Th>
                    <Table.Th style={{ textAlign: 'right' }}>n</Table.Th>
                    <Table.Th style={{ textAlign: 'right' }}>Mittel</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {rows.map((r) => (
                    <Table.Tr key={r.category}>
                      <Table.Td>{r.category}</Table.Td>
                      <Table.Td style={{ textAlign: 'right' }}>{r.count}</Table.Td>
                      <Table.Td style={{ textAlign: 'right' }}>{Number.isFinite(r.mean as number) ? r.mean.toFixed(2) : '—'}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </div>
          ) : (
            <div>—</div>
          )}
        </div>
      ))}
    </>
  );
}
