import { TextInput } from '@mantine/core';
import type { TextInputProps } from '@mantine/core';

type Props = {
  label: string;
  value: string;
  setValue: (v: string) => void;
  min?: number;
  placeholder?: string;
  onCommit: (n: number) => void;
} & Omit<TextInputProps, 'value' | 'onChange' | 'label' | 'placeholder'>;

export function NumericTextInput({ label, value, setValue, min = 0, placeholder, onCommit, ...rest }: Props) {
  return (
    <TextInput
      label={label}
      value={value}
      onChange={(e) => {
        const v = e.currentTarget.value;
        if (/^\d*$/.test(v)) setValue(v);
      }}
      onBlur={() => {
        const parsed = parseInt(value || '0', 10);
        const n = Math.max(min, Number.isFinite(parsed) ? parsed : 0);
        setValue(String(n));
        onCommit(n);
      }}
      placeholder={placeholder}
      {...rest}
    />
  );
}

