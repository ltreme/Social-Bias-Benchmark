import { Group, Select } from '@mantine/core';

type AttributeOption = { value: string; label: string };

type AttributeBaselineSelectorProps = {
  attributes: AttributeOption[];
  attribute: string;
  onAttributeChange: (value: string) => void;
  categories: string[];
  baseline?: string;
  defaultBaseline?: string;
  onBaselineChange: (value: string | null) => void;
};

export function AttributeBaselineSelector({ attributes, attribute, onAttributeChange, categories, baseline, defaultBaseline, onBaselineChange }: AttributeBaselineSelectorProps) {
  return (
    <Group align="end">
      <Select
        label="Merkmal"
        data={attributes}
        value={attribute}
        onChange={(v) => onAttributeChange(v || attributes[0]?.value || 'gender')}
      />
      <Select
        label="Baseline"
        data={categories.map((c) => ({ value: c, label: c }))}
        value={baseline}
        onChange={onBaselineChange}
        clearable
        placeholder={defaultBaseline || 'auto'}
      />
    </Group>
  );
}

