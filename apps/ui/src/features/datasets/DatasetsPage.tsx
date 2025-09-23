import { useState } from 'react';
import { Card, Title } from '@mantine/core';
import { useDatasets } from './hooks';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import type { Dataset } from './api';

export function DatasetsPage() {
    const [q, setQ] = useState<string | undefined>();
    const { data = [], isLoading } = useDatasets(q);

    const columns: ColumnDef<Dataset>[] = [
        { header: 'ID', accessorKey: 'id' },
        { header: 'Name', accessorKey: 'name' },
        { header: 'Size', accessorKey: 'size' },
        { header: 'Art', accessorKey: 'kind' },
    ];

    return (
        <Card>
        <Title order={2} mb="md">Datasets</Title>
        {/* simple input instead of Filters for brevity */}
        <input placeholder="Search…" onChange={(e) => setQ(e.target.value)} />
        {isLoading ? 'Laden…' : <DataTable data={data} columns={columns} />}
        </Card>
    );
}