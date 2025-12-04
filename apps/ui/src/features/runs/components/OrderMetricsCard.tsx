import { Divider, Text, Title, Paper, Group, Stack, ThemeIcon, SimpleGrid, Tooltip, ActionIcon, Progress, Badge } from '@mantine/core';
import { IconArrowsSort, IconScale, IconChartLine, IconRepeat, IconInfoCircle, IconTarget, IconChartBar } from '@tabler/icons-react';
import { gradeCliffs, gradeCorr, gradeObe, gradeRmaExact, gradeWithin1 } from './Grades';
import { useThemedColor } from '../../../lib/useThemeColors';

type OrderMetricsCardProps = {
  data: any | undefined;
};

function MetricCard({ 
  icon: Icon, 
  color, 
  title, 
  tooltip, 
  value, 
  subValue,
  grade,
  progress,
}: {
  icon: any;
  color: string;
  title: string;
  tooltip: string;
  value: string;
  subValue?: string;
  grade?: React.ReactNode;
  progress?: { value: number; color: string };
}) {
  return (
    <Paper p="md" withBorder radius="md">
      <Group justify="space-between" align="flex-start" mb="sm">
        <Group gap="sm">
          <ThemeIcon size={36} radius="md" variant="light" color={color}>
            <Icon size={20} />
          </ThemeIcon>
          <div>
            <Text size="sm" fw={600}>{title}</Text>
            {grade}
          </div>
        </Group>
        <Tooltip label={tooltip} multiline w={280} withArrow>
          <ActionIcon variant="subtle" color="gray" size="sm">
            <IconInfoCircle size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>
      {progress && (
        <Progress value={progress.value} color={progress.color} size="sm" radius="xl" mb="xs" />
      )}
      <Text size="xl" fw={700} c={`${color}.7`}>{value}</Text>
      {subValue && <Text size="xs" c="dimmed">{subValue}</Text>}
    </Paper>
  );
}

