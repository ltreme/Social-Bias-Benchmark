import { SegmentedControl, useMantineColorScheme, Center } from '@mantine/core';
import { IconSun, IconMoon, IconDeviceDesktop } from '@tabler/icons-react';

export function ThemeToggle() {
    const { colorScheme, setColorScheme } = useMantineColorScheme();

    return (
        <SegmentedControl
            size="xs"
            value={colorScheme}
            onChange={(value) => setColorScheme(value as 'light' | 'dark' | 'auto')}
            data={[
                {
                    value: 'light',
                    label: (
                        <Center style={{ gap: 4 }}>
                            <IconSun size={14} />
                        </Center>
                    ),
                },
                {
                    value: 'dark',
                    label: (
                        <Center style={{ gap: 4 }}>
                            <IconMoon size={14} />
                        </Center>
                    ),
                },
                {
                    value: 'auto',
                    label: (
                        <Center style={{ gap: 4 }}>
                            <IconDeviceDesktop size={14} />
                        </Center>
                    ),
                },
            ]}
        />
    );
}
