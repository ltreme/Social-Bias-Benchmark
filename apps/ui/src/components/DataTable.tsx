import {
    useReactTable,
    type ColumnDef,
    getCoreRowModel,
    getSortedRowModel,
    type SortingState,
    flexRender,
    type RowData,
} from '@tanstack/react-table';
import { Table, UnstyledButton } from '@mantine/core';
import { IconChevronUp, IconChevronDown, IconSelector } from '@tabler/icons-react';
import { useState } from 'react';

type DataTableProps<T extends RowData> = {
    data: T[];
    columns: ColumnDef<T, any>[];
    getRowId?: (originalRow: T, index: number, parent?: any) => string;
    enableSorting?: boolean;
    initialSorting?: SortingState;
};

export function DataTable<T extends RowData>({ data, columns, getRowId, enableSorting = false, initialSorting = [] }: DataTableProps<T>) {
    const [sorting, setSorting] = useState<SortingState>(initialSorting);
    
    const table = useReactTable({
        data,
        columns,
        getCoreRowModel: getCoreRowModel(),
        getSortedRowModel: enableSorting ? getSortedRowModel() : undefined,
        state: enableSorting ? { sorting } : undefined,
        onSortingChange: enableSorting ? setSorting : undefined,
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
        <Table striped withTableBorder highlightOnHover>
        <Table.Thead>
            {table.getHeaderGroups().map((hg) => (
            <Table.Tr key={hg.id}>
                {hg.headers.map((header) => {
                    const canSort = enableSorting && header.column.getCanSort();
                    const sortDirection = header.column.getIsSorted();
                    
                    return (
                        <Table.Th key={header.id} style={canSort ? { cursor: 'pointer', userSelect: 'none' } : undefined}>
                            {header.isPlaceholder ? null : canSort ? (
                                <UnstyledButton 
                                    onClick={header.column.getToggleSortingHandler()}
                                    style={{ display: 'flex', alignItems: 'center', gap: 4, fontWeight: 600 }}
                                >
                                    {flexRender(header.column.columnDef.header, header.getContext())}
                                    {sortDirection === 'asc' ? (
                                        <IconChevronUp size={14} />
                                    ) : sortDirection === 'desc' ? (
                                        <IconChevronDown size={14} />
                                    ) : (
                                        <IconSelector size={14} style={{ opacity: 0.3 }} />
                                    )}
                                </UnstyledButton>
                            ) : (
                                flexRender(header.column.columnDef.header, header.getContext())
                            )}
                        </Table.Th>
                    );
                })}
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
