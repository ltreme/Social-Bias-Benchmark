import { Button, Group, Modal, Stack, TextInput, Textarea } from '@mantine/core';
import { useEffect, useState } from 'react';
import type { CaseItem } from './api';

export function CaseModal(props: {
  opened: boolean;
  onClose: () => void;
  mode: 'create' | 'edit';
  initial?: Pick<CaseItem, 'id' | 'adjective' | 'case_template'> | null;
  onSubmit: (values: { adjective: string; case_template?: string | null }) => Promise<any> | void;
}) {
  const [adjective, setAdjective] = useState('');
  const [caseTemplate, setCaseTemplate] = useState<string>('');

  useEffect(() => {
    if (props.opened) {
      setAdjective(props.initial?.adjective ?? '');
      setCaseTemplate(props.initial?.case_template ?? '');
    }
  }, [props.opened, props.initial]);

  const title = props.mode === 'create' ? 'Case hinzufügen' : 'Case bearbeiten';

  return (
    <Modal opened={props.opened} onClose={props.onClose} title={title} centered>
      <Stack>
        {props.mode === 'edit' && (
          <TextInput label="ID" value={props.initial?.id ?? ''} readOnly />
        )}
        <TextInput label="Adjektiv" value={adjective} onChange={(e) => setAdjective(e.currentTarget.value)} required />
        <Textarea label="Case Template" minRows={3} value={caseTemplate} onChange={(e) => setCaseTemplate(e.currentTarget.value)} />
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onClose}>Abbrechen</Button>
          <Button onClick={async () => {
            await props.onSubmit({ adjective, case_template: caseTemplate || null });
            props.onClose();
          }}>Speichern</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

