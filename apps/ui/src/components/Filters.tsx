import { Button, Group, Select, TextInput } from '@mantine/core';
import { useForm } from 'react-hook-form';

type FilterValues = { query?: string; model?: string; dataset?: string };

export function Filters(props: { models?: string[]; datasets?: string[]; onApply: (v: FilterValues) => void }) {
    const { register, handleSubmit } = useForm<FilterValues>({ defaultValues: {} });
    return (
        <form onSubmit={handleSubmit(props.onApply)}>
        <Group gap="sm" align="end">
            <TextInput label="Suche" placeholder="Name/ID…" {...register('query')} />
            <Select label="Modell" data={props.models ?? []} searchable clearable onChange={(v) => props.onApply({ model: v ?? undefined })} />
            <Select label="Dataset" data={props.datasets ?? []} searchable clearable onChange={(v) => props.onApply({ dataset: v ?? undefined })} />
            <Button type="submit">Anwenden</Button>
        </Group>
        </form>
    );
    }