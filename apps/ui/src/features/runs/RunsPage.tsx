import { useMemo, useState } from 'react';
import { ActionIcon, Badge, Card, Group, MultiSelect, Select, Text, TextInput, Title, Tooltip, useComputedColorScheme, Button, Checkbox } from '@mantine/core';
import { Link, useNavigate } from '@tanstack/react-router';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useRuns } from './hooks';
import type { Run } from './api';
import { IconExternalLink, IconMessage, IconMessageCog, IconSearch, IconPlayerPlay, IconFilter, IconCpu, IconDatabase, IconMessageCircle, IconSettings, IconScale } from '@tabler/icons-react';

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
    const { data: runs = [], isLoading } = useRuns();
    const navigate = useNavigate();
    const colorScheme = useComputedColorScheme('light');
    const isDark = colorScheme === 'dark';
    
    // Selection state
    const [selectedRunIds, setSelectedRunIds] = useState<number[]>([]);
    
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
            id: 'select',
            header: ({ table }) => (
                <Checkbox
                    checked={table.getIsAllRowsSelected()}
                    indeterminate={table.getIsSomeRowsSelected()}
                    onChange={table.getToggleAllRowsSelectedHandler()}
                />
            ),
            cell: ({ row }) => (
                <Checkbox
                    checked={selectedRunIds.includes(row.original.id)}
                    onChange={(e) => {
                        if (e.currentTarget.checked) {
                            setSelectedRunIds([...selectedRunIds, row.original.id]);
                        } else {
                            setSelectedRunIds(selectedRunIds.filter(id => id !== row.original.id));
                        }
                    }}
                />
            ),
            size: 40,
        },
        { 
            header: 'ID', 
            accessorKey: 'id', 
            cell: ({ row }) => <span style={{ color: isDark ? '#909296' : '#868e96' }}>#{row.original.id}</span> 
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
                : <span style={{ color: isDark ? '#5c5f66' : '#adb5bd' }}>–</span>
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
                        <span style={{ color: isDark ? '#5c5f66' : '#adb5bd' }}>–</span>
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
                <span style={{ color: isDark ? '#c1c2c5' : '#495057' }}>{formatDate(row.original.created_at)}</span>
            )
        },
        { 
            header: '', 
            accessorKey: 'actions', 
            cell: ({ row }) => (
                <Tooltip label="Run Details" withArrow>
                    <ActionIcon 
                        variant="light" 
                        component={Link}
                        to="/runs/$runId"
                        params={{ runId: String(row.original.id) } as any}
                        target="_blank"
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
            <Group justify="space-between" mb="lg">
                <Group gap="sm">
                    <IconPlayerPlay size={28} color="#228be6" />
                    <Title order={2}>Benchmark Runs</Title>
                    <Badge variant="light" color="blue" size="lg">{runs.length}</Badge>
                </Group>
                <Group gap="md">
                    <Button
                        variant="light"
                        leftSection={<IconScale size={16} />}
                        size="sm"
                        disabled={selectedRunIds.length === 0}
                        onClick={() => {
                            const params = new URLSearchParams();
                            selectedRunIds.forEach(id => params.append('runIds', String(id)));
                            navigate({ to: '/runs/compare', search: { runIds: selectedRunIds.map(String) } as any });
                        }}
                    >
                        Runs vergleichen {selectedRunIds.length > 0 ? `(${selectedRunIds.length})` : ''}
                    </Button>
                    <TextInput
                        placeholder="Modell suchen…"
                        leftSection={<IconSearch size={16} />}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{ width: 250 }}
                    />
                </Group>
            </Group>

            {/* Filter Card */}
            <Card 
                withBorder 
                mb="lg" 
                padding="lg" 
                style={{ 
                    background: isDark ? 'rgba(34, 139, 230, 0.08)' : 'rgba(34, 139, 230, 0.05)',
                    borderColor: isDark ? 'rgba(34, 139, 230, 0.3)' : 'rgba(34, 139, 230, 0.2)'
                }}
            >
                <Group gap="xs" mb="md">
                    <IconFilter size={18} color="#228be6" />
                    <Text fw={600} c="blue">Filter</Text>
                </Group>
                <Group gap="md" align="flex-end" wrap="wrap">
                    <MultiSelect
                        label="Modelle"
                        placeholder="Alle Modelle"
                        leftSection={<IconCpu size={14} />}
                        data={availableModels}
                        value={selectedModels}
                        onChange={setSelectedModels}
                        clearable
                        searchable
                        w={280}
                    />
                    <MultiSelect
                        label="Datasets"
                        placeholder="Alle Datasets"
                        leftSection={<IconDatabase size={14} />}
                        data={availableDatasets.map(d => ({ value: String(d.id), label: d.name }))}
                        value={selectedDatasets}
                        onChange={setSelectedDatasets}
                        clearable
                        searchable
                        w={220}
                    />
                    <Select
                        label="Begründungen"
                        placeholder="Alle"
                        leftSection={<IconMessageCircle size={14} />}
                        data={[
                            { value: 'yes', label: 'Mit Begründungen' },
                            { value: 'no', label: 'Ohne Begründungen' },
                        ]}
                        value={rationaleFilter}
                        onChange={setRationaleFilter}
                        clearable
                        w={200}
                    />
                    <Select
                        label="System Prompt"
                        placeholder="Alle"
                        leftSection={<IconSettings size={14} />}
                        data={[
                            { value: 'yes', label: 'Custom Prompt' },
                            { value: 'no', label: 'Standard Prompt' },
                        ]}
                        value={systemPromptFilter}
                        onChange={setSystemPromptFilter}
                        clearable
                        w={200}
                    />
                </Group>
            </Card>

            <Group mb="md" justify="space-between" align="center">
                <Group gap="sm">
                    <Text size="sm" c="dimmed">
                        {filteredRuns.length} von {runs.length} Run{runs.length !== 1 ? 's' : ''}
                    </Text>
                    {hasActiveFilters && (
                        <Badge variant="light" color="orange" size="sm">gefiltert</Badge>
                    )}
                </Group>
            </Group>

            {isLoading ? (
                <Text c="dimmed" ta="center" py="xl">Runs werden geladen…</Text>
            ) : runs.length === 0 ? (
                <Text c="dimmed" ta="center" py="xl">Keine Benchmark Runs vorhanden.</Text>
            ) : (
                <DataTable data={filteredRuns} columns={columns} enableSorting />
            )}
        </Card>
    );
}
