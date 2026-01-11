import { Card, Group, MultiSelect, Select, Stack, Text, Title, Badge, Paper, ThemeIcon, SimpleGrid, Tooltip, ActionIcon, Tabs } from '@mantine/core';
import { IconChartBar, IconInfoCircle, IconChartDots3, IconChartBar as IconChartBars } from '@tabler/icons-react';
import { AsyncContent } from '../../../components/AsyncContent';
import { DeltaBarsPanel } from './DeltaBarsPanel';
import { ImprovedForestPlot } from './ImprovedForestPlot';
import { translateCategory } from '../utils/kruskalWallisHelpers';
import { SignificanceTableWithFilters } from './SignificanceTableWithFilters';
import { useThemedColor } from '../../../lib/useThemeColors';
import type { RunDeltas } from '../api';

const ATTRS = [
    { value: 'gender', label: 'Geschlecht', icon: '👤', description: 'Vergleich zwischen Geschlechtern' },
    { value: 'age_group', label: 'Altersgruppe', icon: '🎂', description: 'Vergleich nach Entwicklungsphasen (Adoleszenz, Emerging/Early/Middle/Older Adulthood)' },
    { value: 'religion', label: 'Religion', icon: '🕊️', description: 'Vergleich zwischen Religionsgruppen' },
    { value: 'sexuality', label: 'Sexualität', icon: '🌈', description: 'Vergleich nach sexueller Orientierung' },
    { value: 'marriage_status', label: 'Familienstand', icon: '💍', description: 'Vergleich nach Familienstand' },
    { value: 'education', label: 'Bildung', icon: '🎓', description: 'Vergleich nach Bildungsniveau' },
    { value: 'origin_subregion', label: 'Herkunft', icon: '🌍', description: 'Vergleich nach Herkunftsregion' },
    { value: 'migration_status', label: 'Migration', icon: '✈️', description: 'Vergleich nach Migrationshintergrund' },
];

type BiasTabProps = {
    // Run ID for child components
    runId: number;
    // Attribute selection
    attribute: string;
    onAttributeChange: (attr: string) => void;
    availableCategories: Array<{ category: string; count: number; mean: number }>;
    baseline?: string;
    defaultBaseline?: string;
    onBaselineChange: (baseline: string | null) => void;
    targets: string[];
    onTargetsChange: (targets: string[]) => void;
    // Trait category filter
    traitCategoryOptions: string[];
    traitCategory: string;
    onTraitCategoryChange: (cat: string) => void;
    // Data
    deltas?: RunDeltas;
    isLoadingDeltas: boolean;
    deltasError?: any;
    forestsQueries: Array<{ data?: any; isLoading: boolean; isError: boolean; error?: any }>;
    // All means & deltas for summary
    deltasData: Array<{ a: string; q: { data?: RunDeltas; isLoading: boolean; isError: boolean; error?: any } }>;
    // Categories for all attributes
    allAttributesCategories: Record<string, Array<{ category: string; count: number; mean: number }>>;
};

