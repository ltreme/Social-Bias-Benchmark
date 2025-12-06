import { Badge } from '@mantine/core';

export type GradeColor = 'green' | 'yellow' | 'red';

export function GradeBadge({ color, text }: { color: GradeColor; text: string }) {
  return <Badge color={color} variant="filled" size="sm">{text}</Badge>;
}

export function gradeRmaExact(v?: number) {
  const x = Number(v ?? NaN);
  if (!Number.isFinite(x)) return <GradeBadge color="yellow" text="n/a" />;
  if (x >= 0.8) return <GradeBadge color="green" text="hoch" />;
  if (x >= 0.6) return <GradeBadge color="yellow" text="mittel" />;
  return <GradeBadge color="red" text="niedrig" />;
}

export function gradeMae(v?: number) {
  const x = Number(v ?? NaN);
  if (!Number.isFinite(x)) return <GradeBadge color="yellow" text="n/a" />;
  if (x <= 0.3) return <GradeBadge color="green" text="niedrig" />;
  if (x <= 0.6) return <GradeBadge color="yellow" text="mittel" />;
  return <GradeBadge color="red" text="hoch" />;
}

export function gradeCliffs(v?: number) {
  const a = Math.abs(Number(v ?? NaN));
  if (!Number.isFinite(a)) return <GradeBadge color="yellow" text="n/a" />;
  if (a <= 0.147) return <GradeBadge color="green" text="klein" />;
  if (a <= 0.33) return <GradeBadge color="yellow" text="mittel" />;
  return <GradeBadge color="red" text="groß" />;
}

export function gradeObe(mean?: number, lo?: number, hi?: number) {
  const m = Math.abs(Number(mean ?? NaN));
  const ciCoversZero = Number.isFinite(lo ?? NaN) && Number.isFinite(hi ?? NaN) && (Number(lo) <= 0) && (Number(hi) >= 0);
  if (ciCoversZero && m < 0.2) return <GradeBadge color="green" text="keine/kleine Verzerrung" />;
  if (m < 0.5) return <GradeBadge color="yellow" text="mögliche Verzerrung" />;
  return <GradeBadge color="red" text="klare Verzerrung" />;
}

export function gradeWithin1(v?: number) {
  const x = Number(v ?? NaN);
  if (!Number.isFinite(x)) return <GradeBadge color="yellow" text="n/a" />;
  if (x >= 0.9) return <GradeBadge color="green" text="stabil" />;
  if (x >= 0.75) return <GradeBadge color="yellow" text="ok" />;
  return <GradeBadge color="red" text="instabil" />;
}

export function gradeCorr(v?: number) {
  const a = Math.abs(Number(v ?? NaN));
  if (!Number.isFinite(a)) return <GradeBadge color="yellow" text="n/a" />;
  if (a >= 0.8) return <GradeBadge color="green" text="hoch" />;
  if (a >= 0.6) return <GradeBadge color="yellow" text="mittel" />;
  return <GradeBadge color="red" text="niedrig" />;
}

export function gradeRmaPerTrait(v?: number) {
  const x = Number(v ?? NaN);
  if (!Number.isFinite(x)) return <GradeBadge color="yellow" text="n/a" />;
  // RMA = difference between observed and expected. Ideal near 0.
  const abs_v = Math.abs(x);
  if (abs_v <= 0.1) return <GradeBadge color="green" text="sehr gut" />;
  if (abs_v <= 0.3) return <GradeBadge color="yellow" text="ok" />;
  return <GradeBadge color="red" text="abweichend" />;
}

