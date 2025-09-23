import { Card, Group, MultiSelect, Title } from '@mantine/core';
import { useState, useEffect } from 'react';
import { useMetrics } from './hooks';
import { ChartPanel } from '../../components/ChartPanel';

export function ComparePage() {
    const [models, setModels] = useState<string[]>([]);
    const [datasets, setDatasets] = useState<string[]>([]);
    const [availableDatasets, setAvailableDatasets] = useState<any[]>([]);
    const [availableModels, setAvailableModels] = useState<any[]>([]);
    const { data, isLoading } = useMetrics(models, datasets);

    useEffect(() => {
        fetch('/datasets')
            .then(res => res.json())
            .then(setAvailableDatasets)
            .catch(console.error);
    }, []);

    useEffect(() => {
        fetch('/runs')
            .then(res => res.json())
            .then(runs => setAvailableModels([...new Set(runs.map((r: any) => r.model_name))]))
            .catch(console.error);
    }, []);

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
            <MultiSelect label="Modelle" data={availableModels} value={models} onChange={setModels} searchable clearable />
            <MultiSelect label="Datasets" data={availableDatasets.map(d => ({ value: d.id.toString(), label: d.name }))} value={datasets} onChange={setDatasets} searchable clearable />
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