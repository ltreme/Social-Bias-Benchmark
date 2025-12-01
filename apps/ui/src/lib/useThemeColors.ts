import { useComputedColorScheme } from '@mantine/core';

/**
 * Hook that returns color values adapted to the current color scheme.
 * In light mode, it uses light shades (.0, .1) for backgrounds.
 * In dark mode, it uses semi-transparent or muted shades for better contrast.
 */
export function useThemeColors() {
  const colorScheme = useComputedColorScheme('light');
  const isDark = colorScheme === 'dark';

  return {
    isDark,
    /**
     * Get a background color that adapts to light/dark mode.
     * @param color - Base color name (e.g., 'blue', 'green', 'red')
     * @param intensity - 'subtle' for very light bg, 'light' for slightly more visible
     */
    bgSubtle: (color: string) => isDark ? `var(--mantine-color-${color}-light)` : `${color}.0`,
    bgLight: (color: string) => isDark ? `var(--mantine-color-${color}-light)` : `${color}.1`,
    
    /**
     * Get a gray background that adapts to light/dark mode.
     */
    bgGraySubtle: isDark ? 'dark.5' : 'gray.0',
    bgGrayLight: isDark ? 'dark.4' : 'gray.1',
    
    /**
     * Get text colors that work well on the adaptive backgrounds.
     */
    textOnBg: (color: string) => isDark ? `${color}.4` : `${color}.7`,
    textOnGray: isDark ? 'gray.3' : 'gray.6',
  };
}

/**
 * Pre-defined color mappings for common UI elements.
 * These provide consistent colors across light and dark modes.
 * Dark mode uses lighter shades with alpha for subtle backgrounds.
 */
export const themeColorMap = {
  light: {
    green: { bg: 'green.0', text: 'green.7', icon: '#2f9e44', label: 'dimmed' },
    red: { bg: 'red.0', text: 'red.7', icon: '#e03131', label: 'dimmed' },
    blue: { bg: 'blue.0', text: 'blue.7', icon: '#1971c2', label: 'dimmed' },
    violet: { bg: 'violet.0', text: 'violet.7', icon: '#6741d9', label: 'dimmed' },
    teal: { bg: 'teal.0', text: 'teal.7', icon: '#0c8599', label: 'dimmed' },
    orange: { bg: 'orange.0', text: 'orange.7', icon: '#e8590c', label: 'dimmed' },
    gray: { bg: 'gray.1', text: 'gray.6', icon: '#868e96', label: 'dimmed' },
  },
  dark: {
    green: { bg: 'rgba(47, 158, 68, 0.15)', text: 'green.4', icon: '#69db7c', label: 'gray.5' },
    red: { bg: 'rgba(224, 49, 49, 0.15)', text: 'red.4', icon: '#ff8787', label: 'gray.5' },
    blue: { bg: 'rgba(25, 113, 194, 0.15)', text: 'blue.4', icon: '#74c0fc', label: 'gray.5' },
    violet: { bg: 'rgba(103, 65, 217, 0.15)', text: 'violet.4', icon: '#b197fc', label: 'gray.5' },
    teal: { bg: 'rgba(12, 133, 153, 0.15)', text: 'teal.4', icon: '#63e6be', label: 'gray.5' },
    orange: { bg: 'rgba(232, 89, 12, 0.15)', text: 'orange.4', icon: '#ffc078', label: 'gray.5' },
    gray: { bg: 'rgba(134, 142, 150, 0.12)', text: 'gray.4', icon: '#adb5bd', label: 'gray.5' },
  },
} as const;

export type ThemeColorKey = keyof typeof themeColorMap.light;

/**
 * Hook that returns a function to get themed colors for a given color key.
 */
export function useThemedColor() {
  const colorScheme = useComputedColorScheme('light');
  const colors = colorScheme === 'dark' ? themeColorMap.dark : themeColorMap.light;
  
  return (color: ThemeColorKey) => colors[color];
}
