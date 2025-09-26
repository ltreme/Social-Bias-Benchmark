import { Card, Grid, Title, Spoiler } from '@mantine/core';
import { useParams, Link } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useDatasetComposition, useDataset, useDatasetRuns } from './hooks';

function toBar(items: Array<{ value: string; count: number }>, opts?: { horizontal?: boolean }) {
    const labels = items.map((d) => d.value);
    const values = items.map((d) => d.count);
    return [{ type: 'bar', x: opts?.horizontal ? values : labels, y: opts?.horizontal ? labels : values, orientation: opts?.horizontal ? 'h' : undefined } as Partial<Plotly.Data>];
}

export function DatasetDetailPage() {
    const { datasetId } = useParams({ from: '/datasets/$datasetId' });
    const idNum = Number(datasetId);
    const { data: dataset_info, isLoading: isLoadingDataset } = useDataset(idNum);
    const { data, isLoading } = useDatasetComposition(idNum);
    const { data: runs, isLoading: isLoadingRuns } = useDatasetRuns(idNum);

    const gender = data?.attributes?.gender ?? [];
    const religion = data?.attributes?.religion ?? [];
    const sexuality = data?.attributes?.sexuality ?? [];
    const education = data?.attributes?.education ?? [];
    const marriage = data?.attributes?.marriage_status ?? [];
    const originRegion = data?.attributes?.origin_region ?? [];
    const originCountry = data?.attributes?.origin_country ?? [];

    // Age pyramid setup: male negative on X, female positive
    const ageBins = data?.age?.bins ?? [];
    const male = (data?.age?.male ?? []).map((v) => -v);
    const female = data?.age?.female ?? [];
    const other = data?.age?.other ?? [];
    const traces: Partial<Plotly.Data>[] = [
        { name: 'Male', type: 'bar', x: male, y: ageBins, orientation: 'h' },
        { name: 'Female', type: 'bar', x: female, y: ageBins, orientation: 'h' },
    ];
    if (other.some((v) => v > 0)) {
        traces.push({ name: 'Other', type: 'bar', x: other, y: ageBins, orientation: 'h' });
    }

    return (
        <Card>
            <Title order={2} mb="md">Dataset {datasetId}: {dataset_info?.name} – Zusammensetzung</Title>
            {isLoadingDataset ? ('') : dataset_info ? (
                <div style={{ marginBottom: '1em' }}>
                    <b>Art:</b> {dataset_info.kind} | <b>Größe:</b> {dataset_info.size} | {dataset_info.created_at ? (<><b>Erstellt:</b> {new Date(dataset_info.created_at).toLocaleDateString()} | <b>Anteil Personas mit generierten Attributen:</b> {dataset_info.enriched_percentage.toFixed(2)}% | </> ) : null}
                    {dataset_info.seed ? (<><b>Seed:</b> {dataset_info.seed} </>) : null}
                    {dataset_info.config_json ? (<p><b>Config:</b> <Spoiler maxHeight={0} showLabel="anzeigen" hideLabel="verstecken"><pre style={{ margin: 0, fontFamily: 'monospace' }}>{JSON.stringify(dataset_info.config_json, null, 2)}</pre></Spoiler></p>) : null}
                </div>
            ) : (
                <div style={{ marginBottom: '1em' }}>Dataset nicht gefunden.</div>
            )}
            {isLoadingRuns ? ('') : runs && runs.length > 0 ? (
                <div style={{ marginBottom: '1em' }}>
                    <b>Runs mit diesem Dataset:</b>
                    <ul style={{ margin: 0, paddingLeft: '1.5em' }}>
                        {runs.map(r => (
                            <li key={r.id}>
                                <Link to={`/runs/${r.id}`}>Run {r.id}</Link> – {r.model_name}
                                {r.include_rationale ? ' (mit Begründung)' : ''}
                                {r.created_at ? `, erstellt ${new Date(r.created_at).toLocaleDateString()}` : ''}
                            </li>
                        ))}
                    </ul>
                </div>
            ) : runs && runs.length === 0 ? (
                <div style={{ marginBottom: '1em' }}>Keine Runs mit diesem Dataset.</div>
            ) : null}

            {isLoading || !data ? (
                <div>Laden…</div>
            ) : (
                <Grid>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                        <ChartPanel title={`Geschlecht (n=${data.n})`} data={[{ type: 'pie', labels: gender.map(d => d.value), values: gender.map(d => d.count) }]} />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                        <ChartPanel title="Religion" data={toBar(religion, { horizontal: true })} />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                        <ChartPanel title="Sexualität" data={toBar(sexuality, { horizontal: true })} />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                        <ChartPanel title="Bildung" data={toBar(education, { horizontal: true })} />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                        <ChartPanel title="Familienstand" data={toBar(marriage, { horizontal: true })} />
                    </Grid.Col>
                    <Grid.Col span={{ base: 12, md: 6 }}>
                        <ChartPanel title="Herkunft – Region" data={toBar(originRegion, { horizontal: true })} />
                    </Grid.Col>
                    <Grid.Col span={12}>
                        <ChartPanel title="Herkunft – Länder (Top)" data={toBar(originCountry, { horizontal: true })} />
                    </Grid.Col>
                    <Grid.Col span={12}>
                        <ChartPanel title="Alterspyramide" data={traces} layout={{ barmode: 'relative', xaxis: { title: 'Anzahl', tickformat: '', separatethousands: true }, yaxis: { title: 'Alter' } }} />
                    </Grid.Col>
                </Grid>
            )}
        </Card>
    );
}

