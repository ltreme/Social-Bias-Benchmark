import { Card, Table, Badge, Text, Group, Stack, ThemeIcon, Tooltip, Paper, Skeleton, Title, Button } from '@mantine/core';
import { IconChartBar, IconInfoCircle, IconDownload, IconCopy } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { fetchKruskalWallis, fetchKruskalWallisLatex, type KruskalWallisResponse } from '../api';
import { useThemedColor } from '../../../lib/useThemeColors';
import { notifications } from '@mantine/notifications';

const ATTR_LABELS: Record<string, string> = {
  gender: 'Geschlecht',
  age_group: 'Altersgruppe',
  religion: 'Religion',
  sexuality: 'Sexualität',
  marriage_status: 'Familienstand',
  education: 'Bildung',
  origin_subregion: 'Herkunft',
  migration_status: 'Migration',
};

/**
 * Format p-value with scientific notation for very small values.
 */
function formatPValue(p: number | null | undefined): string {
  if (p == null) return '—';
  if (p < 0.001) return p.toExponential(2);
  return p.toFixed(4);
}

/**
 * Get significance stars based on p-value.
 */
function getSignificanceStars(p: number | null | undefined): string {
  if (p == null) return '';
  if (p < 0.001) return '***';
  if (p < 0.01) return '**';
  if (p < 0.05) return '*';
  return '';
}

/**
 * Get effect size color based on eta_squared.
 */
function getEffectColor(eta_squared: number | null | undefined): string {
  if (eta_squared == null) return 'gray';
  if (eta_squared >= 0.14) return 'red';
  if (eta_squared >= 0.06) return 'orange';
  if (eta_squared >= 0.01) return 'yellow';
  return 'gray';
}

type KruskalWallisCardProps = {
  runId: number;
};

