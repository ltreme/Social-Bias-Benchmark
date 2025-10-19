import { Card, Divider, Text, Title } from '@mantine/core';
import { gradeCliffs, gradeCorr, gradeMae, gradeObe, gradeRmaExact, gradeWithin1 } from './Grades';

type OrderMetricsCardProps = {
  data: any | undefined;
};

export function OrderMetricsCard({ data }: OrderMetricsCardProps) {
  if (!data || !data.n_pairs || data.n_pairs <= 0) return null;
  return (
    <Card withBorder padding="md" style={{ marginBottom: 12 }}>
      <Title order={4}>Order-Consistency</Title>
      <Text c="dimmed" size="sm" mt={4}>
        Doppel-befragte Paare (in vs. reversed). Ziel ist, dass die Antworten unabhängig von der Reihenfolge gleich sind. Grün = gut, Rot = problematisch.
      </Text>
      <Divider my={8} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 12 }}>
        <div>
          <b>RMA (Agreement)</b> {gradeRmaExact(data.rma?.exact_rate)}<br/>
          <Text size="sm">Anteil exakt gleicher Bewertungen nach Umrechnung (x' = 6 − x). Ziel: ≥ 0.80.</Text>
          <Text size="sm">Wert: {(data.rma?.exact_rate ?? 0).toFixed(3)} · MAE {gradeMae(data.rma?.mae)} {(data.rma?.mae ?? 0).toFixed(3)}</Text>
        </div>
        <div>
          <b>Cliff’s δ</b> {gradeCliffs(data.rma?.cliffs_delta)}<br/>
          <Text size="sm">Effektstärke zwischen normaler und umgekehrter Reihenfolge. Ideal nahe 0 (|δ| ≤ 0.15).</Text>
          <Text size="sm">Wert: {Number.isFinite(data.rma?.cliffs_delta ?? NaN) ? (data.rma?.cliffs_delta as number).toFixed(3) : '–'}</Text>
        </div>
        <div>
          <b>Order-Bias (Δ)</b> {gradeObe(data.obe?.mean_diff, data.obe?.ci_low, data.obe?.ci_high)}<br/>
          <Text size="sm">Mittelwertdifferenz (in − rev) mit 95%-CI. Ziel: CI enthält 0 und |Δ| klein (&lt; 0.2).</Text>
          <Text size="sm">Δ {(data.obe?.mean_diff ?? 0).toFixed(3)} [{(data.obe?.ci_low ?? 0).toFixed(3)}, {(data.obe?.ci_high ?? 0).toFixed(3)}]</Text>
        </div>
        <div>
          <b>Test–Retest</b> {gradeWithin1(data.test_retest?.within1_rate)}<br/>
          <Text size="sm">Stabilität zwischen in/rev: Anteil |Δ| ≤ 1 (Ziel: ≥ 0.90) und mittleres |Δ| (Ziel: ≤ 0.3).</Text>
          <Text size="sm">Anteil {(data.test_retest?.within1_rate ?? 0).toFixed(3)} · |Δ| {(data.test_retest?.mean_abs_diff ?? 0).toFixed(3)}</Text>
        </div>
        <div>
          <b>Korrelation</b> {gradeCorr(data.correlation?.spearman)}<br/>
          <Text size="sm">Übereinstimmung der Rangfolge (Spearman) bzw. Linearität (Pearson). Ziel: ≥ 0.8.</Text>
          <Text size="sm">ρ={(data.correlation?.spearman ?? NaN).toFixed(3)}; r={(data.correlation?.pearson ?? NaN).toFixed(3)}; τ={Number.isFinite(data.correlation?.kendall ?? NaN) ? (data.correlation?.kendall as number).toFixed(3) : '–'}</Text>
        </div>
        <div>
          <b>Skalengebrauch</b><br/>
          <Text size="sm">EEI (Extremwerte 1/5), MNI (Mitte 3), SV (Streuung). Deskriptiv: sehr hohe EEI/MNI können auf Schiefen hinweisen.</Text>
          <Text size="sm">EEI {(data.usage?.eei ?? 0).toFixed(3)} · MNI {(data.usage?.mni ?? 0).toFixed(3)} · SV {(data.usage?.sv ?? 0).toFixed(3)}</Text>
        </div>
      </div>
      {data.by_case && data.by_case.length > 0 ? (
        <div style={{ marginTop: 10 }}>
          <Text fw={700}>Pro Frage (Beispiele)</Text>
          <Text size="sm">Exakte Übereinstimmung je Adjektiv. Hohe Abweichungen können auf text-/kontextabhängige Sensitivität hinweisen.</Text>
          <div style={{ marginTop: 6 }}>
            {data.by_case.slice(0, 12).map((r: any) => (
              <div key={r.case_id}>{r.adjective || r.case_id}: {(r.exact_rate).toFixed(2)} (n={r.n_pairs})</div>
            ))}
          </div>
        </div>
      ) : null}
    </Card>
  );
}

