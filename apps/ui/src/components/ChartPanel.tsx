import Plot from 'react-plotly.js';

type ChartPanelProps = {
    title?: string;
    data: Partial<Plotly.Data>[];
    layout?: Partial<Plotly.Layout>;
};

export function ChartPanel({ title, data, layout }: ChartPanelProps) {
    return (
        <div>
            {title && <h3 style={{ marginBottom: 8 }}>{title}</h3>}
            <Plot data={data} layout={{ autosize: true, margin: { t: 24 }, ...layout }} style={{ width: '100%', height: '420px' }} useResizeHandler />
        </div>
    );
}