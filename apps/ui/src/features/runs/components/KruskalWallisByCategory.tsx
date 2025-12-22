import { Card, Table, Badge, Text, Group, Stack, ThemeIcon, Tooltip, Paper, Skeleton, Title, Tabs } from '@mantine/core';
import { IconChartBar, IconInfoCircle } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { fetchKruskalWallisByCategory, type KruskalWallisByCategoryResponse } from '../api';
import { useThemedColor } from '../../../lib/useThemeColors';

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

const CATEGORY_LABELS: Record<string, string> = {
  kompetenz: 'Kompetenz',
  waerme: 'Wärme',
  moral: 'Moral',
  gesellschaftlich: 'Gesellschaftlich',
  Unbekannt: 'Unbekannt',
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

type KruskalWallisByCategoryProps = {
  runId: number;
};

type CategoryResults = {
  attributes: Array<{
    attribute: string;
    h_stat: number;
    p_value: number;
    eta_squared: number;
    n_groups: number;
    n_total: number;
    significant: boolean;
    effect_interpretation: string;
  }>;
  summary: {
    significant_count: number;
    total: number;
  };
};

function KruskalTable({ data }: { data: CategoryResults }) {
  const { attributes } = data;

  if (attributes.length === 0) {
    return (
      <Text c="dimmed" ta="center" py="md">
        Keine Daten verfügbar
      </Text>
    );
  }

  return (
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
  );
}

export function KruskalWallisByCategory({ runId }: KruskalWallisByCategoryProps) {
  const getColor = useThemedColor();

  const { data, isLoading, error } = useQuery<KruskalWallisByCategoryResponse>({
    queryKey: ['run', runId, 'kruskal-by-category'],
    queryFn: () => fetchKruskalWallisByCategory(runId),
    staleTime: 1000 * 60 * 5, // 5 min
  });

  if (isLoading) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Stack gap="md">
          <Skeleton height={28} width={300} />
          <Skeleton height={40} />
          <Skeleton height={300} />
        </Stack>
      </Card>
    );
  }

  if (error || !data || !data.categories) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Text c="dimmed">Fehler beim Laden der Kruskal-Wallis-Daten pro Trait-Kategorie</Text>
      </Card>
    );
  }

  const { categories } = data;
  const categoryKeys = Object.keys(categories).sort();

  if (categoryKeys.length === 0) {
    return (
      <Card shadow="sm" radius="md" withBorder>
        <Text c="dimmed" ta="center">Keine Trait-Kategorien verfügbar</Text>
      </Card>
    );
  }

  // Calculate overall stats
  const totalSignificant = Object.values(categories).reduce(
    (sum, cat) => sum + cat.summary.significant_count, 
    0
  );
  const totalTests = Object.values(categories).reduce(
    (sum, cat) => sum + cat.summary.total, 
    0
  );

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
              <Title order={5}>Kruskal-Wallis pro Trait-Kategorie</Title>
              <Text size="sm" c="dimmed">
                Gruppenunterschiede je Trait-Kategorie (Kompetenz, Wärme, etc.)
              </Text>
            </div>
          </Group>
          <Tooltip 
            label="Zeigt Kruskal-Wallis Tests für jede Trait-Kategorie separat. So können Sie sehen, ob demografische Unterschiede nur bei bestimmten Trait-Typen auftreten."
            withArrow 
            multiline 
            w={300}
          >
            <ThemeIcon variant="subtle" color="gray" size="sm">
              <IconInfoCircle size={16} />
            </ThemeIcon>
          </Tooltip>
        </Group>

        {/* Overall Summary Badge */}
        <Group>
          <Badge 
            color={totalSignificant > 0 ? 'green' : 'gray'} 
            variant="light" 
            size="lg"
          >
            Gesamt: {totalSignificant} / {totalTests} Tests signifikant
          </Badge>
          <Text size="xs" c="dimmed">
            über alle Kategorien
          </Text>
        </Group>

        {/* Tabs per Trait Category */}
        <Tabs defaultValue={categoryKeys[0]}>
          <Tabs.List>
            {categoryKeys.map((catKey) => {
              const catData = categories[catKey];
              const label = CATEGORY_LABELS[catKey] || catKey;
              const hasSignificant = catData.summary.significant_count > 0;
              
              return (
                <Tabs.Tab 
                  key={catKey} 
                  value={catKey}
                  rightSection={
                    hasSignificant ? (
                      <Badge color="green" variant="filled" size="xs" circle>
                        {catData.summary.significant_count}
                      </Badge>
                    ) : undefined
                  }
                >
                  {label}
                </Tabs.Tab>
              );
            })}
          </Tabs.List>

          {categoryKeys.map((catKey) => {
            const catData = categories[catKey];
            return (
              <Tabs.Panel key={catKey} value={catKey} pt="md">
                <Stack gap="md">
                  {/* Category Summary */}
                  <Group>
                    <Badge 
                      color={catData.summary.significant_count > 0 ? 'green' : 'gray'} 
                      variant="light"
                    >
                      {catData.summary.significant_count} / {catData.summary.total} signifikant
                    </Badge>
                    <Text size="sm" c="dimmed">
                      (p &lt; 0.05)
                    </Text>
                  </Group>

                  {/* Table */}
                  <KruskalTable data={catData} />
                </Stack>
              </Tabs.Panel>
            );
          })}
        </Tabs>

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
