// Shared small helpers for building Plotly traces

export function toBar(items: Array<{ value: string; count: number }>, opts?: { horizontal?: boolean }) {
  const labels = items.map((d) => d.value);
  const values = items.map((d) => d.count);
  return [{
    type: 'bar',
    x: opts?.horizontal ? values : labels,
    y: opts?.horizontal ? labels : values,
    orientation: opts?.horizontal ? 'h' : undefined,
  } as Partial<Plotly.Data>];
}

