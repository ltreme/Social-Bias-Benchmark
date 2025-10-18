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
        <div key={key} style={{ marginTop: 8 }}>
          <b>{getLabel(key)}</b>
          <div style={{ fontFamily: 'monospace' }}>
            {rows && rows.length > 0 ? rows.map((r) => `${r.category}: mean=${r.mean.toFixed(2)} (n=${r.count})`).join(' · ') : '—'}
          </div>
        </div>
      ))}
    </>
  );
}

