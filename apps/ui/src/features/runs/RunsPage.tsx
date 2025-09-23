import { Button, Card, Group, TextInput, Title } from '@mantine/core';
import { useRuns, useStartRun } from './hooks';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import type { Run } from './api';
import { useState } from 'react';

export function RunsPage() {
    const { data = [], isLoading } = useRuns();
    const cols: ColumnDef<Run>[] = [
        { header: 'ID', accessorKey: 'id' },
        { header: 'Model', accessorKey: 'model_name' },
        { header: 'With Rationale', accessorKey: 'include_rationale' },
        { header: 'GenID', accessorKey: 'gen_id' },
        { header: 'Created', accessorKey: 'created_at' },
    ];

    const start = useStartRun();
    const [model, setModel] = useState('Qwen/Qwen2.5-1.5B-Instruct');
    const [dataset, setDataset] = useState('pool-20250919');

    return (
        <Card>
        <Title order={2} mb="md">Runs</Title>
        <Group mb="md">
            <TextInput label="Model" value={model} onChange={(e) => setModel(e.currentTarget.value)} />
            <TextInput label="Dataset" value={dataset} onChange={(e) => setDataset(e.currentTarget.value)} />
            <Button loading={start.isPending} onClick={() => start.mutate({ model_name: model, dataset_id: dataset })}>Run starten</Button>
        </Group>
        {isLoading ? 'Laden…' : <DataTable data={data} columns={cols} />}
        </Card>
    );
}