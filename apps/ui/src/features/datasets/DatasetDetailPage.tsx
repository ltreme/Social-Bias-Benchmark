import { ActionIcon, Button, Card, Grid, Group, Progress, Spoiler, Title } from '@mantine/core';
import { useParams, Link } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useDatasetComposition, useDataset, useDatasetRuns, useStartAttrgen, useAttrgenStatus, useLatestAttrgen, useAttrgenRuns, useStartBenchmark, useBenchmarkStatus } from './hooks';
import { useModels } from '../compare/hooks';
import { useEffect, useState } from 'react';
import { Modal, NumberInput, Select, TextInput, Checkbox, Textarea } from '@mantine/core';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useDeleteRun } from '../runs/hooks';
import { useQueryClient } from '@tanstack/react-query';

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
    const startAttr = useStartAttrgen();
    const { data: availableModels } = useModels();
    const [modalOpen, setModalOpen] = useState(false);
    const [benchModalOpen, setBenchModalOpen] = useState(false);
    const [llm, setLlm] = useState<'vllm'|'fake'>('vllm');
    const [modelName, setModelName] = useState<string>('');
    const [batchSize, setBatchSize] = useState<number>(8);
    const [maxNew, setMaxNew] = useState<number>(192);
    const [maxAttempts, setMaxAttempts] = useState<number>(3);
    const [systemPrompt, setSystemPrompt] = useState<string>('');
    const [vllmBase, setVllmBase] = useState<string>('http://localhost:8000');
    const [vllmApiKey, setVllmApiKey] = useState<string>('');
    const [includeRationale, setIncludeRationale] = useState<boolean>(false);
    const [runId, setRunId] = useState<number | undefined>(undefined);
    const runsList = useAttrgenRuns(idNum);
    const [resumeRunId, setResumeRunId] = useState<number | undefined>(undefined);
    const startBench = useStartBenchmark();
    const [benchRunId, setBenchRunId] = useState<number | undefined>(undefined);
    const benchStatus = useBenchmarkStatus(benchRunId);
    const status = useAttrgenStatus(runId);
    const latest = useLatestAttrgen(idNum);
    useEffect(() => {
        if (!runId && latest.data && latest.data.found && latest.data.run_id) {
            setRunId(latest.data.run_id);
        }
    }, [latest.data, runId]);

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

    // Columns for runs table
    const runsColumns: ColumnDef<{ id: number; model_name: string; include_rationale: boolean; created_at: string }>[] = [
        { header: 'ID', accessorKey: 'id', cell: ({ row }) => (<Link to={`/runs/${row.original.id}`}>#{row.original.id}</Link>) },
        { header: 'Model', accessorKey: 'model_name' },
        { header: 'Rationale', accessorKey: 'include_rationale', cell: ({ row }) => (row.original.include_rationale ? 'Ja' : 'Nein') },
        { header: 'Erstellt', accessorKey: 'created_at', cell: ({ row }) => (row.original.created_at ? new Date(row.original.created_at).toLocaleString() : '') },
        { header: '', accessorKey: 'actions', cell: ({ row }) => (
            <ActionIcon variant="subtle" color="red" title="Run löschen" onClick={async (e) => {
                e.preventDefault();
                if (!confirm(`Run #${row.original.id} wirklich löschen?`)) return;
                try {
                    await delRun.mutateAsync(row.original.id);
                    qc.invalidateQueries({ queryKey: ['dataset-runs', idNum] });
                } catch (err) { /* no-op */ }
            }}>🗑️</ActionIcon>
        ) },
    ];

    const delRun = useDeleteRun();
    const qc = useQueryClient();

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
              <div />
              <Group>
                <Button variant="light" onClick={() => setBenchModalOpen(true)}>Benchmark starten…</Button>
                <Button onClick={() => setModalOpen(true)}>Additional Attributes generieren…</Button>
              </Group>
            </Group>
            {/* Zeige Progress nur für aktive Läufe; abgeschlossene werden unten gelistet */}
            {(runId && status.data && status.data.status !== 'done' && status.data.status !== 'failed') ? (
              <div style={{ marginBottom: '1em' }}>
                <b>AttrGen Status:</b> {status.data.status} {status.data.done ?? 0}/{status.data.total ?? 0}
                <Progress value={status.data.pct ?? 0} mt="xs" />
              </div>
            ) : ((latest.data && latest.data.found && latest.data.status !== 'done' && latest.data.status !== 'failed')) ? (
              <div style={{ marginBottom: '1em' }}>
                <b>AttrGen Status:</b> {latest.data.status} {latest.data.done ?? 0}/{latest.data.total ?? 0}
                <Progress value={latest.data.pct ?? 0} mt="xs" />
              </div>
            ) : null}

            {/* Liste der AttrGen-Runs: fertige als Eintrag mit Modell, laufende mit Fortschritt */}
            {runsList.data?.runs && runsList.data.runs.length > 0 ? (
              <div style={{ marginBottom: '1em' }}>
                <b>Attribute-Generierung (Historie):</b>
                <ul style={{ margin: 0, paddingLeft: '1.5em' }}>
                  {runsList.data.runs.map(r => {
                    const isDone = (r.status === 'done') || ((r.done ?? 0) > 0 && (r.total ?? 0) > 0 && (r.done === r.total));
                    return (
                      <li key={r.id} style={{ marginBottom: 6 }}>
                        <span>Run #{r.id} – {r.model_name || 'Modell unbekannt'} – {new Date(r.created_at).toLocaleString()} – </span>
                        {isDone ? (
                          <span style={{ color: '#2ca25f' }}>Fertig</span>
                        ) : (
                          <span>
                            {r.status} {r.done ?? 0}/{r.total ?? 0}
                            <div style={{ width: 240 }}>
                              <Progress value={r.pct ?? 0} mt="xs" />
                            </div>
                          </span>
                        )}
                        {isDone ? (
                          <Button size="xs" style={{ marginLeft: 8 }} onClick={() => { setModelName(r.model_name || ''); setBenchModalOpen(true); }}>
                            Benchmark starten
                          </Button>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
                {benchRunId && benchStatus.data ? (
                  <div style={{ marginTop: 8 }}>
                    <b>Benchmark-Status:</b> {benchStatus.data.status} {benchStatus.data.done ?? 0}/{benchStatus.data.total ?? 0}
                    <div style={{ width: 320 }}>
                      <Progress value={benchStatus.data.pct ?? 0} mt="xs" />
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
            {isLoadingRuns ? ('') : runs && runs.length > 0 ? (
                <div style={{ marginBottom: '1em' }}>
                    <b>Runs mit diesem Dataset:</b>
                    <DataTable data={runs} columns={runsColumns} />
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
        <Modal opened={modalOpen} onClose={() => setModalOpen(false)} title="Additional Attributes generieren" size="lg">
          <Group grow mb="md">
            <Select label="Backend" data={[ {value:'vllm',label:'vLLM'}, {value:'fake',label:'Fake'} ]} value={llm} onChange={(v)=>setLlm((v as any)||'vllm')} />
            <Select label="Model" data={availableModels || []} value={modelName} onChange={(v)=>setModelName(v || '')} searchable placeholder="Model wählen" />
          </Group>
          <Group grow mb="md">
            <Select label="Run fortsetzen" data={ (runsList.data?.runs || []).map(r => ({ value: String(r.id), label: `#${r.id} · ${r.model_name ?? ''} · ${new Date(r.created_at).toLocaleString()} · ${Math.round(r.pct || 0)}%` })) } value={resumeRunId ? String(resumeRunId) : null} onChange={(v)=> setResumeRunId(v ? Number(v) : undefined)} clearable placeholder="Optional" />
          </Group>
          {llm==='vllm' ? (
            <TextInput label="vLLM Base URL" value={vllmBase} onChange={(e)=>setVllmBase(e.currentTarget.value)} />
          ) : null}
          <Group grow mb="md">
            <NumberInput label="Batch Size" value={batchSize} onChange={(v)=>setBatchSize(Number(v||0))} min={1} />
            <NumberInput label="Max New Tokens" value={maxNew} onChange={(v)=>setMaxNew(Number(v||0))} min={32} />
            <NumberInput label="Max Attempts" value={maxAttempts} onChange={(v)=>setMaxAttempts(Number(v||0))} min={1} />
          </Group>
          <TextInput label="System Prompt (optional)" value={systemPrompt} onChange={(e)=>setSystemPrompt(e.currentTarget.value)} />
          <Group justify="right" mt="md">
            <Button variant="default" onClick={()=>setModalOpen(false)}>Abbrechen</Button>
            <Button loading={startAttr.isPending} disabled={!modelName && !resumeRunId} onClick={async ()=>{
              try {
                const r = await startAttr.mutateAsync({ dataset_id: idNum, model_name: modelName, llm, batch_size: batchSize, max_new_tokens: maxNew, max_attempts: maxAttempts, system_prompt: systemPrompt || undefined, vllm_base_url: llm==='vllm'? vllmBase: undefined, resume_run_id: resumeRunId });
                setRunId(r.run_id); setModalOpen(false);
              } catch(e) {}
            }}>Starten</Button>
          </Group>
        </Modal>
        {/* Benchmark Modal */}
        <Modal opened={benchModalOpen} onClose={() => setBenchModalOpen(false)} title="Benchmark starten" size="lg">
          {(() => {
            const completedModels = Array.from(new Set((runsList.data?.runs || []).filter(r => (r.done ?? 0) > 0 && (r.total ?? 0) > 0 && r.done === r.total).map(r => r.model_name || ''))).filter(Boolean);
            return (
              <>
                <Group grow mb="md">
                  <Select label="Model (aus fertigen AttrGen-Runs)" data={completedModels} value={modelName} onChange={(v)=>setModelName(v || '')} placeholder="Model wählen" searchable />
                  <NumberInput label="Batch Size" value={batchSize} onChange={(v)=>setBatchSize(Number(v||0))} min={1} />
                </Group>
                <Group grow mb="md">
                  <NumberInput label="Max New Tokens" value={maxNew} onChange={(v)=>setMaxNew(Number(v||0))} min={32} />
                  <NumberInput label="Max Attempts" value={maxAttempts} onChange={(v)=>setMaxAttempts(Number(v||0))} min={1} />
                </Group>
                <Checkbox label="Rationale inkludieren" checked={includeRationale} onChange={(e) => setIncludeRationale(e.currentTarget.checked)} />
                <Textarea label="System Prompt (optional)" minRows={3} value={systemPrompt} onChange={(e)=>setSystemPrompt(e.currentTarget.value)} />
                <Group grow mb="md" mt="md">
                  <TextInput label="vLLM Base URL" value={vllmBase} onChange={(e)=>setVllmBase(e.currentTarget.value)} />
                  <TextInput label="vLLM API Key (optional)" value={vllmApiKey} onChange={(e)=>setVllmApiKey(e.currentTarget.value)} placeholder="Nutze .env, falls leer" />
                </Group>
                <Group justify="right" mt="md">
                  <Button variant="default" onClick={()=>setBenchModalOpen(false)}>Abbrechen</Button>
                  <Button loading={startBench.isPending} disabled={!modelName} onClick={async ()=>{
                    try {
                      const rs = await startBench.mutateAsync({ dataset_id: idNum, model_name: modelName, include_rationale: includeRationale, llm: 'vllm', batch_size: batchSize, max_new_tokens: maxNew, max_attempts: maxAttempts, system_prompt: systemPrompt || undefined, vllm_base_url: vllmBase, vllm_api_key: vllmApiKey || undefined });
                      setBenchRunId(rs.run_id); setBenchModalOpen(false);
                    } catch(e) {}
                  }}>Benchmark starten</Button>
                </Group>
              </>
            );
          })()}
        </Modal>
        </>
    );
}
