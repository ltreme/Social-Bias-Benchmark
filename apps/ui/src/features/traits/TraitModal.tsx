import { Autocomplete, Button, Group, Modal, Select, Stack, TextInput } from '@mantine/core';
import { useEffect, useState } from 'react';
import type { TraitItem, TraitPayload } from './api';

export function TraitModal(props: {
  opened: boolean;
  onClose: () => void;
  mode: 'create' | 'edit';
  initial?: Pick<TraitItem, 'id' | 'adjective' | 'case_template' | 'category' | 'valence'> | null;
  categoryOptions: string[];
  onSubmit: (values: TraitPayload) => Promise<any> | void;
}) {
  const [adjective, setAdjective] = useState('');
  const [category, setCategory] = useState<string>('');
  const [valence, setValence] = useState<string>('');

  useEffect(() => {
    if (props.opened) {
      setAdjective(props.initial?.adjective ?? '');
      setCategory(props.initial?.category ?? '');
      setValence(
        props.initial?.valence === undefined || props.initial?.valence === null
          ? ''
          : String(props.initial.valence),
      );
    }
  }, [props.opened, props.initial]);

  const title = props.mode === 'create' ? 'Trait hinzufügen' : 'Trait bearbeiten';

  return (
    <Modal opened={props.opened} onClose={props.onClose} title={title} centered>
      <Stack>
        {props.mode === 'edit' && (
          <TextInput label="ID" value={props.initial?.id ?? ''} readOnly />
        )}
        <TextInput label="Adjektiv" value={adjective} onChange={(e) => setAdjective(e.currentTarget.value)} required />
        <Autocomplete
          label="Kategorie"
          placeholder="z. B. Moral, Persönlichkeit…"
          data={props.categoryOptions}
          value={category}
          onChange={setCategory}
          searchable
          clearable
        />
        <Select
          label="Valenz"
          placeholder="Bitte wählen"
          data={[
            { value: '1', label: 'Positiv' },
            { value: '0', label: 'Neutral / situationsabhängig' },
            { value: '-1', label: 'Negativ' },
          ]}
          allowDeselect
          value={valence}
          onChange={(value) => setValence(value ?? '')}
        />
        <Group justify="flex-end">
          <Button variant="default" onClick={props.onClose}>Abbrechen</Button>
          <Button onClick={async () => {
            await props.onSubmit({
              adjective,
              case_template: props.initial?.case_template ?? null,
              category: category || null,
              valence: valence === '' ? null : (Number(valence) as -1 | 0 | 1),
            });
            props.onClose();
          }}>Speichern</Button>
        </Group>
      </Stack>
    </Modal>
  );
}
