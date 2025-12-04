// Shared small helpers for building Plotly traces

export function toBar(items: Array<{ value: string; count: number }>, opts?: { horizontal?: boolean; color?: string }) {
  const labels = items.map((d) => d.value);
  const values = items.map((d) => d.count);
  return [{
    type: 'bar',
    x: opts?.horizontal ? values : labels,
    y: opts?.horizontal ? labels : values,
    orientation: opts?.horizontal ? 'h' : undefined,
    marker: opts?.color ? { color: opts.color } : undefined,
  } as Partial<Plotly.Data>];
}

export function toPie(items: Array<{ value: string; count: number }>, opts?: { hole?: number; colors?: string[]; legendOnly?: boolean }) {
  return [{
    type: 'pie',
    labels: items.map((d) => d.value),
    values: items.map((d) => d.count),
    hole: opts?.hole ?? 0,
    marker: opts?.colors ? { colors: opts.colors } : undefined,
    textinfo: opts?.legendOnly ? 'percent' as const : 'label+percent' as const,
    textposition: 'inside',
  } as Partial<Plotly.Data>];
}

export function toDonut(items: Array<{ value: string; count: number }>, opts?: { colors?: string[]; legendOnly?: boolean }) {
  return toPie(items, { hole: 0.4, ...opts });
}

// Color palettes
export const CHART_COLORS = {
  gender: ['#228be6', '#fa5252', '#40c057'], // blue, red, green
  sexuality: ['#7950f2', '#be4bdb', '#e64980'], // violet shades
  religion: ['#fab005', '#fd7e14', '#e8590c', '#d9480f', '#c92a2a', '#a61e4d', '#862e9c'],
  education: ['#12b886', '#20c997', '#38d9a9', '#63e6be', '#96f2d7', '#c3fae8'],
  marriage: ['#4c6ef5', '#748ffc', '#91a7ff', '#bac8ff', '#dbe4ff'],
  region: ['#228be6', '#15aabf', '#12b886', '#40c057', '#82c91e', '#fab005', '#fd7e14'],
};