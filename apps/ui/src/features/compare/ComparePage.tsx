import { Card, Group, MultiSelect, Title } from '@mantine/core';
import { useState } from 'react';
import { useMetrics, useModels, useDatasets } from './hooks';
import { ChartPanel } from '../../components/ChartPanel';

export function ComparePage() {
    const [datasets, setDatasets] = useState<string[]>([]);
    const [selectedModels, setSelectedModels] = useState<string[]>([]);
    const { data: availableModels } = useModels();
    const { data: availableDatasets } = useDatasets();
    const { data, isLoading } = useMetrics(selectedModels, datasets);
    

    const bars: Partial<Plotly.Data>[] = data ? [
        {
            type: 'bar',
            x: data.hist.bins,
            y: data.hist.shares,
        },
    ] : [];

    return (
        <Card>
        <Title order={2} mb="md">Vergleich</Title>
        <Group mb="md">
            <MultiSelect label="Modelle" data={availableModels || []} value={selectedModels} onChange={setSelectedModels} searchable clearable />
            <MultiSelect label="Datasets" data={availableDatasets?.map(d => ({ value: d.id.toString(), label: d.name })) || []} value={datasets} onChange={setDatasets} searchable clearable />
        </Group>
        {isLoading ? (
            <div>Loading...</div>
        ) : data && data.hist.bins.length > 0 ? (
            <ChartPanel title="Rating Distribution" data={bars} />
        ) : (
            <div>Keine Daten verfügbar.</div>
        )}
        </Card>
    );
}