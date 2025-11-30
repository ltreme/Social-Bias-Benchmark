import { useMemo, useState } from 'react';
import { ActionIcon, Badge, Card, Group, MultiSelect, Select, TextInput, Title, Tooltip } from '@mantine/core';
import { useNavigate } from '@tanstack/react-router';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useRuns } from './hooks';
import type { Run } from './api';
import { IconExternalLink, IconMessage, IconMessageCog, IconSearch } from '@tabler/icons-react';

// Helper to format date nicely
function formatDate(dateStr?: string | null): string {
    if (!dateStr) return '–';
    const d = new Date(dateStr);
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

// Helper to format large numbers compactly
function formatCompactNumber(n: number): string {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(n % 1_000_000 === 0 ? 0 : 1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(n % 1_000 === 0 ? 0 : 1)}K`;
    return String(n);
}

export function RunsPage() {
    const navigate = useNavigate();
    const { data: runs = [], isLoading } = useRuns();
    
    // Filter states
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedModels, setSelectedModels] = useState<string[]>([]);
    const [selectedDatasets, setSelectedDatasets] = useState<string[]>([]);
    const [rationaleFilter, setRationaleFilter] = useState<string | null>(null);
    const [systemPromptFilter, setSystemPromptFilter] = useState<string | null>(null);

    // Extract unique values for filters
    const availableModels = useMemo(() => 
        [...new Set(runs.map(r => r.model_name))].sort(),
    [runs]);
    
    const availableDatasets = useMemo(() => {
        const datasets = runs
            .filter(r => r.dataset_id)
            .map(r => ({ id: r.dataset_id!, name: `Dataset #${r.dataset_id}` }));
        const unique = [...new Map(datasets.map(d => [d.id, d])).values()];
        return unique.sort((a, b) => a.id - b.id);
    }, [runs]);

    // Filter runs
    const filteredRuns = useMemo(() => {
        return runs.filter(run => {
            // Search filter (model name)
            if (searchQuery && !run.model_name.toLowerCase().includes(searchQuery.toLowerCase())) {
                return false;
            }
            // Model filter
            if (selectedModels.length > 0 && !selectedModels.includes(run.model_name)) {
                return false;
            }
            // Dataset filter
            if (selectedDatasets.length > 0 && !selectedDatasets.includes(String(run.dataset_id))) {
                return false;
            }
            // Rationale filter
            if (rationaleFilter === 'yes' && !run.include_rationale) return false;
            if (rationaleFilter === 'no' && run.include_rationale) return false;
            // System prompt filter
            if (systemPromptFilter === 'yes' && !run.system_prompt) return false;
            if (systemPromptFilter === 'no' && run.system_prompt) return false;
            
            return true;
        });
    }, [runs, searchQuery, selectedModels, selectedDatasets, rationaleFilter, systemPromptFilter]);

    const columns: ColumnDef<Run>[] = [
        { 
            header: 'ID', 
            accessorKey: 'id', 
            cell: ({ row }) => <span style={{ color: '#868e96' }}>#{row.original.id}</span> 
        },
        { 
            header: 'Modell', 
            accessorKey: 'model_name',
            cell: ({ row }) => (
                <span style={{ fontWeight: 500 }}>{row.original.model_name}</span>
            )
        },
        {
            header: 'Dataset',
            accessorKey: 'dataset_id',
            cell: ({ row }) => row.original.dataset_id 
                ? <Badge variant="light" color="blue">#{row.original.dataset_id}</Badge>
                : <span style={{ color: '#adb5bd' }}>–</span>
        },
        {
            header: 'Optionen',
            accessorKey: 'options',
            cell: ({ row }) => (
                <Group gap={6} wrap="nowrap">
                    {row.original.include_rationale && (
                        <Tooltip label="Mit Begründungen" withArrow>
                            <IconMessage size={18} color="#228be6" />
                        </Tooltip>
                    )}
                    {row.original.system_prompt && (
                        <Tooltip label="Custom System Prompt" withArrow>
                            <IconMessageCog size={18} color="#fd7e14" />
                        </Tooltip>
                    )}
                    {!row.original.include_rationale && !row.original.system_prompt && (
                        <span style={{ color: '#adb5bd' }}>–</span>
                    )}
                </Group>
            ),
        },
        {
            header: 'Ergebnisse',
            accessorKey: 'n_results',
            cell: ({ row }) => (
                <Tooltip label={row.original.n_results.toLocaleString('de-DE')} withArrow>
                    <span>{formatCompactNumber(row.original.n_results)}</span>
                </Tooltip>
            )
        },
        { 
            header: 'Erstellt', 
            accessorKey: 'created_at', 
            cell: ({ row }) => (
                <span style={{ color: '#495057' }}>{formatDate(row.original.created_at)}</span>
            )
        },
        { 
            header: '', 
            accessorKey: 'actions', 
            cell: ({ row }) => (
                <Tooltip label="Run Details" withArrow>
                    <ActionIcon 
                        variant="light" 
                        onClick={() => navigate({ to: '/runs/$runId', params: { runId: String(row.original.id) } })}
                    >
                        <IconExternalLink size={16} />
                    </ActionIcon>
                </Tooltip>
            ) 
        },
    ];

    const hasActiveFilters = selectedModels.length > 0 || selectedDatasets.length > 0 || rationaleFilter || systemPromptFilter;

    return (
        <Card>
            <Group justify="space-between" mb="md">
                <Group gap="sm">
                    <Title order={2}>Benchmark Runs</Title>
                    {hasActiveFilters && (
                        <Badge variant="light" color="blue">{filteredRuns.length} von {runs.length}</Badge>
                    )}
                </Group>
                <TextInput
                    placeholder="Modell suchen…"
                    leftSection={<IconSearch size={16} />}
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    style={{ width: 220 }}
                />
            </Group>

            {/* Filter Row */}
            <Group mb="md" gap="sm">
                <MultiSelect
                    placeholder="Modelle"
                    data={availableModels}
                    value={selectedModels}
                    onChange={setSelectedModels}
                    clearable
                    searchable
                    style={{ minWidth: 200 }}
                />
                <MultiSelect
                    placeholder="Datasets"
                    data={availableDatasets.map(d => ({ value: String(d.id), label: d.name }))}
                    value={selectedDatasets}
                    onChange={setSelectedDatasets}
                    clearable
                    searchable
                    style={{ minWidth: 160 }}
                />
                <Select
                    placeholder="Begründungen"
                    data={[
                        { value: 'yes', label: 'Mit Begründungen' },
                        { value: 'no', label: 'Ohne Begründungen' },
                    ]}
                    value={rationaleFilter}
                    onChange={setRationaleFilter}
                    clearable
                    style={{ minWidth: 160 }}
                />
                <Select
                    placeholder="System Prompt"
                    data={[
                        { value: 'yes', label: 'Custom Prompt' },
                        { value: 'no', label: 'Standard Prompt' },
                    ]}
                    value={systemPromptFilter}
                    onChange={setSystemPromptFilter}
                    clearable
                    style={{ minWidth: 160 }}
                />
            </Group>

            {isLoading ? 'Laden…' : <DataTable data={filteredRuns} columns={columns} />}
        </Card>
    );
}