export function OrderMetricsCard({ data }: OrderMetricsCardProps) {
  const getColor = useThemedColor();
  
  if (!data || !data.n_pairs || data.n_pairs <= 0) return null;
  
  const rmaValue = data.rma?.exact_rate ?? 0;
  const maeValue = data.rma?.mae ?? 0;
  const cliffsValue = data.rma?.cliffs_delta;
  const within1Value = data.test_retest?.within1_rate ?? 0;
  const spearmanValue = data.correlation?.spearman ?? 0;

  // Calculate progress colors based on grades
  const getRmaColor = (v: number) => v >= 0.8 ? 'teal' : v >= 0.6 ? 'yellow' : 'red';
  const getWithin1Color = (v: number) => v >= 0.9 ? 'teal' : v >= 0.75 ? 'yellow' : 'red';
  const getCorrColor = (v: number) => Math.abs(v) >= 0.8 ? 'teal' : Math.abs(v) >= 0.6 ? 'yellow' : 'red';

  return (
    <Stack gap="md">
      {/* Header */}
      <Paper p="md" withBorder radius="md">
        <Group gap="sm" mb="xs">
          <ThemeIcon size="lg" radius="md" variant="light" color="indigo">
            <IconArrowsSort size={20} />
          </ThemeIcon>
          <div>
            <Title order={4}>Order-Consistency</Title>
            <Text size="sm" c="dimmed">
              Basierend auf {data.n_pairs?.toLocaleString('de-DE')} Dual-Paaren (in vs. reversed)
            </Text>
          </div>
        </Group>
        <Text size="xs" c="dimmed">
          Ziel: Antworten sollen unabhängig von der Reihenfolge der Skala gleich sein. Grün = gut, Rot = problematisch.
        </Text>
      </Paper>

      {/* Main Metrics Grid */}
      <SimpleGrid cols={{ base: 1, sm: 2, lg: 3 }} spacing="md">
        <MetricCard
          icon={IconTarget}
          color="blue"
          title="RMA (Agreement)"
          tooltip="Anteil exakt gleicher Bewertungen nach Umrechnung (x' = 6 − x). Ziel: ≥ 0.80 für hohe Konsistenz."
          value={rmaValue.toFixed(3)}
          subValue={`MAE: ${maeValue.toFixed(3)}`}
          grade={gradeRmaExact(rmaValue)}
          progress={{ value: rmaValue * 100, color: getRmaColor(rmaValue) }}
        />

        <MetricCard
          icon={IconScale}
          color="violet"
          title="Cliff's δ"
          tooltip="Effektstärke zwischen normaler und umgekehrter Reihenfolge. Ideal nahe 0 (|δ| ≤ 0.15 = klein)."
          value={Number.isFinite(cliffsValue) ? cliffsValue.toFixed(3) : '–'}
          grade={gradeCliffs(cliffsValue)}
          progress={Number.isFinite(cliffsValue) ? { 
            value: Math.min(Math.abs(cliffsValue) * 100, 100), 
            color: Math.abs(cliffsValue) <= 0.147 ? 'teal' : Math.abs(cliffsValue) <= 0.33 ? 'yellow' : 'red'
          } : undefined}
        />

        <MetricCard
          icon={IconChartLine}
          color="orange"
          title="Order-Bias (Δ)"
          tooltip="Mittelwertdifferenz (in − rev) mit 95%-CI. Ziel: CI enthält 0 und |Δ| klein (< 0.2)."
          value={`Δ ${(data.obe?.mean_diff ?? 0).toFixed(3)}`}
          subValue={`CI: [${(data.obe?.ci_low ?? 0).toFixed(3)}, ${(data.obe?.ci_high ?? 0).toFixed(3)}]`}
          grade={gradeObe(data.obe?.mean_diff, data.obe?.ci_low, data.obe?.ci_high)}
        />

        <MetricCard
          icon={IconRepeat}
          color="teal"
          title="Test-Retest"
          tooltip="Stabilität zwischen in/rev: Anteil |Δ| ≤ 1 (Ziel: ≥ 0.90) und mittleres |Δ| (Ziel: ≤ 0.3)."
          value={(within1Value * 100).toFixed(1) + '%'}
          subValue={`Mittl. |Δ|: ${(data.test_retest?.mean_abs_diff ?? 0).toFixed(3)}`}
          grade={gradeWithin1(within1Value)}
          progress={{ value: within1Value * 100, color: getWithin1Color(within1Value) }}
        />

        <MetricCard
          icon={IconChartLine}
          color="grape"
          title="Korrelation"
          tooltip="Übereinstimmung der Rangfolge (Spearman ρ) bzw. Linearität (Pearson r). Ziel: ≥ 0.8."
          value={`ρ = ${spearmanValue.toFixed(3)}`}
          subValue={`r = ${(data.correlation?.pearson ?? 0).toFixed(3)}, τ = ${Number.isFinite(data.correlation?.kendall) ? data.correlation.kendall.toFixed(3) : '–'}`}
          grade={gradeCorr(spearmanValue)}
          progress={{ value: Math.abs(spearmanValue) * 100, color: getCorrColor(spearmanValue) }}
        />

        <MetricCard
          icon={IconChartBar}
          color="pink"
          title="Skalengebrauch"
          tooltip="EEI (Extremwerte 1/5), MNI (Mitte 3), SV (Streuung). Deskriptiv: sehr hohe EEI/MNI können auf Schiefen hinweisen."
          value={`EEI ${(data.usage?.eei ?? 0).toFixed(2)}`}
          subValue={`MNI ${(data.usage?.mni ?? 0).toFixed(2)} · SV ${(data.usage?.sv ?? 0).toFixed(2)}`}
        />
      </SimpleGrid>

      {/* By Case / By Trait Category */}
      {(data.by_case?.length > 0 || data.by_trait_category?.length > 0) && (
        <Paper p="md" withBorder radius="md">
          {data.by_trait_category && data.by_trait_category.length > 0 && (
            <>
              <Title order={5} mb="sm">Nach Trait-Kategorie</Title>
              <Text size="xs" c="dimmed" mb="md">
                Aggregierte Order-Consistency getrennt nach Trait-Kategorien
              </Text>
              <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} spacing="sm" mb="md">
                {data.by_trait_category.map((cat: any) => (
                  <Paper key={cat.trait_category} p="sm" bg={getColor('gray').bg} radius="md">
                    <Text size="sm" fw={600}>{cat.trait_category}</Text>
                    <Group gap="xs" mt={4}>
                      <Badge size="xs" variant="light" color="gray">n={cat.n_pairs}</Badge>
                    </Group>
                    <Group gap="md" mt="xs">
                      <div>
                        <Text size="xs" c="dimmed">Exact</Text>
                        <Text size="sm" fw={500}>{(cat.exact_rate ?? 0).toFixed(3)}</Text>
                      </div>
                      <div>
                        <Text size="xs" c="dimmed">MAE</Text>
                        <Text size="sm" fw={500}>{(cat.mae ?? 0).toFixed(3)}</Text>
                      </div>
                    </Group>
                  </Paper>
                ))}
              </SimpleGrid>
            </>
          )}

          {data.by_case && data.by_case.length > 0 && (
            <>
              {data.by_trait_category?.length > 0 && <Divider my="md" />}
              <Title order={5} mb="sm">Pro Trait</Title>
              <Text size="xs" c="dimmed" mb="md">
                Exakte Übereinstimmung je Trait. Hohe Abweichungen können auf text-/kontextabhängige Sensitivität hinweisen.
              </Text>
              <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} spacing="xs">
                {data.by_case.map((r: any) => (
                  <Paper key={r.case_id} p="xs" bg={getColor('gray').bg} radius="sm">
                    <Group justify="space-between" wrap="nowrap">
                      <Text size="xs" truncate style={{ maxWidth: 120 }}>{r.adjective || r.case_id}{r.case_id ? ` (${r.case_id})` : ''}</Text>
                      <Group gap={4}>
                        <Text size="xs" fw={600}>{(r.exact_rate).toFixed(2)}</Text>
                        <Text size="xs" c="dimmed">(n={r.n_pairs})</Text>
                      </Group>
                    </Group>
                  </Paper>
                ))}
              </SimpleGrid>
            </>
          )}
        </Paper>
      )}
    </Stack>
  );
}
