type Row = {
  category: string;
  count?: number;
  mean?: number;
  delta?: number;
  p_value?: number;
  significant?: boolean;
  // optional fields present in some responses
  q_value?: number;
  cliffs_delta?: number;
};

export function SignificanceTable({ rows }: { rows: Row[] }) {
  if (!rows || rows.length === 0) return <div>—</div>;
  return (
    <div style={{ overflowX:'auto' }}>
      <table style={{ width:'100%', borderCollapse:'collapse' }}>
        <thead>
          <tr>
            <th style={{ textAlign:'left' }}>Kategorie</th>
            <th style={{ textAlign:'right' }}>n</th>
            <th style={{ textAlign:'right' }}>Mittel</th>
            <th style={{ textAlign:'right' }}>Delta</th>
            <th style={{ textAlign:'right' }}>p</th>
            <th style={{ textAlign:'right' }}>q</th>
            <th style={{ textAlign:'right' }}>Cliff’s δ</th>
            <th style={{ textAlign:'center' }}>Sig</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.category}>
              <td>{r.category}</td>
              <td style={{ textAlign:'right' }}>{r.count}</td>
              <td style={{ textAlign:'right' }}>{Number.isFinite(r.mean as number) ? (r.mean as number).toFixed(2) : '—'}</td>
              <td style={{ textAlign:'right' }}>{Number.isFinite(r.delta as number) ? (r.delta as number).toFixed(2) : '—'}</td>
              <td style={{ textAlign:'right' }}>{Number.isFinite(r.p_value as number) ? (r.p_value as number).toFixed(3) : '—'}</td>
              <td style={{ textAlign:'right' }}>{Number.isFinite((r as any).q_value as number) ? ((r as any).q_value as number).toFixed(3) : '—'}</td>
              <td style={{ textAlign:'right' }}>{Number.isFinite((r as any).cliffs_delta as number) ? ((r as any).cliffs_delta as number).toFixed(2) : '—'}</td>
              <td style={{ textAlign:'center' }}>{r.significant ? 'yes' : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

