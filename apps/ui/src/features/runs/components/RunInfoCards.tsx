import { Badge, Group, Paper, Popover, SimpleGrid, Text, ThemeIcon } from '@mantine/core';
import { IconChartBar, IconClipboardCheck, IconCpu, IconDatabase, IconMessage, IconMessageCog } from '@tabler/icons-react';
import { Link } from '@tanstack/react-router';
import type { RunDetail } from '../api';

interface RunInfoCardsProps {
  run: RunDetail;
  benchDone: number | null;
  benchTotal: number | null;
}

export function RunInfoCards({ run, benchDone, benchTotal }: RunInfoCardsProps) {
  return (
    <SimpleGrid cols={{ base: 1, xs: 2, md: 4 }} spacing="sm">
      {/* Dataset Card */}
      <Paper p="sm" withBorder radius="md">
        <Group gap="xs" wrap="nowrap">
          <ThemeIcon size="md" radius="md" variant="light" color="blue">
            <IconDatabase size={16} />
          </ThemeIcon>
          <div style={{ minWidth: 0 }}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700} lh={1}>Datensatz</Text>
            <Text size="sm" fw={500} truncate lh={1.2} mt={2}>
              <Link to={`/datasets/${run.dataset?.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                {run.dataset?.name}
              </Link>
            </Text>
          </div>
        </Group>
      </Paper>

      {/* Model Card */}
      <Paper p="sm" withBorder radius="md">
        <Group gap="xs" wrap="nowrap">
          <ThemeIcon size="md" radius="md" variant="light" color="violet">
            <IconCpu size={16} />
          </ThemeIcon>
          <div style={{ minWidth: 0 }}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700} lh={1}>Modell</Text>
            <Text size="sm" fw={500} truncate lh={1.2} mt={2}>{run.model_name}</Text>
          </div>
        </Group>
      </Paper>

      {/* Results Card */}
      <Paper p="sm" withBorder radius="md">
        <Group gap="xs" wrap="nowrap">
          <ThemeIcon size="md" radius="md" variant="light" color="teal">
            <IconChartBar size={16} />
          </ThemeIcon>
          <div>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700} lh={1}>Ergebnisse</Text>
            <Text size="sm" fw={500} lh={1.2} mt={2}>
              {run.n_results?.toLocaleString('de-DE') ?? '–'}
              {benchDone !== null && benchTotal !== null && benchDone < benchTotal && (
                <Text span size="xs" c="dimmed"> / {benchTotal.toLocaleString('de-DE')}</Text>
              )}
            </Text>
          </div>
        </Group>
      </Paper>

      {/* Options Card */}
      <Paper p="sm" withBorder radius="md">
        <Group gap="xs" wrap="nowrap">
          <ThemeIcon size="md" radius="md" variant="light" color="orange">
            <IconClipboardCheck size={16} />
          </ThemeIcon>
          <div style={{ minWidth: 0 }}>
            <Text size="xs" c="dimmed" tt="uppercase" fw={700} lh={1}>Optionen</Text>
            <Group gap={4} mt={2} wrap="nowrap">
              {run.include_rationale ? (
                <Badge size="xs" variant="light" color="blue" leftSection={<IconMessage size={10} />}>
                  Rationale
                </Badge>
              ) : null}
              {run.system_prompt ? (
                <Popover width={400} position="bottom" withArrow shadow="md">
                  <Popover.Target>
                    <Badge 
                      size="xs" 
                      variant="light" 
                      color="orange" 
                      leftSection={<IconMessageCog size={10} />}
                      style={{ cursor: 'pointer' }}
                    >
                      Prompt
                    </Badge>
                  </Popover.Target>
                  <Popover.Dropdown>
                    <Text size="xs" fw={600} mb={4}>System Prompt:</Text>
                    <Text size="xs" style={{ whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
                      {run.system_prompt}
                    </Text>
                  </Popover.Dropdown>
                </Popover>
              ) : null}
              {!run.include_rationale && !run.system_prompt && (
                <Text size="xs" c="dimmed">Standard</Text>
              )}
            </Group>
          </div>
        </Group>
      </Paper>
    </SimpleGrid>
  );
}
