import { ActionIcon, Button, Card, Grid, Group, Progress, Spoiler, Title } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useParams, Link } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useDatasetComposition, useDataset, useDatasetRuns, useStartAttrgen, useAttrgenStatus, useLatestAttrgen, useAttrgenRuns, useStartBenchmark, useBenchmarkStatus, useDeleteAttrgenRun } from './hooks';
import { useModels } from '../compare/hooks';
import { useEffect, useState } from 'react';
import { Modal, Select, TextInput, Checkbox, Textarea } from '@mantine/core';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useDeleteRun } from '../runs/hooks';
import { useQueryClient } from '@tanstack/react-query';
import { IconPlayerPlay, IconUsers, IconTrash } from '@tabler/icons-react';
import type { AttrgenRun } from './api';

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
    const [batchSizeStr, setBatchSizeStr] = useState<string>('8');
    const [maxNewStr, setMaxNewStr] = useState<string>('192');
    const [maxAttemptsStr, setMaxAttemptsStr] = useState<string>('3');
    const [systemPrompt, setSystemPrompt] = useState<string>('');
    const [vllmBase, setVllmBase] = useState<string>('http://host.docker.internal:8000');
    const [vllmApiKey, setVllmApiKey] = useState<string>('');
    const [includeRationale, setIncludeRationale] = useState<boolean>(false);
    const [runId, setRunId] = useState<number | undefined>(undefined);
    const runsList = useAttrgenRuns(idNum);
    const [resumeRunId, setResumeRunId] = useState<number | undefined>(undefined);
    const startBench = useStartBenchmark();
    const [benchRunId, setBenchRunId] = useState<number | undefined>(undefined);
    const [attrgenRunForBenchmark, setAttrgenRunForBenchmark] = useState<number | undefined>(undefined);
    const [resumeBenchRunId, setResumeBenchRunId] = useState<number | undefined>(undefined);
    const [scaleMode, setScaleMode] = useState<'in'|'rev'|'random50'>('in');
    const [dualFrac, setDualFrac] = useState<number>(0.15);
    const benchStatus = useBenchmarkStatus(benchRunId);
    const status = useAttrgenStatus(runId);
    const latest = useLatestAttrgen(idNum);
    const delAttrRun = useDeleteAttrgenRun(idNum);
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

    // Columns for attribute-generation runs
    const attrColumns: ColumnDef<AttrgenRun>[] = [
        { header: 'ID', accessorKey: 'id', cell: ({ row }) => (<>#{row.original.id}</>) },
        { header: 'Model', accessorKey: 'model_name', cell: ({ row }) => (row.original.model_name || '') },
        { header: 'Status', accessorKey: 'status', cell: ({ row }) => {
            const r = row.original;
            const isDone = (r.status === 'done') || ((r.done ?? 0) > 0 && (r.total ?? 0) > 0 && (r.done === r.total));
            return (
              <div style={{ minWidth: 180 }}>
                {r.status === 'failed' ? (
                  <span style={{ color: '#d32f2f' }} title={r.error || ''}>Fehlgeschlagen</span>
                ) : isDone ? (<span style={{ color: '#2ca25f' }}>Fertig</span>) : (
                  <>
                    <span>{r.status} {r.done ?? 0}/{r.total ?? 0}</span>
                    <div style={{ width: 140 }}><Progress value={r.pct ?? 0} mt="xs" /></div>
                  </>
                )}
              </div>
            );
        } },
        { header: 'Erstellt', accessorKey: 'created_at', cell: ({ row }) => (row.original.created_at ? new Date(row.original.created_at).toLocaleString() : '') },
        { header: 'Aktionen', accessorKey: 'actions', cell: ({ row }) => {
            const r = row.original;
            const isDone = (r.status === 'done') || ((r.done ?? 0) > 0 && (r.total ?? 0) > 0 && (r.done === r.total));
            return (
              <Group gap="xs">
                <ActionIcon title="Benchmark starten" variant="light" onClick={() => { setModelName(r.model_name || ''); setAttrgenRunForBenchmark(r.id); setBenchModalOpen(true); }} disabled={!isDone}>
                  <IconPlayerPlay size={16} />
                </ActionIcon>
                <ActionIcon title="Personas anzeigen" variant="light" component={Link as any} to={'/datasets/$datasetId/personas'} params={{ datasetId: String(datasetId) }} search={{ attrgenRunId: r.id }}>
                  <IconUsers size={16} />
                </ActionIcon>
                <ActionIcon title="Attr-Run löschen" color="red" variant="subtle" onClick={async () => {
                  if (!confirm(`AttrGen-Run #${r.id} wirklich löschen?`)) return;
                  try {
                    await delAttrRun.mutateAsync(r.id);
                  } catch (e) { /* notification via interceptor */ }
                }}>
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
            );
        } },
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
                <DataTable data={runsList.data.runs} columns={attrColumns} />
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
            <TextInput
              label="Batch Size"
              value={batchSizeStr}
              onChange={(e)=>{ const v=e.currentTarget.value; if (/^\d*$/.test(v)) setBatchSizeStr(v); }}
              onBlur={()=>{ const n = Math.max(1, parseInt(batchSizeStr || '0', 10) || 0); setBatchSize(n); setBatchSizeStr(String(n)); }}
              placeholder="z.B. 8"
            />
            <TextInput
              label="Max New Tokens"
              value={maxNewStr}
              onChange={(e)=>{ const v=e.currentTarget.value; if (/^\d*$/.test(v)) setMaxNewStr(v); }}
              onBlur={()=>{ const n = Math.max(32, parseInt(maxNewStr || '0', 10) || 0); setMaxNew(n); setMaxNewStr(String(n)); }}
              placeholder="z.B. 192"
            />
            <TextInput
              label="Max Attempts"
              value={maxAttemptsStr}
              onChange={(e)=>{ const v=e.currentTarget.value; if (/^\d*$/.test(v)) setMaxAttemptsStr(v); }}
              onBlur={()=>{ const n = Math.max(1, parseInt(maxAttemptsStr || '0', 10) || 0); setMaxAttempts(n); setMaxAttemptsStr(String(n)); }}
              placeholder="z.B. 3"
            />
          </Group>
          <TextInput label="System Prompt (optional)" value={systemPrompt} onChange={(e)=>setSystemPrompt(e.currentTarget.value)} />
          <Group justify="right" mt="md">
            <Button variant="default" onClick={()=>setModalOpen(false)}>Abbrechen</Button>
            <Button loading={startAttr.isPending} disabled={!modelName && !resumeRunId} onClick={async ()=>{
              try {
                const bs = Math.max(1, parseInt(batchSizeStr || String(batchSize), 10) || batchSize);
                const mn = Math.max(32, parseInt(maxNewStr || String(maxNew), 10) || maxNew);
                const ma = Math.max(1, parseInt(maxAttemptsStr || String(maxAttempts), 10) || maxAttempts);
                setBatchSize(bs); setBatchSizeStr(String(bs));
                setMaxNew(mn); setMaxNewStr(String(mn));
                setMaxAttempts(ma); setMaxAttemptsStr(String(ma));
                const r = await startAttr.mutateAsync({ dataset_id: idNum, model_name: modelName, llm, batch_size: bs, max_new_tokens: mn, max_attempts: ma, system_prompt: systemPrompt || undefined, vllm_base_url: llm==='vllm'? vllmBase: undefined, resume_run_id: resumeRunId });
                setRunId(r.run_id); setModalOpen(false);
              } catch(e) {}
            }}>Starten</Button>
          </Group>
        </Modal>
        {/* Benchmark Modal */}
        <Modal opened={benchModalOpen} onClose={() => { setBenchModalOpen(false); setAttrgenRunForBenchmark(undefined); }} title="Benchmark starten" size="lg">
          {(() => {
            const completedModels = Array.from(new Set((runsList.data?.runs || []).filter(r => (r.done ?? 0) > 0 && (r.total ?? 0) > 0 && r.done === r.total).map(r => r.model_name || ''))).filter(Boolean);
            return (
              <>
                <Group grow mb="md">
                  <Select label="Model (aus fertigen AttrGen-Runs)" data={completedModels} value={modelName} onChange={(v)=>setModelName(v || '')} placeholder="Model wählen" searchable disabled={!!resumeBenchRunId} />
                  <TextInput
                    label="Batch Size"
                    value={batchSizeStr}
                    onChange={(e)=>{ const v=e.currentTarget.value; if (/^\d*$/.test(v)) setBatchSizeStr(v); }}
                    onBlur={()=>{ const n = Math.max(1, parseInt(batchSizeStr || '0', 10) || 0); setBatchSize(n); setBatchSizeStr(String(n)); }}
                    placeholder="z.B. 8"
                  />
                </Group>
                <Group grow mb="md">
                  <TextInput
                    label="Max New Tokens"
                    value={maxNewStr}
                    onChange={(e)=>{ const v=e.currentTarget.value; if (/^\d*$/.test(v)) setMaxNewStr(v); }}
                    onBlur={()=>{ const n = Math.max(32, parseInt(maxNewStr || '0', 10) || 0); setMaxNew(n); setMaxNewStr(String(n)); }}
                    placeholder="z.B. 192"
                  />
                  <TextInput
                    label="Max Attempts"
                    value={maxAttemptsStr}
                    onChange={(e)=>{ const v=e.currentTarget.value; if (/^\d*$/.test(v)) setMaxAttemptsStr(v); }}
                    onBlur={()=>{ const n = Math.max(1, parseInt(maxAttemptsStr || '0', 10) || 0); setMaxAttempts(n); setMaxAttemptsStr(String(n)); }}
                    placeholder="z.B. 3"
                  />
                </Group>
                <Checkbox label="Rationale inkludieren" checked={includeRationale} onChange={(e) => setIncludeRationale(e.currentTarget.checked)} />
                <Select
                  label="Likert-Reihenfolge"
                  data={[{value:'in',label:'in order'}, {value:'rev',label:'reversed order'}, {value:'random50',label:'50/50 random'}]}
                  value={scaleMode}
                  onChange={(v)=> setScaleMode((v as any) || 'in')}
                  description="Steuert die Reihenfolge der Skala im Prompt"
                  disabled={!!resumeBenchRunId}
                />
                <Select
                  label="Doppel-Befragung Anteil"
                  data={[
                    { value: '0', label: '0%' },
                    { value: '0.1', label: '10%' },
                    { value: '0.15', label: '15%' },
                    { value: '0.2', label: '20%' },
                  ]}
                  value={String(dualFrac)}
                  onChange={(v)=> setDualFrac(Number(v || '0'))}
                  description="Anteil der Paare, die in beiden Richtungen gefragt werden"
                  disabled={!!resumeBenchRunId}
                />
                <Textarea label="System Prompt (optional)" minRows={3} value={systemPrompt} onChange={(e)=>setSystemPrompt(e.currentTarget.value)} />
                <Group grow mb="md" mt="md">
                  <TextInput label="vLLM Base URL" value={vllmBase} onChange={(e)=>setVllmBase(e.currentTarget.value)} />
                  <TextInput label="vLLM API Key (optional)" value={vllmApiKey} onChange={(e)=>setVllmApiKey(e.currentTarget.value)} placeholder="Nutze .env, falls leer" />
                </Group>
                <Group grow mb="md">
                  <Select
                    label="Run fortsetzen"
                    data={(runs || []).map(r => ({ value: String(r.id), label: `#${r.id} · ${r.model_name} · ${new Date(r.created_at).toLocaleString()}` }))}
                    value={resumeBenchRunId ? String(resumeBenchRunId) : null}
                    onChange={(v)=> setResumeBenchRunId(v ? Number(v) : undefined)}
                    clearable
                    placeholder="Optional"
                  />
                </Group>
                <Group justify="right" mt="md">
                  <Button variant="default" onClick={()=>setBenchModalOpen(false)}>Abbrechen</Button>
                  <Button loading={startBench.isPending} disabled={!modelName && !resumeBenchRunId} onClick={async ()=>{
                    try {
                      const bs = Math.max(1, parseInt(batchSizeStr || String(batchSize), 10) || batchSize);
                      const mn = Math.max(32, parseInt(maxNewStr || String(maxNew), 10) || maxNew);
                      const ma = Math.max(1, parseInt(maxAttemptsStr || String(maxAttempts), 10) || maxAttempts);
                      setBatchSize(bs); setBatchSizeStr(String(bs));
                      setMaxNew(mn); setMaxNewStr(String(mn));
                      setMaxAttempts(ma); setMaxAttemptsStr(String(ma));
                      const rs = await startBench.mutateAsync({ dataset_id: idNum, model_name: modelName || undefined, include_rationale: includeRationale, llm: 'vllm', batch_size: bs, max_new_tokens: mn, max_attempts: ma, system_prompt: systemPrompt || undefined, vllm_base_url: vllmBase, vllm_api_key: vllmApiKey || undefined, resume_run_id: resumeBenchRunId, scale_mode: resumeBenchRunId ? undefined : scaleMode, dual_fraction: resumeBenchRunId ? undefined : dualFrac, attrgen_run_id: attrgenRunForBenchmark });
                      setBenchRunId(rs.run_id); setBenchModalOpen(false); setResumeBenchRunId(undefined);
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