export function KruskalWallisCard({ runId }: KruskalWallisCardProps) {
  const getColor = useThemedColor();

  const { data, isLoading, error } = useQuery<KruskalWallisResponse>({
    queryKey: ['run', runId, 'kruskal'],
    queryFn: () => fetchKruskalWallis(runId),
    staleTime: 1000 * 60 * 5, // 5 min
  });

  if (isLoading) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Stack gap="md">
          <Skeleton height={28} width={250} />
          <Skeleton height={200} />
        </Stack>
      </Card>
    );
  }

  if (error || !data) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Text c="dimmed">Fehler beim Laden der Kruskal-Wallis-Daten</Text>
      </Card>
    );
  }

  const { attributes, summary } = data;

  const handleDownloadCSV = () => {
    const url = `${import.meta.env.VITE_API_BASE_URL || ''}/runs/${runId}/kruskal/csv`;
    window.open(url, '_blank');
  };

  const handleCopyLatex = async () => {
    try {
      const latex = await fetchKruskalWallisLatex(runId);
      await navigator.clipboard.writeText(latex);
      notifications.show({
        title: 'LaTeX kopiert',
        message: 'Die LaTeX-Tabelle wurde in die Zwischenablage kopiert.',
        color: 'green',
      });
    } catch (error) {
      notifications.show({
        title: 'Fehler',
        message: 'LaTeX konnte nicht in die Zwischenablage kopiert werden.',
        color: 'red',
      });
    }
  };

  return (
    <Card shadow="sm" radius="md" withBorder>
      <Stack gap="md">
        {/* Header */}
        <Group justify="space-between" align="flex-start">
          <Group gap="xs">
            <ThemeIcon size="lg" radius="md" variant="light" color="grape">
              <IconChartBar size={20} />
            </ThemeIcon>
            <div>
              <Title order={5}>Kruskal-Wallis Omnibus-Test</Title>
              <Text size="sm" c="dimmed">
                Gruppenunterschiede pro demografischem Merkmal
              </Text>
            </div>
          </Group>
          <Group gap="xs">
            <Tooltip label="Als CSV herunterladen" withArrow>
              <Button
                variant="light"
                size="xs"
                leftSection={<IconDownload size={16} />}
                onClick={handleDownloadCSV}
              >
                CSV
              </Button>
            </Tooltip>
            <Tooltip label="LaTeX-Tabelle in Zwischenablage kopieren" withArrow>
              <Button
                variant="light"
                size="xs"
                leftSection={<IconCopy size={16} />}
                onClick={handleCopyLatex}
              >
                LaTeX
              </Button>
            </Tooltip>
            <Tooltip 
              label="Der Kruskal-Wallis H-Test prüft, ob sich die Antwortverteilungen zwischen den Gruppen eines Attributs signifikant unterscheiden. η² gibt die Effektstärke an."
              withArrow 
              multiline 
              w={300}
            >
              <ThemeIcon variant="subtle" color="gray" size="sm">
                <IconInfoCircle size={16} />
              </ThemeIcon>
            </Tooltip>
          </Group>
        </Group>

        {/* Summary Badge */}
        <Group>
          <Badge 
            color={summary.significant_count > 0 ? 'green' : 'gray'} 
            variant="light" 
            size="lg"
          >
            {summary.significant_count} / {summary.total} Attribute signifikant
          </Badge>
          <Text size="xs" c="dimmed">
            (p &lt; 0.05)
          </Text>
        </Group>

        {/* Results Table */}
        {attributes.length === 0 ? (
          <Text c="dimmed" ta="center" py="md">
            Keine Daten verfügbar
          </Text>
        ) : (
          <Table striped withTableBorder withColumnBorders highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Attribut</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>H-Statistik</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>p-Wert</Table.Th>
                <Table.Th style={{ textAlign: 'center' }}>Sig.</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>
                  <Tooltip label="Eta-Quadrat Effektstärke (klein ≥ 0.01, mittel ≥ 0.06, groß ≥ 0.14)" withArrow>
                    <span>η²</span>
                  </Tooltip>
                </Table.Th>
                <Table.Th>Effekt</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>n Gruppen</Table.Th>
                <Table.Th style={{ textAlign: 'right' }}>n Total</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {attributes.map((row) => (
                <Table.Tr key={row.attribute}>
                  <Table.Td>
                    <Text fw={row.significant ? 600 : 400}>
                      {ATTR_LABELS[row.attribute] || row.attribute}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {row.h_stat?.toFixed(2) ?? '—'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <Text 
                      size="sm" 
                      fw={row.significant ? 600 : 400}
                      c={row.significant ? 'green' : undefined}
                    >
                      {formatPValue(row.p_value)}
                    </Text>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'center' }}>
                    {row.significant ? (
                      <Badge color="green" variant="light" size="sm">
                        {getSignificanceStars(row.p_value)}
                      </Badge>
                    ) : (
                      <Text size="xs" c="dimmed">n.s.</Text>
                    )}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    <Text 
                      size="sm"
                      fw={(row.eta_squared ?? 0) >= 0.06 ? 600 : 400}
                      c={getEffectColor(row.eta_squared)}
                    >
                      {row.eta_squared?.toFixed(4) ?? '—'}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge 
                      color={getEffectColor(row.eta_squared)} 
                      variant="outline" 
                      size="sm"
                    >
                      {row.effect_interpretation}
                    </Badge>
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {row.n_groups ?? '—'}
                  </Table.Td>
                  <Table.Td style={{ textAlign: 'right' }}>
                    {row.n_total?.toLocaleString('de-DE') ?? '—'}
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}

        {/* Legend */}
        <Paper p="xs" bg={getColor('gray').bg} radius="sm">
          <Group gap="xl">
            <Group gap="xs">
              <Text size="xs" c="dimmed">Signifikanz:</Text>
              <Text size="xs">*** p &lt; 0.001</Text>
              <Text size="xs">** p &lt; 0.01</Text>
              <Text size="xs">* p &lt; 0.05</Text>
              <Text size="xs" c="dimmed">n.s. nicht signifikant</Text>
            </Group>
            <Group gap="xs">
              <Text size="xs" c="dimmed">Effekt η²:</Text>
              <Badge color="yellow" variant="outline" size="xs">klein ≥ 0.01</Badge>
              <Badge color="orange" variant="outline" size="xs">mittel ≥ 0.06</Badge>
              <Badge color="red" variant="outline" size="xs">groß ≥ 0.14</Badge>
            </Group>
          </Group>
        </Paper>
      </Stack>
    </Card>
  );
}
