import Plot from 'react-plotly.js';
import { useComputedColorScheme } from '@mantine/core';
import { useMemo } from 'react';

type ChartPanelProps = {
    title?: string;
    data: Partial<Plotly.Data>[];
    layout?: Partial<Plotly.Layout>;
    height?: number;
};

// Dark mode color palette for Plotly
const darkModeColors = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#c1c2c5' },
    gridcolor: 'rgba(255,255,255,0.1)',
    linecolor: 'rgba(255,255,255,0.2)',
    zerolinecolor: 'rgba(255,255,255,0.2)',
};

const lightModeColors = {
    paper_bgcolor: 'rgba(255,255,255,0)',
    plot_bgcolor: 'rgba(255,255,255,0)',
    font: { color: '#212529' },
    gridcolor: 'rgba(0,0,0,0.1)',
    linecolor: 'rgba(0,0,0,0.1)',
    zerolinecolor: 'rgba(0,0,0,0.2)',
};

export function ChartPanel({ title, data, layout, height }: ChartPanelProps) {
    const colorScheme = useComputedColorScheme('light');
    const isDark = colorScheme === 'dark';
    const colors = isDark ? darkModeColors : lightModeColors;

    const themedLayout = useMemo<Partial<Plotly.Layout>>(() => ({
        autosize: true,
        margin: { t: 24, ...(layout?.margin || {}) },
        paper_bgcolor: colors.paper_bgcolor,
        plot_bgcolor: colors.plot_bgcolor,
        font: colors.font,
        xaxis: {
            gridcolor: colors.gridcolor,
            linecolor: colors.linecolor,
            zerolinecolor: colors.zerolinecolor,
            ...(layout?.xaxis || {}),
        },
        yaxis: {
            gridcolor: colors.gridcolor,
            linecolor: colors.linecolor,
            zerolinecolor: colors.zerolinecolor,
            ...(layout?.yaxis || {}),
        },
        legend: {
            font: colors.font,
            ...(layout?.legend || {}),
        },
        ...layout,
        // Ensure colors are applied last to override any layout settings
        ...(isDark ? {
            paper_bgcolor: colors.paper_bgcolor,
            plot_bgcolor: colors.plot_bgcolor,
        } : {}),
    }), [colors, layout, isDark]);

    return (
        <div>
            {title && <h3 style={{ marginBottom: 8, color: isDark ? '#c1c2c5' : '#212529' }}>{title}</h3>}
            <Plot
                data={data}
                layout={themedLayout}
                style={{ width: '100%', height: height ? `${height}px` : '420px' }}
                useResizeHandler
                config={{ 
                    displayModeBar: true,
                    displaylogo: false,
                }}
            />
        </div>
    );
}