export function BiasTab({
    runId,
    attribute,
    onAttributeChange,
    availableCategories,
    baseline,
    defaultBaseline,
    onBaselineChange,
    targets,
    onTargetsChange,
    traitCategoryOptions,
    traitCategory,
    onTraitCategoryChange,
    deltas,
    isLoadingDeltas,
    deltasError,
    allAttributesCategories,
    forestsQueries,
    deltasData,
}: BiasTabProps) {
    const getColor = useThemedColor();
    const loadingForest = forestsQueries.length > 0 ? forestsQueries.some((q) => q.isLoading) : false;
    const errorForest = forestsQueries.length > 0 ? forestsQueries.some((q) => q.isError) : false;
    const forestError = forestsQueries.find((q) => q.isError)?.error;
    const attrLabel = ATTRS.find((x) => x.value === attribute)?.label || attribute;

    return (
        <Stack gap="lg">
            {/* Configuration Section - Redesigned */}
            <Paper p="md" withBorder radius="md">
                <Group gap="xs" mb="md">
                    <ThemeIcon size="lg" radius="md" variant="light" color="blue">
                        <IconChartBar size={20} />
                    </ThemeIcon>
                    <div>
                        <Title order={4}>Bias-Analyse Konfiguration</Title>
                        <Text size="sm" c="dimmed">Wähle Merkmal, Vergleichsgruppen und Filter</Text>
                    </div>
                </Group>

                <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
                    {/* Step 1: Merkmal */}
                    <Paper p="md" bg={getColor('blue').bg} radius="md">
                        <Group gap="xs" mb="sm">
                            <ThemeIcon size="sm" radius="xl" color="blue" variant="filled">
                                <Text size="xs" fw={700}>1</Text>
                            </ThemeIcon>
                            <Text size="sm" fw={600}>Merkmal</Text>
                            <Tooltip label="Das demografische Merkmal, nach dem die Bias-Analyse durchgeführt wird" withArrow>
                                <ActionIcon variant="subtle" color="gray" size="xs">
                                    <IconInfoCircle size={14} />
                                </ActionIcon>
                            </Tooltip>
                        </Group>
                        <Select
                            data={ATTRS.map(a => ({ 
                                value: a.value, 
                                label: `${a.icon} ${a.label}` 
                            }))}
                            value={attribute}
                            onChange={(v) => {
                                onAttributeChange(v || 'gender');
                                onBaselineChange(null);
                                onTargetsChange([]);
                            }}
                            size="sm"
                        />
                        <Text size="xs" c="dimmed" mt="xs">
                            {ATTRS.find(a => a.value === attribute)?.description}
                        </Text>
                    </Paper>

                    {/* Step 2: Baseline */}
                    <Paper p="md" bg={getColor('violet').bg} radius="md">
                        <Group gap="xs" mb="sm">
                            <ThemeIcon size="sm" radius="xl" color="violet" variant="filled">
                                <Text size="xs" fw={700}>2</Text>
                            </ThemeIcon>
                            <Text size="sm" fw={600}>Baseline-Gruppe</Text>
                            <Tooltip label="Die Referenzgruppe, gegen die alle anderen Gruppen verglichen werden" withArrow>
                                <ActionIcon variant="subtle" color="gray" size="xs">
                                    <IconInfoCircle size={14} />
                                </ActionIcon>
                            </Tooltip>
                        </Group>
                        <Select
                            data={availableCategories.map((c) => ({ 
                                value: c.category, 
                                label: `${translateCategory(c.category)} (n=${c.count.toLocaleString('de-DE')})` 
                            }))}
                            value={baseline}
                            onChange={onBaselineChange}
                            clearable
                            placeholder={defaultBaseline ? `Auto: ${translateCategory(defaultBaseline)}` : 'Automatisch'}
                            size="sm"
                        />
                        <Text size="xs" c="dimmed" mt="xs">
                            {baseline ? `Δ = Gruppe − ${translateCategory(baseline)}` : `Δ = Gruppe − ${translateCategory(defaultBaseline || 'Auto')}`}
                        </Text>
                    </Paper>

                    {/* Step 3: Vergleichsgruppen */}
                    <Paper p="md" bg={getColor('teal').bg} radius="md">
                        <Group gap="xs" mb="sm">
                            <ThemeIcon size="sm" radius="xl" color="teal" variant="filled">
                                <Text size="xs" fw={700}>3</Text>
                            </ThemeIcon>
                            <Text size="sm" fw={600}>Vergleichsgruppen</Text>
                            <Tooltip label="Gruppen, die im Forest-Plot detailliert verglichen werden" withArrow>
                                <ActionIcon variant="subtle" color="gray" size="xs">
                                    <IconInfoCircle size={14} />
                                </ActionIcon>
                            </Tooltip>
                        </Group>
                        <MultiSelect
                            data={availableCategories
                                .filter(c => c.category !== (baseline || defaultBaseline))
                                .map(c => ({ value: c.category, label: translateCategory(c.category) }))}
                            value={targets}
                            onChange={onTargetsChange}
                            placeholder="Kategorien wählen"
                            searchable
                            size="sm"
                            maxDropdownHeight={200}
                        />
                        <Text size="xs" c="dimmed" mt="xs">
                            {targets.length === 0 ? 'Für Forest-Plot auswählen' : `${targets.length} Gruppe(n) ausgewählt`}
                        </Text>
                    </Paper>

                    {/* Step 4: Filter */}
                    <Paper p="md" bg={getColor('orange').bg} radius="md">
                        <Group gap="xs" mb="sm">
                            <ThemeIcon size="sm" radius="xl" color="orange" variant="filled">
                                <Text size="xs" fw={700}>4</Text>
                            </ThemeIcon>
                            <Text size="sm" fw={600}>Trait-Filter</Text>
                            <Tooltip label="Optional: Nur bestimmte Trait-Kategorien (z.B. sozial, kompetenz) analysieren" withArrow>
                                <ActionIcon variant="subtle" color="gray" size="xs">
                                    <IconInfoCircle size={14} />
                                </ActionIcon>
                            </Tooltip>
                        </Group>
                        <Select
                            data={[
                                { value: '__all', label: '🔍 Alle Kategorien' }, 
                                ...traitCategoryOptions.map((c) => ({ value: c, label: c }))
                            ]}
                            value={traitCategory}
                            onChange={(val) => onTraitCategoryChange(val ?? '__all')}
                            size="sm"
                        />
                        <Text size="xs" c="dimmed" mt="xs">
                            {traitCategory === '__all' ? 'Alle Traits einbezogen' : `Nur "${traitCategory}" Traits`}
                        </Text>
                    </Paper>
                </SimpleGrid>

                {/* Current Selection Summary */}
                <Paper p="sm" bg={getColor('gray').bg} radius="md" mt="md">
                    <Group gap="xs" wrap="wrap">
                        <Text size="xs" fw={600}>Aktuelle Auswahl:</Text>
                        <Badge variant="light" color="blue" size="sm">{attrLabel}</Badge>
                        {targets.length > 0 ? (
                            <>
                                <Text size="xs" c="dimmed">→</Text>
                                <Badge variant="light" color="violet" size="sm">{translateCategory(baseline || defaultBaseline || 'Auto')}</Badge>
                                <Text size="xs" c="dimmed">vs.</Text>
                                {targets.map((t, i) => (
                                    <Group key={t} gap={4}>
                                        {i > 0 && <Text size="xs" c="dimmed">,</Text>}
                                        <Badge variant="light" color="teal" size="sm">{translateCategory(t)}</Badge>
                                    </Group>
                                ))}
                            </>
                        ) : (
                            <>
                                <Text size="xs" c="dimmed">| Baseline:</Text>
                                <Badge variant="light" color="violet" size="sm">{translateCategory(baseline || defaultBaseline || 'Auto')}</Badge>
                            </>
                        )}
                        {traitCategory !== '__all' && (
                            <>
                                <Text size="xs" c="dimmed">|</Text>
                                <Badge variant="light" color="orange" size="sm">Filter: {traitCategory}</Badge>
                            </>
                        )}
                    </Group>
                </Paper>
            </Paper>

            {/* Visualizations with Tabs */}
            <Paper p="md" withBorder radius="md">
                <Tabs defaultValue="lollipop">
                    <Tabs.List mb="md">
                        <Tabs.Tab value="lollipop" leftSection={<IconChartBars size={16} />}>
                            Lollipop-Chart
                        </Tabs.Tab>
                        <Tabs.Tab value="forest" leftSection={<IconChartDots3 size={16} />}>
                            Forest Plot
                        </Tabs.Tab>
                    </Tabs.List>

                    <Tabs.Panel value="lollipop">
                        <AsyncContent isLoading={isLoadingDeltas} isError={!!deltasError} error={deltasError}>
                            <DeltaBarsPanel 
                                deltas={deltas as any} 
                                title="Gruppenvergleich (Lollipop)"
                                baseline={baseline || defaultBaseline}
                            />
                        </AsyncContent>
                    </Tabs.Panel>

                    <Tabs.Panel value="forest">
                        {targets.length > 0 ? (
                            <AsyncContent isLoading={loadingForest} isError={errorForest} error={forestError}>
                                <ImprovedForestPlot
                                    datasets={forestsQueries.map((q, i) => ({ 
                                        target: targets[i], 
                                        rows: (q.data as any)?.rows || [], 
                                        overall: (q.data as any)?.overall 
                                    }))}
                                    attr={attrLabel}
                                    baseline={baseline}
                                    defaultBaseline={defaultBaseline}
                                />
                            </AsyncContent>
                        ) : (
                            <Paper p="xl" bg={getColor('gray').bg} radius="md" ta="center">
                                <ThemeIcon size="xl" radius="xl" variant="light" color="gray" mb="md">
                                    <IconChartDots3 size={24} />
                                </ThemeIcon>
                                <Text fw={500} mb="xs">Forest Plot</Text>
                                <Text size="sm" c="dimmed">
                                    Wähle unter "Vergleichsgruppen" mindestens eine Kategorie aus,<br />
                                    um den detaillierten Forest Plot zu sehen.
                                </Text>
                            </Paper>
                        )}
                    </Tabs.Panel>
                </Tabs>
            </Paper>

            {/* Significance Tables */}
            <Card withBorder padding="md">
                <Title order={4} mb="md">Signifikanz-Tabellen (p, q, Cliff's δ)</Title>
                <Text size="sm" c="dimmed" mb="md">
                    Für jede Tabelle kannst du individuell die Trait-Kategorie und Baseline-Gruppe anpassen.
                </Text>
                {deltasData.map(({ a }) => (
                    <div key={a} style={{ marginTop: 16, marginBottom: 16 }}>
                        <Title order={5} mb="xs">{ATTRS.find(x => x.value === a)?.label || a}</Title>
                        <SignificanceTableWithFilters
                            runId={runId}
                            attribute={a}
                            availableCategories={allAttributesCategories[a] || []}
                            traitCategoryOptions={traitCategoryOptions}
                            initialTraitCategory={traitCategory}
                        />
                    </div>
                ))}
            </Card>
        </Stack>
    );
}
