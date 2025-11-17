import {
    useReactTable,
    type ColumnDef,
    getCoreRowModel,
    flexRender,
    type RowData,
} from '@tanstack/react-table';
import { Table } from '@mantine/core';

type DataTableProps<T extends RowData> = {
    data: T[];
    columns: ColumnDef<T, any>[];
    getRowId?: (originalRow: T, index: number, parent?: any) => string;
};

export function DataTable<T extends RowData>({ data, columns, getRowId }: DataTableProps<T>) {
    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getRowId: getRowId
            ? getRowId
            : (row: T, index: number) => {
                  if (typeof (row as any)?.id === 'string' || typeof (row as any)?.id === 'number') {
                      return String((row as any).id);
                  }
                  return String(index);
              },
    });
    return (
        <Table striped withTableBorder>
        <Table.Thead>
            {table.getHeaderGroups().map((hg) => (
            <Table.Tr key={hg.id}>
                {hg.headers.map((header) => (
                <Table.Th key={header.id}>
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                </Table.Th>
                ))}
            </Table.Tr>
            ))}
        </Table.Thead>
        <Table.Tbody>
            {table.getRowModel().rows.map((row) => (
            <Table.Tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                <Table.Td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</Table.Td>
                ))}
            </Table.Tr>
            ))}
        </Table.Tbody>
        </Table>
    );
}
