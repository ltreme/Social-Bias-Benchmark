import { useMemo, useState } from 'react';
import { useParams } from '@tanstack/react-router';
import { Card, Group, NumberInput, Select, TextInput, Title, Button } from '@mantine/core';
import { DataTable } from '../../components/DataTable';
import type { ColumnDef } from '@tanstack/react-table';
import { useDatasetPersonas } from './hooks';

export function PersonaBrowserPage() {
  const { datasetId } = useParams({ from: '/datasets/$datasetId/personas' });
  const idNum = Number(datasetId);

  // Query state
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [sort, setSort] = useState('created_at');
  const [order, setOrder] = useState<'asc'|'desc'>('desc');
  const [gender, setGender] = useState<string | undefined>();
  const [education, setEducation] = useState<string | undefined>();
  const [religion, setReligion] = useState<string | undefined>();
  const [originSubregion, setOriginSubregion] = useState<string | undefined>();
  const [minAge, setMinAge] = useState<number | undefined>();
  const [maxAge, setMaxAge] = useState<number | undefined>();

  const params = useMemo(() => ({
    limit: pageSize,
    offset: (page - 1) * pageSize,
    sort,
    order,
    gender,
    education,
    religion,
    origin_subregion: originSubregion,
    min_age: minAge,
    max_age: maxAge,
  }), [page, pageSize, sort, order, gender, education, religion, originSubregion, minAge, maxAge]);

  const { data, isLoading } = useDatasetPersonas(idNum, params);
  const total = data?.total || 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  type Row = NonNullable<typeof data>['items'][number];
  const columns: ColumnDef<Row>[] = [
    { header: 'UUID', accessorKey: 'uuid' },
    { header: 'Erstellt', accessorKey: 'created_at' },
    { header: 'Alter', accessorKey: 'age' },
    { header: 'Geschlecht', accessorKey: 'gender' },
    { header: 'Religion', accessorKey: 'religion' },
    { header: 'Sexualität', accessorKey: 'sexuality' },
    { header: 'Bildung', accessorKey: 'education' },
    { header: 'Familienstand', accessorKey: 'marriage_status' },
    { header: 'Migration', accessorKey: 'migration_status' },
    { header: 'Herkunft Subregion', accessorKey: 'origin_subregion' },
    { header: 'Zusatz: Name', accessorKey: 'additional_attributes.name', cell: ({ row }) => (row.original.additional_attributes?.['name'] || '') },
    { header: 'Zusatz: Aussehen', accessorKey: 'additional_attributes.appearance', cell: ({ row }) => (row.original.additional_attributes?.['appearance'] || '') },
    { header: 'Zusatz: Biografie', accessorKey: 'additional_attributes.biography', cell: ({ row }) => (row.original.additional_attributes?.['biography'] || '') },
  ];

  return (
    <Card>
      <Title order={2} mb="sm">Personas – Dataset {datasetId}</Title>
      <Group grow mb="md">
        <Select label="Sortierung" data={[{value:'created_at',label:'Erstellt'}, {value:'age',label:'Alter'}, {value:'gender',label:'Geschlecht'}, {value:'education',label:'Bildung'}, {value:'religion',label:'Religion'}, {value:'origin_subregion',label:'Herkunft Subregion'}]} value={sort} onChange={(v)=>setSort((v as any) || 'created_at')} />
        <Select label="Reihenfolge" data={[{value:'desc',label:'absteigend'}, {value:'asc',label:'aufsteigend'}]} value={order} onChange={(v)=>setOrder((v as any) || 'desc')} />
        <TextInput label="Geschlecht" value={gender || ''} onChange={(e)=>setGender(e.currentTarget.value || undefined)} placeholder="z.B. male" />
        <TextInput label="Bildung" value={education || ''} onChange={(e)=>setEducation(e.currentTarget.value || undefined)} placeholder="z.B. Bachelor" />
        <TextInput label="Religion" value={religion || ''} onChange={(e)=>setReligion(e.currentTarget.value || undefined)} placeholder="z.B. Christian" />
        <TextInput label="Herkunft Subregion" value={originSubregion || ''} onChange={(e)=>setOriginSubregion(e.currentTarget.value || undefined)} placeholder="z.B. Western Europe" />
        <NumberInput label="min Alter" value={minAge} onChange={(v)=>setMinAge(Number.isFinite(Number(v)) ? Number(v) : undefined)} />
        <NumberInput label="max Alter" value={maxAge} onChange={(v)=>setMaxAge(Number.isFinite(Number(v)) ? Number(v) : undefined)} />
      </Group>

      {isLoading ? 'Laden…' : <DataTable data={data?.items || []} columns={columns} />}

      <Group justify="space-between" mt="md">
        <Group>
          <Button variant="default" disabled={page <= 1} onClick={()=>setPage((p)=>Math.max(1, p-1))}>Zurück</Button>
          <Button variant="default" disabled={page >= totalPages} onClick={()=>setPage((p)=>Math.min(totalPages, p+1))}>Weiter</Button>
        </Group>
        <Group>
          <NumberInput label="Seite" value={page} onChange={(v)=>setPage(Math.min(totalPages, Math.max(1, Number(v||1))))} min={1} max={totalPages} style={{ width: 140 }} />
          <NumberInput label="Pro Seite" value={pageSize} onChange={(v)=>{ setPageSize(Number(v||50)); setPage(1); }} min={10} max={500} style={{ width: 160 }} />
          <div style={{ alignSelf:'end' }}>Gesamt: {total} · Seiten: {totalPages}</div>
        </Group>
      </Group>
    </Card>
  );
}
