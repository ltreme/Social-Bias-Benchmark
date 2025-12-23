import { Divider, Text, Title, Paper, Group, Stack, ThemeIcon, SimpleGrid, Tooltip, ActionIcon, Progress, Badge, Button } from '@mantine/core';
import { IconArrowsSort, IconScale, IconChartLine, IconRepeat, IconInfoCircle, IconTarget, IconChartBar, IconCopy } from '@tabler/icons-react';
import { gradeCliffs, gradeCorr, gradeObe, gradeRmaExact, gradeWithin1 } from './Grades';
import { useThemedColor } from '../../../lib/useThemeColors';import { notifications } from '@mantine/notifications';
type OrderMetricsCardProps = {
  data: any | undefined;
};

function MetricValueWithProgress({ 
  label, 
  value, 
  progressValue,
  color,
  tooltip,
  icon: Icon,
}: {
  label: string;
  value: string;
  progressValue?: number;
  color?: string;
  tooltip?: string;
  icon: any;
}) {
  return (
    <Paper p="sm" withBorder radius="md">
      <Group justify="space-between" align="flex-start" mb="xs">
        <Group gap="xs" wrap="nowrap" style={{ flex: 1 }}>
          <ThemeIcon size="md" radius="md" variant="light" color="blue" style={{ flexShrink: 0 }}>
            <Icon size={16} />
          </ThemeIcon>
          <div style={{ minWidth: 0 }}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700} lh={1}>{label}</Text>
            <Text size="lg" fw={700} c={color} lh={1.2} mt={6}>{value}</Text>
          </div>
        </Group>
        {tooltip && (
          <Tooltip label={tooltip} multiline w={200} withArrow>
            <ActionIcon variant="subtle" color="gray" size="xs" style={{ flexShrink: 0 }}>
              <IconInfoCircle size={14} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
      {progressValue !== undefined && (
        <Progress value={progressValue} size="sm" radius="md" mt={8} />
      )}
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
  const pearsonValue = data.correlation?.pearson ?? 0;

  const getRmaColor = (v: number) => v >= 0.8 ? 'teal' : v >= 0.6 ? 'yellow' : 'red';
  const getMaeColor = (v: number) => v <= 0.3 ? 'teal' : v <= 0.6 ? 'yellow' : 'red';
  const getWithin1Color = (v: number) => v >= 0.9 ? 'teal' : v >= 0.75 ? 'yellow' : 'red';
  const getCorrColor = (v: number) => Math.abs(v) >= 0.8 ? 'teal' : Math.abs(v) >= 0.6 ? 'yellow' : 'red';

  const handleCopyLatex = async () => {
    const lines: string[] = [];
    
    lines.push('\\begin{table}[htbp]');
    lines.push('\\centering');
    lines.push('\\caption{Order-Consistency Metriken}');
    lines.push('\\label{tab:order_consistency}');
    lines.push('\\begin{tabular}{lr}');
    lines.push('\\toprule');
    lines.push('Metrik & Wert \\\\');
    lines.push('\\midrule');
    
    // Add metrics
    lines.push(`RMA & ${rmaValue.toFixed(3)} \\\\`);
    lines.push(`MAE & ${maeValue.toFixed(3)} \\\\`);
    
    if (Number.isFinite(cliffsValue)) {
      lines.push(`Cliff's $\\delta$ & ${cliffsValue.toFixed(3)} \\\\`);
    }
    
    const obeMean = data.obe?.mean_diff ?? 0;
    const obeCiLow = data.obe?.ci_low ?? 0;
    const obeCiHigh = data.obe?.ci_high ?? 0;
    lines.push(`Order-Bias ($\\Delta$) & ${obeMean.toFixed(3)} \\\\`);
    lines.push(`Order-Bias CI & [${obeCiLow.toFixed(2)}, ${obeCiHigh.toFixed(2)}] \\\\`);
    
    lines.push(`Test-Retest & ${(within1Value * 100).toFixed(1)}\\% \\\\`);
    lines.push(`Spearman $\\rho$ & ${spearmanValue.toFixed(3)} \\\\`);
    lines.push(`Pearson $r$ & ${pearsonValue.toFixed(3)} \\\\`);
    
    const kendallValue = data.correlation?.kendall;
    if (Number.isFinite(kendallValue)) {
      lines.push(`Kendall $\\tau$ & ${kendallValue.toFixed(3)} \\\\`);
    }
    
    lines.push('\\bottomrule');
    lines.push('\\end{tabular}');
    lines.push('\\end{table}');
    
    const latex = lines.join('\n');
    
    try {
      await navigator.clipboard.writeText(latex);
      notifications.show({
        title: 'LaTeX kopiert',
        message: 'Tabelle wurde in die Zwischenablage kopiert',
        color: 'green',
      });
    } catch (err) {
      notifications.show({
        title: 'Fehler',
        message: 'Konnte nicht in die Zwischenablage kopieren',
        color: 'red',
      });
    }
  };

  return (
    <Stack gap="md">
      {/* Header */}
      <Paper p="md" withBorder radius="md">
        <Group justify="space-between" align="flex-start">
          <Group gap="sm">
            <ThemeIcon size="lg" radius="md" variant="light" color="indigo">
              <IconArrowsSort size={20} />
            </ThemeIcon>
            <div>
              <Title order={4}>Order-Consistency</Title>
              <Text size="sm" c="dimmed">
                {data.n_pairs?.toLocaleString('de-DE')} Dual-Paare (in vs. reversed)
              </Text>
            </div>
          </Group>
          <Button
            leftSection={<IconCopy size={16} />}
            variant="light"
            size="sm"
            onClick={handleCopyLatex}
          >
            LaTeX kopieren
          </Button>
        </Group>
      </Paper>

      {/* Main Metrics Grid - Compact */}
      <SimpleGrid cols={{ base: 1, xs: 2, md: 3 }} spacing="sm">
        <MetricValueWithProgress
          icon={IconTarget}
          label="RMA"
          value={rmaValue.toFixed(3)}
          progressValue={rmaValue * 100}
          color={`${getRmaColor(rmaValue)}.7`}
          tooltip="Anteil exakt gleicher Bewertungen. Ziel: ≥ 0.80"
        />

        <MetricValueWithProgress
          icon={IconScale}
          label="Cliff's δ"
          value={Number.isFinite(cliffsValue) ? cliffsValue.toFixed(3) : '–'}
          color={Number.isFinite(cliffsValue) ? (Math.abs(cliffsValue) <= 0.147 ? 'teal' : Math.abs(cliffsValue) <= 0.33 ? 'yellow' : 'red') + '.7' : undefined}
          tooltip="Effektstärke zwischen Ordnungen. Ideal: |δ| ≤ 0.15"
        />

        <Paper p="sm" withBorder radius="md">
          <Group justify="space-between" align="flex-start" mb="xs">
            <Group gap="xs" wrap="nowrap" style={{ flex: 1 }}>
              <ThemeIcon size="md" radius="md" variant="light" color="orange" style={{ flexShrink: 0 }}>
                <IconChartLine size={16} />
              </ThemeIcon>
              <div style={{ minWidth: 0 }}>
                <Text size="xs" c="dimmed" tt="uppercase" fw={700} lh={1}>Order-Bias (Δ)</Text>
                <Text size="lg" fw={700} lh={1.2} mt={6}>
                  {(data.obe?.mean_diff ?? 0).toFixed(3)}
                </Text>
                <Text size="xs" c="dimmed" mt={6}>
                  CI: [{(data.obe?.ci_low ?? 0).toFixed(2)}, {(data.obe?.ci_high ?? 0).toFixed(2)}]
                </Text>
              </div>
            </Group>
            <Tooltip label="Mittelwertdifferenz mit 95%-CI. Ziel: CI enthält 0 und |Δ| klein" multiline w={200} withArrow>
              <ActionIcon variant="subtle" color="gray" size="xs" style={{ flexShrink: 0 }}>
                <IconInfoCircle size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Paper>

        <MetricValueWithProgress
          icon={IconRepeat}
          label="Test-Retest"
          value={(within1Value * 100).toFixed(1) + '%'}
          progressValue={within1Value * 100}
          color={`${getWithin1Color(within1Value)}.7`}
          tooltip="Anteil Abweichungen ≤ 1. Ziel: ≥ 90%"
        />

        <MetricValueWithProgress
          icon={IconChartLine}
          label="Spearman ρ"
          value={spearmanValue.toFixed(3)}
          progressValue={Math.abs(spearmanValue) * 100}
          color={`${getCorrColor(spearmanValue)}.7`}
          tooltip="Spearman ρ für Rangfolge-Übereinstimmung. Ziel: ≥ 0.80"
        />

        <MetricValueWithProgress
          icon={IconChartLine}
          label="Pearson r"
          value={pearsonValue.toFixed(3)}
          progressValue={Math.abs(pearsonValue) * 100}
          color={`${getCorrColor(pearsonValue)}.7`}
          tooltip="Pearson r für lineare Korrelation. Ziel: ≥ 0.80"
        />

        <Paper p="sm" withBorder radius="md">
          <Group justify="space-between" align="flex-start" mb="xs">
            <Group gap="xs" wrap="nowrap" style={{ flex: 1 }}>
              <ThemeIcon size="md" radius="md" variant="light" color="pink" style={{ flexShrink: 0 }}>
                <IconChartBar size={16} />
              </ThemeIcon>
              <div style={{ minWidth: 0 }}>
                <Text size="xs" c="dimmed" tt="uppercase" fw={700} lh={1}>Skalengebrauch</Text>
                <Text size="lg" fw={700} lh={1.2} mt={6}>
                  EEI {(data.usage?.eei ?? 0).toFixed(2)}
                </Text>
                <Text size="xs" c="dimmed" mt={6}>
                  MNI {(data.usage?.mni ?? 0).toFixed(2)} · SV {(data.usage?.sv ?? 0).toFixed(2)}
                </Text>
              </div>
            </Group>
            <Tooltip label="EEI = Extremwerte, MNI = Mitte, SV = Streuung" multiline w={200} withArrow>
              <ActionIcon variant="subtle" color="gray" size="xs" style={{ flexShrink: 0 }}>
                <IconInfoCircle size={14} />
              </ActionIcon>
            </Tooltip>
          </Group>
        </Paper>
      </SimpleGrid>

      {/* By Case / By Trait Category */}
      {(data.by_case?.length > 0 || data.by_trait_category?.length > 0) && (
        <Paper p="md" withBorder radius="md">
          {data.by_trait_category && data.by_trait_category.length > 0 && (
            <>
              <Group gap="xs" mb="sm" align="center">
                <Title order={5} mb={0}>Nach Trait-Kategorie</Title>
                <Tooltip label="MAE pro Kategorie. Grün = konsistent, Rot = inkonsistent." multiline w={200} withArrow>
                  <ActionIcon variant="subtle" color="gray" size={18}>
                    <IconInfoCircle size={14} />
                  </ActionIcon>
                </Tooltip>
              </Group>
              <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} spacing="sm" mb="md">
                {data.by_trait_category.map((cat: any) => {
                  const maeColor = cat.abs_diff <= 0.3 ? 'teal' : cat.abs_diff <= 0.6 ? 'yellow' : 'red';
                  return (
                    <Paper key={cat.trait_category} p="xs" bg={getColor('gray').bg} radius="md">
                      <Text size="xs" fw={600} truncate>{cat.trait_category}</Text>
                      <Group gap="xs" mt={4} justify="space-between" wrap="nowrap">
                        <Badge size="xs" variant="light" color="gray">n={cat.n}</Badge>
                        <Text size="xs" fw={700} c={`${maeColor}.7`}>{(cat.abs_diff ?? 0).toFixed(3)}</Text>
                      </Group>
                    </Paper>
                  );
                })}
              </SimpleGrid>
            </>
          )}

          {data.by_case && data.by_case.length > 0 && (
            <>
              {data.by_trait_category?.length > 0 && <Divider my="md" />}
              <Group gap="xs" mb="sm" align="center">
                <Title order={5} mb={0}>Pro Trait</Title>
                <Tooltip label="MAE und RMA pro Trait. Rot = Konsistenzprobleme." multiline w={200} withArrow>
                  <ActionIcon variant="subtle" color="gray" size={18}>
                    <IconInfoCircle size={14} />
                  </ActionIcon>
                </Tooltip>
              </Group>
              <SimpleGrid cols={{ base: 2, sm: 3, md: 4 }} spacing="xs">
                {data.by_case.map((r: any) => {
                  const maeColor = r.abs_diff <= 0.3 ? 'teal' : r.abs_diff <= 0.6 ? 'yellow' : 'red';
                  return (
                    <Paper key={r.case_id} p="xs" bg={getColor('gray').bg} radius="sm">
                      <Text size="xs" fw={600} truncate>{r.label || r.case_id}</Text>
                      <Group gap={4} mt={3} wrap="nowrap">
                        <Badge size="xs" variant="dot" color="gray">n={r.n ?? 0}</Badge>
                      </Group>
                      <Group gap={6} mt={2} wrap="wrap">
                        <Group gap={3} wrap="nowrap">
                          <Text size="xs" c="dimmed">MAE</Text>
                          <Text size="xs" fw={700} c={`${maeColor}.7`}>{(r.abs_diff ?? 0).toFixed(2)}</Text>
                        </Group>
                        {r.rma !== undefined && r.rma !== null && (
                          <Group gap={3} wrap="nowrap">
                            <Text size="xs" c="dimmed">RMA</Text>
                            <Text size="xs" fw={700}>{(r.rma ?? 0).toFixed(2)}</Text>
                          </Group>
                        )}
                      </Group>
                    </Paper>
                  );
                })}
              </SimpleGrid>
            </>
          )}
        </Paper>
      )}
    </Stack>
  );
}
