import { Badge, Button, Card, Divider, Grid, Group, Select, Text, Title, Tooltip } from '@mantine/core';
import { useEffect, useState } from 'react';
import { Link, useParams } from '@tanstack/react-router';
import { ChartPanel } from '../../components/ChartPanel';
import { useRunDeltas, useRunForest, useRunMetrics, useRun, useRunMissing, useRunOrderMetrics } from './hooks';
import { useStartBenchmark } from '../datasets/hooks';

const ATTRS = [
  { value: 'gender', label: 'Geschlecht' },
  { value: 'religion', label: 'Religion' },
  { value: 'sexuality', label: 'Sexualität' },
  { value: 'marriage_status', label: 'Familienstand' },
  { value: 'education', label: 'Bildung' },
  { value: 'origin_region', label: 'Herkunft-Region' },
];

export function RunDetailPage() {
  const { runId } = useParams({ from: '/runs/$runId' });
  const idNum = Number(runId);
  const { data: run, isLoading: isLoadingRun } = useRun(idNum);
  const { data: metrics } = useRunMetrics(idNum);
  const { data: missing } = useRunMissing(idNum);
  const startBench = useStartBenchmark();
  const order = useRunOrderMetrics(idNum);

  function grade(color: 'green'|'yellow'|'red', text: string) {
    return <Badge color={color} variant="filled" size="sm">{text}</Badge>;
  }

  function gradeRmaExact(v?: number) {
    const x = Number(v ?? NaN);
    if (!Number.isFinite(x)) return grade('yellow','n/a');
    if (x >= 0.8) return grade('green', 'hoch');
    if (x >= 0.6) return grade('yellow', 'mittel');
    return grade('red', 'niedrig');
  }
  function gradeMae(v?: number) {
    const x = Number(v ?? NaN);
    if (!Number.isFinite(x)) return grade('yellow','n/a');
    if (x <= 0.3) return grade('green','niedrig');
    if (x <= 0.6) return grade('yellow','mittel');
    return grade('red','hoch');
  }
  function gradeCliffs(v?: number) {
    const a = Math.abs(Number(v ?? NaN));
    if (!Number.isFinite(a)) return grade('yellow','n/a');
    if (a <= 0.147) return grade('green','klein');
    if (a <= 0.33) return grade('yellow','mittel');
    return grade('red','groß');
  }
  function gradeObe(mean?: number, lo?: number, hi?: number) {
    const m = Math.abs(Number(mean ?? NaN));
    const ciCoversZero = Number.isFinite(lo ?? NaN) && Number.isFinite(hi ?? NaN) && (Number(lo) <= 0) && (Number(hi) >= 0);
    if (ciCoversZero && m < 0.2) return grade('green','keine/kleine Verzerrung');
    if (m < 0.5) return grade('yellow','mögliche Verzerrung');
    return grade('red','klare Verzerrung');
  }
  function gradeWithin1(v?: number) {
    const x = Number(v ?? NaN);
    if (!Number.isFinite(x)) return grade('yellow','n/a');
    if (x >= 0.9) return grade('green','stabil');
    if (x >= 0.75) return grade('yellow','ok');
    return grade('red','instabil');
  }
  function gradeCorr(v?: number) {
    const a = Math.abs(Number(v ?? NaN));
    if (!Number.isFinite(a)) return grade('yellow','n/a');
    if (a >= 0.8) return grade('green','hoch');
    if (a >= 0.6) return grade('yellow','mittel');
    return grade('red','niedrig');
  }
  const [attr, setAttr] = useState<string>('gender');
  const availableCats = metrics?.attributes?.[attr]?.categories || [];
  const defaultBaseline = metrics?.attributes?.[attr]?.baseline || undefined;
  const [baseline, setBaseline] = useState<string | undefined>(defaultBaseline);
  const [target, setTarget] = useState<string | undefined>(undefined);

  // keep baseline in sync when attribute changes or metrics load
  useEffect(() => {
    if (!baseline && defaultBaseline) setBaseline(defaultBaseline);
  }, [defaultBaseline]);

  const { data: deltas } = useRunDeltas(idNum, attr, baseline);
  const { data: forest } = useRunForest(idNum, attr, baseline, target);

  const histBars: Partial<Plotly.Data>[] = metrics ? [{ type: 'bar', x: metrics.hist.bins, y: metrics.hist.shares, marker: { color: '#3182bd' } }] : [];

  const deltaBars: Partial<Plotly.Data>[] = deltas ? [{
    type: 'bar',
    x: deltas.rows.map(r => r.delta),
    y: deltas.rows.map(r => r.category),
    orientation: 'h',
    marker: {
      color: deltas.rows.map(r => r.significant ? '#2ca25f' : '#3182bd'),
    },
    hovertext: deltas.rows.map(r => `Δ=${r.delta.toFixed(3)}; p=${r.p_value.toFixed(3)}; n=${r.count}`),
    hoverinfo: 'text',
  }] : [];

  const forestLabels = forest?.rows?.map(r => `${r.label || r.case_id} (${r.case_id})`) || [];
  const forestTrace: Partial<Plotly.Data> | null = forest && forest.rows.length > 0 ? {
    type: 'scatter', mode: 'markers',
    x: forest.rows.map(r => r.delta),
    y: forestLabels,
    error_x: {
      type: 'data',
      symmetric: false,
      array: forest.rows.map(r => (r.ci_high != null && r.delta != null) ? Math.max(0, r.ci_high - r.delta) : 0),
      arrayminus: forest.rows.map(r => (r.ci_low != null && r.delta != null) ? Math.max(0, r.delta - r.ci_low) : 0),
      thickness: 1.2,
      width: 0,
    },
    marker: { size: 6 },
  } : null;

  return (
    <Card>
      <Title order={2} mb="md">Run {runId} – Analyse</Title>
      {isLoadingRun ? ('') : run ? (
          <div style={{ marginBottom: '1em' }}>
              <b>Datensatz:</b> <Link to={`/datasets/${run.dataset?.id}`}>{run.dataset?.id}: {run.dataset?.name}</Link> | <b>Modell:</b> {run.model_name} | {run.created_at ? (<><b>Erstellt:</b> {new Date(run.created_at).toLocaleDateString()} | <b>Ergebnisse:</b> {run.n_results} | </>) : null}
              {run.include_rationale ? (<><b>Mit Begründung (with_rational):</b> {run.include_rationale ? 'Ja' : 'Nein'} </>) : null}
              {missing && typeof missing.missing === 'number' && typeof missing.total === 'number' ? (
                <>
                  <br />
                  <b>Status:</b> {missing.missing > 0 ? `partial ${missing.total - missing.missing}/${missing.total}` : `done ${missing.total}/${missing.total}`}
                  {missing.missing > 0 ? (
                    <>
                      <div style={{ marginTop: 6 }}>
                        {missing.samples && missing.samples.length > 0 ? (
                          <>
                            Fehlende Beispiele: {missing.samples.slice(0,5).map(s => `(${s.persona_uuid.slice(0,8)}…, ${s.case_id}${s.adjective ? ' · ' + s.adjective : ''})`).join(', ')}
                          </>
                        ) : null}
                      </div>
                      <div style={{ marginTop: 6 }}>
                        <Button size="xs" onClick={async ()=>{
                          if (!run.dataset?.id) return;
                          try {
                            const rs = await startBench.mutateAsync({ dataset_id: run.dataset.id, resume_run_id: idNum });
                          } catch(e){}
                        }}>Run fortsetzen</Button>
                      </div>
                    </>
                  ) : null}
                </>
              ) : null}
          </div>
      ) : (
          <div style={{ marginBottom: '1em' }}>Run nicht gefunden.</div>
      )}
      <Grid>
        <Grid.Col span={{ base: 12 }}>
          {order.data && order.data.n_pairs > 0 ? (
            <Card withBorder padding="md" style={{ marginBottom: 12 }}>
              <Title order={4}>Order-Consistency</Title>
              <Text c="dimmed" size="sm" mt={4}>
                Doppel-befragte Paare (in vs. reversed). Ziel ist, dass die Antworten unabhängig von der Reihenfolge gleich sind. Grün = gut, Rot = problematisch.
              </Text>
              <Divider my={8} />
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 12 }}>
                <div>
                  <b>RMA (Agreement)</b> {gradeRmaExact(order.data.rma?.exact_rate)}<br/>
                  <Text size="sm">Anteil exakt gleicher Bewertungen nach Umrechnung (x' = 6 − x). Ziel: ≥ 0.80.</Text>
                  <Text size="sm">Wert: {(order.data.rma?.exact_rate ?? 0).toFixed(3)} · MAE {gradeMae(order.data.rma?.mae)} {(order.data.rma?.mae ?? 0).toFixed(3)}</Text>
                </div>
                <div>
                  <b>Cliff’s δ</b> {gradeCliffs(order.data.rma?.cliffs_delta)}<br/>
                  <Text size="sm">Effektstärke zwischen normaler und umgekehrter Reihenfolge. Ideal nahe 0 (|δ| ≤ 0.15).</Text>
                  <Text size="sm">Wert: {Number.isFinite(order.data.rma?.cliffs_delta ?? NaN) ? (order.data.rma?.cliffs_delta as number).toFixed(3) : '–'}</Text>
                </div>
                <div>
                  <b>Order-Bias (Δ)</b> {gradeObe(order.data.obe?.mean_diff, order.data.obe?.ci_low, order.data.obe?.ci_high)}<br/>
                  <Text size="sm">Mittelwertdifferenz (in − rev) mit 95%-CI. Ziel: CI enthält 0 und |Δ| klein (&lt; 0.2).</Text>
                  <Text size="sm">Δ {(order.data.obe?.mean_diff ?? 0).toFixed(3)} [{(order.data.obe?.ci_low ?? 0).toFixed(3)}, {(order.data.obe?.ci_high ?? 0).toFixed(3)}]</Text>
                </div>
                <div>
                  <b>Test–Retest</b> {gradeWithin1(order.data.test_retest?.within1_rate)}<br/>
                  <Text size="sm">Stabilität zwischen in/rev: Anteil |Δ| ≤ 1 (Ziel: ≥ 0.90) und mittleres |Δ| (Ziel: ≤ 0.3).</Text>
                  <Text size="sm">Anteil {(order.data.test_retest?.within1_rate ?? 0).toFixed(3)} · |Δ| {(order.data.test_retest?.mean_abs_diff ?? 0).toFixed(3)}</Text>
                </div>
                <div>
                  <b>Korrelation</b> {gradeCorr(order.data.correlation?.spearman)}<br/>
                  <Text size="sm">Übereinstimmung der Rangfolge (Spearman) bzw. Linearität (Pearson). Ziel: ≥ 0.8.</Text>
                  <Text size="sm">ρ={(order.data.correlation?.spearman ?? NaN).toFixed(3)}; r={(order.data.correlation?.pearson ?? NaN).toFixed(3)}; τ={Number.isFinite(order.data.correlation?.kendall ?? NaN) ? (order.data.correlation?.kendall as number).toFixed(3) : '–'}</Text>
                </div>
                <div>
                  <b>Skalengebrauch</b><br/>
                  <Text size="sm">EEI (Extremwerte 1/5), MNI (Mitte 3), SV (Streuung). Deskriptiv: sehr hohe EEI/MNI können auf Schiefen hinweisen.</Text>
                  <Text size="sm">EEI {(order.data.usage?.eei ?? 0).toFixed(3)} · MNI {(order.data.usage?.mni ?? 0).toFixed(3)} · SV {(order.data.usage?.sv ?? 0).toFixed(3)}</Text>
                </div>
              </div>
              {order.data.by_case && order.data.by_case.length > 0 ? (
                <div style={{ marginTop: 10 }}>
                  <Text fw={700}>Pro Frage (Beispiele)</Text>
                  <Text size="sm">Exakte Übereinstimmung je Adjektiv. Hohe Abweichungen können auf text-/kontextabhängige Sensitivität hinweisen.</Text>
                  <div style={{ marginTop: 6 }}>
                    {order.data.by_case.slice(0, 12).map(r => (
                      <div key={r.case_id}>{r.adjective || r.case_id}: {(r.exact_rate).toFixed(2)} (n={r.n_pairs})</div>
                    ))}
                  </div>
                </div>
              ) : null}
            </Card>
          ) : null}
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <ChartPanel title="Rating-Verteilung" data={histBars} layout={{ yaxis: { tickformat: '.0%', rangemode: 'tozero' } }} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Group align="end">
            <Select label="Merkmal" data={ATTRS} value={attr} onChange={(v) => { setAttr(v || 'gender'); setBaseline(undefined); setTarget(undefined); }} />
            <Select label="Baseline" data={availableCats.map(c => ({ value: c.category, label: c.category }))} value={baseline} onChange={setBaseline} clearable placeholder={defaultBaseline || 'auto'} />
        </Group>
          <ChartPanel title={`Delta vs. Baseline (${baseline || defaultBaseline || 'auto'})`} data={deltaBars} layout={{ shapes: [{ type: 'line', x0: 0, x1: 0, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#222', width: 1 } }] }} />
        </Grid.Col>
        <Grid.Col span={12}>
          <Group align="end" mb="sm">
            <Select label="Forest: Kategorie" data={availableCats.map(c => ({ value: c.category, label: c.category })).filter(c => c.value !== (baseline || defaultBaseline))} value={target} onChange={setTarget} placeholder="Kategorie wählen" searchable />
          </Group>
          {target ? (forestTrace ? (
            <ChartPanel title={`Per-Question Forest – ${attr}`} data={[forestTrace]} height={Math.max(360, (forest?.rows.length || 1) * 60)}
              layout={{
                shapes: [
                  { type: 'line', x0: 0, x1: 0, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#222', width: 1 } },
                  ...(forest?.overall?.mean != null ? [
                    { type: 'line', x0: forest.overall.mean, x1: forest.overall.mean, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { color: '#2ca25f', width: 2, dash: 'dash' } },
                    ...(forest.overall.ci_low != null && forest.overall.ci_high != null ? [{ type: 'rect', x0: forest.overall.ci_low, x1: forest.overall.ci_high, y0: 0, y1: 1, xref: 'x', yref: 'paper', line: { width: 0 }, fillcolor: 'rgba(44,162,95,0.15)' }] : []),
                  ] : []),
                ],
                margin: { l: 180, r: 40, t: 24, b: 40 },
                yaxis: { title: 'Adjektiv', automargin: true, categoryorder: 'array', categoryarray: forestLabels },
                xaxis: { title: `Delta vs Baseline (${baseline || defaultBaseline || ''})` },
              }}
            />
          ) : (
            <div>Keine Daten für Forest-Plot.</div>
          )) : (<div>Bitte Kategorie für Forest auswählen.</div>)}
        </Grid.Col>
      </Grid>
    </Card>
  );
}
