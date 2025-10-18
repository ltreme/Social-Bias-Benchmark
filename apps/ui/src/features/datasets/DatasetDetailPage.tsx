import { Button, Card, Grid, Group, Progress, Spoiler, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useParams, Link } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { toBar } from '../../components/ChartUtils';
import { useDatasetComposition, useDataset, useDatasetRuns, useAttrgenStatus, useLatestAttrgen, useAttrgenRuns, useBenchmarkStatus } from './hooks';
import { useModels } from '../compare/hooks';
import { useEffect, useState } from 'react';
// no modal inputs here; forms live in child components
import { AttrGenModal } from './components/AttrGenModal';
import { BenchmarkModal } from './components/BenchmarkModal';
import { AttrgenRunsTable } from './components/AttrgenRunsTable';
import { DatasetRunsTable } from './components/DatasetRunsTable';

export function DatasetDetailPage() {
    const { datasetId } = useParams({ from: '/datasets/$datasetId' });
    const idNum = Number(datasetId);
    const { data: dataset_info, isLoading: isLoadingDataset } = useDataset(idNum);
    const { data, isLoading } = useDatasetComposition(idNum);
    const { data: runs, isLoading: isLoadingRuns } = useDatasetRuns(idNum);
    const { data: availableModels } = useModels();
    const [modalOpen, setModalOpen] = useState(false);
    const [benchModalOpen, setBenchModalOpen] = useState(false);
    const [runId, setRunId] = useState<number | undefined>(undefined);
    const runsList = useAttrgenRuns(idNum);
    const [benchRunId, setBenchRunId] = useState<number | undefined>(undefined);
    const [attrgenRunForBenchmark, setAttrgenRunForBenchmark] = useState<number | undefined>(undefined);
    const [benchInitialModelName, setBenchInitialModelName] = useState<string | undefined>(undefined);
    const benchStatus = useBenchmarkStatus(benchRunId);
    const status = useAttrgenStatus(runId);
    const latest = useLatestAttrgen(idNum);
    useEffect(() => {
        if (!runId && latest.data && latest.data.found && latest.data.run_id) {
            setRunId(latest.data.run_id);
        }
    }, [latest.data, runId]);

    // Notify user on failed attrgen status
    useEffect(() => {
        const s = status.data?.status;
        const l = latest.data?.status;
        const err = (status.data as any)?.error || (latest.data as any)?.error;
        if ((s === 'failed' || l === 'failed') && err) {
            notifications.show({ color: 'red', title: 'AttrGen fehlgeschlagen', message: String(err) });
        }
    }, [status.data?.status, latest.data?.status]);

    // Notify user on failed benchmark status
    useEffect(() => {
        const st = benchStatus.data?.status;
        if (st === 'failed' && (benchStatus.data as any)?.error) {
            notifications.show({ color: 'red', title: 'Benchmark fehlgeschlagen', message: String((benchStatus.data as any).error) });
        }
    }, [benchStatus.data?.status]);

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

    // tables moved into components

    return (
        <>
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

            <Group justify="space-between" mb="md">
              <Group>
                <Button component={Link} to={'/datasets/$datasetId/personas'} params={{ datasetId: String(datasetId) }}>Personas anzeigen</Button>
              </Group>
              <Group>
                <Button variant="light" onClick={() => setBenchModalOpen(true)}>Benchmark starten…</Button>
                <Button onClick={() => setModalOpen(true)}>Additional Attributes generieren…</Button>
              </Group>
            </Group>
            {/* Zeige Progress nur für aktive Läufe; abgeschlossene werden unten gelistet */}
            {(runId && status.data && status.data.status === 'failed') ? (
              <div style={{ marginBottom: '1em', color: '#d32f2f' }}>
                <b>AttrGen Fehler:</b> {status.data.error || 'Unbekannter Fehler'}
              </div>
            ) : (runId && status.data && status.data.status !== 'done') ? (
              <div style={{ marginBottom: '1em' }}>
                <b>AttrGen Status:</b> {status.data.status} {status.data.done ?? 0}/{status.data.total ?? 0}
                <Progress value={status.data.pct ?? 0} mt="xs" />
              </div>
            ) : ((latest.data && latest.data.found && latest.data.status === 'failed')) ? (
              <div style={{ marginBottom: '1em', color: '#d32f2f' }}>
                <b>AttrGen Fehler:</b> {latest.data.error || 'Unbekannter Fehler'}
              </div>
            ) : ((latest.data && latest.data.found && latest.data.status !== 'done')) ? (
              <div style={{ marginBottom: '1em' }}>
                <b>AttrGen Status:</b> {latest.data.status} {latest.data.done ?? 0}/{latest.data.total ?? 0}
                <Progress value={latest.data.pct ?? 0} mt="xs" />
              </div>
            ) : null}

            {/* Attribute-Generierung Runs als Tabelle */}
            {(runsList.data?.runs && runsList.data.runs.length > 0) ? (
              <div style={{ marginBottom: '1em' }}>
                <b>Attribute-Generierung (Historie):</b>
                <AttrgenRunsTable
                  datasetId={idNum}
                  runs={runsList.data.runs}
                  onRequestBenchmark={(modelName, runId) => { setBenchInitialModelName(modelName || undefined); setAttrgenRunForBenchmark(runId); setBenchModalOpen(true); }}
                />
                {benchRunId && benchStatus.data ? (
                  benchStatus.data.status === 'failed' ? (
                    <div style={{ marginTop: 8, color: '#d32f2f' }}>
                      <b>Benchmark-Fehler:</b> {(benchStatus.data as any).error || 'Unbekannter Fehler'}
                    </div>
                  ) : (
                    <div style={{ marginTop: 8 }}>
                      <b>Benchmark-Status:</b> {benchStatus.data.status} {benchStatus.data.done ?? 0}/{benchStatus.data.total ?? 0}
                      <div style={{ width: 320 }}>
                        <Progress value={benchStatus.data.pct ?? 0} mt="xs" />
                      </div>
                    </div>
                  )
                ) : null}
              </div>
            ) : null}
            {isLoadingRuns ? ('') : runs && runs.length > 0 ? (
                <div style={{ marginBottom: '1em' }}>
                    <b>Runs mit diesem Dataset:</b>
                    <DatasetRunsTable datasetId={idNum} runs={runs} />
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
        <AttrGenModal
          opened={modalOpen}
          onClose={() => setModalOpen(false)}
          datasetId={idNum}
          availableModels={availableModels}
          onStarted={(rid) => setRunId(rid)}
        />
        {/* Benchmark Modal */}
        <BenchmarkModal
          opened={benchModalOpen}
          onClose={() => { setBenchModalOpen(false); setAttrgenRunForBenchmark(undefined); setBenchInitialModelName(undefined); }}
          datasetId={idNum}
          initialModelName={benchInitialModelName}
          attrgenRunId={attrgenRunForBenchmark}
          onStarted={(rid) => setBenchRunId(rid)}
        />
        </>
    );
}
