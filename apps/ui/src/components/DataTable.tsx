import { useReactTable, type ColumnDef, getCoreRowModel, flexRender } from '@tanstack/react-table';
import { Table } from '@mantine/core';

type DataTableProps<T extends object> = {
    data: T[];
    columns: ColumnDef<T, any>[];
};

export function DataTable<T extends object>({ data, columns }: DataTableProps<T>) {
    const table = useReactTable({ data, columns, getCoreRowModel: getCoreRowModel() });
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