/**
 * Shared utilities for Kruskal-Wallis test components
 */

export const ATTR_LABELS: Record<string, string> = {
  gender: 'Geschlecht',
  age_group: 'Altersgruppe',
  religion: 'Religion',
  sexuality: 'Sexualität',
  marriage_status: 'Familienstand',
  education: 'Bildung',
  occupation: 'Beruf',
  occupation_category: 'Berufskategorie',
  origin_subregion: 'Herkunft',
  migration_status: 'Migration',
};

/**
 * Trait category translations
 */
export const CATEGORY_LABELS: Record<string, string> = {
  alle: 'Alle',
  kompetenz: 'Kompetenz',
  waerme: 'Wärme',
  moral: 'Moral',
  gesellschaftlich: 'Gesellschaftlich',
  Unbekannt: 'Unbekannt',
};

/**
 * Demographic category value translations
 */
export const CATEGORY_VALUE_TRANSLATIONS: Record<string, string> = {
  // Gender
  'male': 'Männlich',
  'female': 'Weiblich',
  'diverse': 'Divers',
  // Age groups
  '0-9': 'Kindheit (0-9)',
  '10-19': 'Adoleszenz (10-19)',
  '20-29': 'Emerging Adulthood (20-29)',
  '30-44': 'Early Adulthood (30-44)',
  '45-64': 'Middle Adulthood (45-64)',
  '65+': 'Older Adulthood (65+)',
  'unknown': 'Unbekannt',
  // Religion
  'Christians': 'Christen',
  'Muslims': 'Muslime',
  'Buddhists': 'Buddhisten',
  'Hindus': 'Hindus',
  'Jews': 'Juden',
  'Religiously_unaffiliated': 'Konfessionslos',
  'Other_religions': 'Andere Religionen',
  // Migration
  'with_migration': 'Mit Migrationshintergrund',
  'without_migration': 'Ohne Migrationshintergrund',
  // Sexuality
  'heterosexual': 'Heterosexuell',
  'bisexual': 'Bisexuell',
  'homosexual': 'Homosexuell',
  'nan': 'Keine Angabe',
  // Marriage status
  'single': 'Ledig',
  'married': 'Verheiratet',
  'divorced': 'Geschieden',
  'widowed': 'Verwitwet',
  // Education
  'Hauptschulabschluss': 'Hauptschule',
  'mittleren Schulabschluss': 'Realschule',
  'Fachhochschulreife': 'Fachhochschulreife',
  'Hochschulreife': 'Abitur',
  'ohne Schulabschluss': 'Kein Abschluss',
  'Volksschulabschluss': 'Volksschule',
  // Regions
  'Northern Europe': 'Nordeuropa',
  'Western Europe': 'Westeuropa',
  'Eastern Europe': 'Osteuropa',
  'Southern Europe': 'Südeuropa',
  'Northern Africa': 'Nordafrika',
  'Sub-Saharan Africa': 'Subsahara-Afrika',
  'Western Asia': 'Westasien',
  'Southern Asia': 'Südasien',
  'South-Eastern Asia': 'Südostasien',
  'Eastern Asia': 'Ostasien',
  'Central Asia': 'Zentralasien',
  'Northern America': 'Nordamerika',
  'Latin America and the Caribbean': 'Lateinamerika',
  'Australia and New Zealand': 'Ozeanien',
};

/**
 * Translate a category value to German
 */
export function translateCategory(category: string): string {
  return CATEGORY_VALUE_TRANSLATIONS[category] || category;
}

/**
 * Format p-value with scientific notation for very small values.
 */
export function formatPValue(p: number | null | undefined): string {
  if (p == null) return '—';
  if (p < 0.001) return p.toExponential(2);
  return p.toFixed(4);
}

/**
 * Format p-value for LaTeX output with proper scientific notation.
 * Very small values are formatted as $mantissa \times 10^{exponent}$
 */
export function formatPValueForLatex(p: number | null | undefined): string {
  if (p == null) return '—';
  if (p < 0.001) {
    const exp = Math.floor(Math.log10(p));
    const mantissa = p / Math.pow(10, exp);
    return `$${mantissa.toFixed(2)} \\times 10^{${exp}}$`;
  }
  return p.toFixed(4);
}

/**
 * Get significance stars based on p-value.
 */
export function getSignificanceStars(p: number | null | undefined): string {
  if (p == null) return '';
  if (p < 0.001) return '***';
  if (p < 0.01) return '**';
  if (p < 0.05) return '*';
  return '';
}

/**
 * Get effect size color based on eta_squared.
 */
export function getEffectColor(eta_squared: number | null | undefined): string {
  if (eta_squared == null) return 'gray';
  if (eta_squared >= 0.14) return 'red';
  if (eta_squared >= 0.06) return 'orange';
  if (eta_squared >= 0.01) return 'yellow';
  return 'gray';
}

export type ColumnKey = 'attribute' | 'h_stat' | 'p_value' | 'sig' | 'eta_squared' | 'effect' | 'n_groups' | 'n_total';

export const COLUMN_LABELS: Record<ColumnKey, string> = {
  attribute: 'Attribut',
  h_stat: 'H-Statistik',
  p_value: 'p-Wert',
  sig: 'Signifikanz',
  eta_squared: 'η²',
  effect: 'Effekt',
  n_groups: 'n Gruppen',
  n_total: 'n Total',
};

export const LATEX_COLUMN_DEFS: Record<ColumnKey, string> = {
  attribute: 'l',
  h_stat: 'r',
  p_value: 'r',
  sig: 'c',
  eta_squared: 'r',
  effect: 'l',
  n_groups: 'r',
  n_total: 'r',
};

export const LATEX_COLUMN_HEADERS: Record<ColumnKey, string> = {
  attribute: 'Attribut',
  h_stat: 'H-Statistik',
  p_value: 'p-Wert',
  sig: 'Sig.',
  eta_squared: '$\\eta^2$',
  effect: 'Effekt',
  n_groups: 'n Gruppen',
  n_total: 'n Total',
};
