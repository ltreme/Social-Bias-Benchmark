import { useCallback, useState } from 'react';
import { jsPDF } from 'jspdf';
import type { RunDetail, RunMetrics, OrderMetrics, RunDeltas } from './api';

const ATTR_LABELS: Record<string, string> = {
  gender: 'Geschlecht',
  age_group: 'Altersgruppe',
  religion: 'Religion',
  sexuality: 'Sexualität',
  marriage_status: 'Familienstand',
  education: 'Bildung',
  origin_subregion: 'Herkunft',
  migration_status: 'Migration',
};

export interface PdfExportData {
  run: RunDetail;
  metrics?: RunMetrics | null;
  orderMetrics?: OrderMetrics | null;
  allDeltas?: Record<string, RunDeltas> | null;
}

export interface PdfExportOptions {
  filename?: string;
}

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '–';
  return v.toFixed(decimals);
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '–';
  return `${(v * 100).toFixed(1)}%`;
}

function fmtInt(v: number | null | undefined): string {
  if (v === null || v === undefined) return '–';
  return v.toLocaleString('de-DE');
}

export function usePdfExport() {
  const [isExporting, setIsExporting] = useState(false);
  const [progress, setProgress] = useState(0);

  const exportToPdf = useCallback(async (data: PdfExportData, options: PdfExportOptions = {}) => {
    const { run, metrics, orderMetrics, allDeltas } = data;
    const { filename = `run_${run.id}_analyse.pdf` } = options;

    setIsExporting(true);
    setProgress(10);

    try {
      const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const margin = 15;
      const contentWidth = pageWidth - margin * 2;
      let y = margin;

      const checkPageBreak = (needed: number) => {
        if (y + needed > pageHeight - margin) {
          pdf.addPage();
          y = margin;
          return true;
        }
        return false;
      };

      const addSectionTitle = (title: string) => {
        checkPageBreak(15);
        pdf.setFontSize(14);
        pdf.setFont('helvetica', 'bold');
        pdf.setTextColor(30, 30, 30);
        pdf.text(title, margin, y);
        y += 8;
        pdf.setDrawColor(200, 200, 200);
        pdf.setLineWidth(0.3);
        pdf.line(margin, y - 2, margin + contentWidth, y - 2);
        y += 4;
      };

      const addKeyValue = (key: string, value: string, indent = 0) => {
        checkPageBreak(6);
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'normal');
        pdf.setTextColor(80, 80, 80);
        pdf.text(key + ':', margin + indent, y);
        pdf.setTextColor(30, 30, 30);
        pdf.text(value, margin + 50 + indent, y);
        y += 5;
      };

      // Add multi-line text block
      const addTextBlock = (text: string, maxWidth: number) => {
        pdf.setFontSize(9);
        pdf.setFont('helvetica', 'normal');
        pdf.setTextColor(60, 60, 60);
        const lines = pdf.splitTextToSize(text, maxWidth);
        const lineHeight = 4;
        checkPageBreak(lines.length * lineHeight + 4);
        lines.forEach((line: string) => {
          pdf.text(line, margin + 5, y);
          y += lineHeight;
        });
        y += 2;
      };

      // Draw a simple bar chart
      const drawBarChart = (data: { label: string; value: number; count: number }[], title: string) => {
        const chartHeight = 50;
        const barWidth = contentWidth / data.length - 4;
        checkPageBreak(chartHeight + 25);
        
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'bold');
        pdf.setTextColor(30, 30, 30);
        pdf.text(title, margin, y);
        y += 8;

        const maxValue = Math.max(...data.map(d => d.value), 0.01);
        const chartY = y;
        
        // Draw bars
        data.forEach((d, i) => {
          const barHeight = (d.value / maxValue) * chartHeight;
          const x = margin + i * (barWidth + 4) + 2;
          
          // Bar
          pdf.setFillColor(66, 133, 244);
          pdf.rect(x, chartY + chartHeight - barHeight, barWidth, barHeight, 'F');
          
          // Label below
          pdf.setFontSize(8);
          pdf.setFont('helvetica', 'normal');
          pdf.setTextColor(60, 60, 60);
          pdf.text(d.label, x + barWidth / 2, chartY + chartHeight + 5, { align: 'center' });
          
          // Value on top
          pdf.setFontSize(7);
          pdf.setTextColor(30, 30, 30);
          const pctText = `${(d.value * 100).toFixed(0)}%`;
          pdf.text(pctText, x + barWidth / 2, chartY + chartHeight - barHeight - 2, { align: 'center' });
        });
        
        y = chartY + chartHeight + 12;
      };

      // Draw radar chart for bias scores
      const drawRadarChart = (
        data: { label: string; score: number; cliffsD: number; sigCount: number; total: number }[],
        title: string
      ) => {
        const chartSize = 70; // Radius
        const centerX = margin + contentWidth / 2;
        
        checkPageBreak(chartSize * 2 + 40);
        
        pdf.setFontSize(12);
        pdf.setFont('helvetica', 'bold');
        pdf.setTextColor(30, 30, 30);
        pdf.text(title, margin, y);
        y += 10;

        const centerY = y + chartSize;
        const numAxes = data.length;
        const angleStep = (2 * Math.PI) / numAxes;

        // Draw concentric circles (grid)
        pdf.setDrawColor(220, 220, 220);
        pdf.setLineWidth(0.2);
        [25, 50, 75, 100].forEach(level => {
          const r = (level / 100) * chartSize;
          // Draw circle manually with line segments
          const segments = 60;
          for (let i = 0; i < segments; i++) {
            const a1 = (i / segments) * 2 * Math.PI;
            const a2 = ((i + 1) / segments) * 2 * Math.PI;
            const x1 = centerX + Math.cos(a1) * r;
            const y1 = centerY + Math.sin(a1) * r;
            const x2 = centerX + Math.cos(a2) * r;
            const y2 = centerY + Math.sin(a2) * r;
            pdf.line(x1, y1, x2, y2);
          }
        });

        // Draw axes and labels
        pdf.setDrawColor(180, 180, 180);
        pdf.setLineWidth(0.3);
        data.forEach((d, i) => {
          const angle = -Math.PI / 2 + i * angleStep; // Start from top
          const x = centerX + Math.cos(angle) * chartSize;
          const y_pos = centerY + Math.sin(angle) * chartSize;
          
          // Axis line
          pdf.line(centerX, centerY, x, y_pos);
          
          // Label
          const labelR = chartSize + 8;
          const labelX = centerX + Math.cos(angle) * labelR;
          const labelY = centerY + Math.sin(angle) * labelR;
          
          pdf.setFontSize(8);
          pdf.setFont('helvetica', 'normal');
          pdf.setTextColor(60, 60, 60);
          
          // Adjust text alignment based on position
          const align = Math.abs(Math.cos(angle)) < 0.3 ? 'center' 
            : Math.cos(angle) > 0 ? 'left' : 'right';
          pdf.text(d.label, labelX, labelY + 2, { align: align as any });
        });

        // Draw data polygon
        pdf.setDrawColor(100, 100, 100);
        pdf.setLineWidth(1);
        
        // Calculate points
        const points: { x: number; y: number; score: number }[] = data.map((d, i) => {
          const angle = -Math.PI / 2 + i * angleStep;
          const r = (d.score / 100) * chartSize;
          return {
            x: centerX + Math.cos(angle) * r,
            y: centerY + Math.sin(angle) * r,
            score: d.score,
          };
        });

        // Draw filled polygon
        pdf.setFillColor(173, 181, 189, 0.3);
        // Close the polygon
        if (points.length > 0) {
          for (let i = 0; i < points.length; i++) {
            const p1 = points[i];
            const p2 = points[(i + 1) % points.length];
            pdf.setDrawColor(150, 150, 150);
            pdf.line(p1.x, p1.y, p2.x, p2.y);
          }
        }

        // Draw colored dots at each point
        points.forEach((p) => {
          // Color based on score
          if (p.score <= 10) {
            pdf.setFillColor(64, 192, 87); // Green
          } else if (p.score <= 25) {
            pdf.setFillColor(34, 139, 230); // Blue
          } else if (p.score <= 45) {
            pdf.setFillColor(250, 176, 5); // Yellow
          } else {
            pdf.setFillColor(224, 49, 49); // Red
          }
          pdf.circle(p.x, p.y, 3, 'F');
        });

        // Legend at bottom
        y = centerY + chartSize + 20;
        pdf.setFontSize(7);
        pdf.setTextColor(100, 100, 100);
        const legendY = y;
        let legendX = margin;
        
        pdf.setFillColor(64, 192, 87); pdf.circle(legendX + 2, legendY, 2, 'F');
        pdf.text('0-10 minimal', legendX + 6, legendY + 1);
        legendX += 32;
        
        pdf.setFillColor(34, 139, 230); pdf.circle(legendX + 2, legendY, 2, 'F');
        pdf.text('10-25 gering', legendX + 6, legendY + 1);
        legendX += 32;
        
        pdf.setFillColor(250, 176, 5); pdf.circle(legendX + 2, legendY, 2, 'F');
        pdf.text('25-45 moderat', legendX + 6, legendY + 1);
        legendX += 35;
        
        pdf.setFillColor(224, 49, 49); pdf.circle(legendX + 2, legendY, 2, 'F');
        pdf.text('45+ hoch', legendX + 6, legendY + 1);
        
        y += 8;

        // Data table below radar
        y += 5;
        pdf.setFontSize(9);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Detailwerte', margin, y);
        y += 5;
        
        const radarTableRows = data.map(d => [
          d.label,
          d.score.toFixed(0),
          d.cliffsD.toFixed(3),
          `${d.sigCount}/${d.total}`,
        ]);
        addTable(
          ['Attribut', 'Score', 'Max |d|', 'Sig.'],
          radarTableRows,
          [50, 30, 35, 35]
        );
      };

      // Draw horizontal lollipop chart for deltas
      const drawLollipopChart = (
        data: { label: string; delta: number; significant: boolean }[],
        title: string,
        baseline: string
      ) => {
        const rowHeight = 8;
        const chartHeight = Math.min(data.length * rowHeight + 20, 120);
        const labelWidth = 50;
        const chartWidth = contentWidth - labelWidth - 10;
        
        checkPageBreak(chartHeight + 15);
        
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'bold');
        pdf.setTextColor(30, 30, 30);
        pdf.text(title, margin, y);
        pdf.setFontSize(8);
        pdf.setFont('helvetica', 'normal');
        pdf.setTextColor(100, 100, 100);
        pdf.text(`(Baseline: ${baseline})`, margin + pdf.getTextWidth(title) + 3, y);
        y += 10;

        const maxAbsDelta = Math.max(...data.map(d => Math.abs(d.delta)), 0.5);
        const centerX = margin + labelWidth + chartWidth / 2;
        const chartY = y;

        // Draw center line (zero)
        pdf.setDrawColor(180, 180, 180);
        pdf.setLineWidth(0.3);
        pdf.line(centerX, chartY, centerX, chartY + data.length * rowHeight);

        // Draw scale labels
        pdf.setFontSize(7);
        pdf.setTextColor(150, 150, 150);
        pdf.text(`-${maxAbsDelta.toFixed(1)}`, margin + labelWidth, chartY - 2);
        pdf.text('0', centerX, chartY - 2, { align: 'center' });
        pdf.text(`+${maxAbsDelta.toFixed(1)}`, margin + labelWidth + chartWidth, chartY - 2, { align: 'right' });

        // Draw rows
        data.forEach((d, i) => {
          const rowY = chartY + i * rowHeight + rowHeight / 2;
          
          // Label
          pdf.setFontSize(8);
          pdf.setFont('helvetica', 'normal');
          pdf.setTextColor(60, 60, 60);
          const labelText = d.label.length > 12 ? d.label.substring(0, 10) + '..' : d.label;
          pdf.text(labelText, margin, rowY + 1);
          
          // Lollipop line
          const deltaX = (d.delta / maxAbsDelta) * (chartWidth / 2);
          const endX = centerX + deltaX;
          
          // Color based on significance and direction
          if (d.significant) {
            if (d.delta > 0) {
              pdf.setDrawColor(46, 125, 50);
              pdf.setFillColor(46, 125, 50);
            } else {
              pdf.setDrawColor(198, 40, 40);
              pdf.setFillColor(198, 40, 40);
            }
          } else {
            pdf.setDrawColor(158, 158, 158);
            pdf.setFillColor(158, 158, 158);
          }
          
          pdf.setLineWidth(1.5);
          pdf.line(centerX, rowY, endX, rowY);
          
          // Circle at end
          pdf.circle(endX, rowY, 2, 'F');
        });

        y = chartY + data.length * rowHeight + 8;
      };

      // Draw radar-style summary for all attributes
      const drawBiasSummary = (
        deltasMap: Record<string, RunDeltas>,
        title: string
      ) => {
        const attrs = Object.keys(deltasMap).filter(k => deltasMap[k]?.rows?.length > 0);
        if (attrs.length === 0) return;

        checkPageBreak(80);
        
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'bold');
        pdf.setTextColor(30, 30, 30);
        pdf.text(title, margin, y);
        y += 8;

        // Calculate max absolute delta per attribute
        const summaryData = attrs.map(attr => {
          const rows = deltasMap[attr]?.rows || [];
          const significantRows = rows.filter(r => r.significant);
          const maxDelta = Math.max(...rows.map(r => Math.abs(r.delta || 0)), 0);
          const avgDelta = rows.length > 0 
            ? rows.reduce((sum, r) => sum + Math.abs(r.delta || 0), 0) / rows.length 
            : 0;
          return {
            attr,
            label: ATTR_LABELS[attr] || attr,
            maxDelta,
            avgDelta,
            sigCount: significantRows.length,
            totalCount: rows.length,
          };
        });

        // Draw horizontal bars showing average bias per attribute
        const barHeight = 10;
        const labelWidth = 55;
        const barMaxWidth = contentWidth - labelWidth - 30;
        const maxAvgDelta = Math.max(...summaryData.map(d => d.avgDelta), 0.3);

        summaryData.forEach((d, i) => {
          checkPageBreak(barHeight + 2);
          const rowY = y + i * (barHeight + 4);
          
          // Label
          pdf.setFontSize(9);
          pdf.setFont('helvetica', 'normal');
          pdf.setTextColor(60, 60, 60);
          pdf.text(d.label, margin, rowY + barHeight / 2 + 1);
          
          // Bar
          const barWidth = (d.avgDelta / maxAvgDelta) * barMaxWidth;
          
          // Color based on bias level
          if (d.avgDelta < 0.05) {
            pdf.setFillColor(64, 192, 87); // Green - minimal
          } else if (d.avgDelta < 0.15) {
            pdf.setFillColor(34, 139, 230); // Blue - low
          } else if (d.avgDelta < 0.3) {
            pdf.setFillColor(250, 176, 5); // Yellow - moderate
          } else {
            pdf.setFillColor(224, 49, 49); // Red - high
          }
          
          pdf.rect(margin + labelWidth, rowY, barWidth, barHeight, 'F');
          
          // Value and sig count
          pdf.setFontSize(8);
          pdf.setTextColor(30, 30, 30);
          pdf.text(
            `${d.avgDelta.toFixed(3)} (${d.sigCount}/${d.totalCount} sig.)`,
            margin + labelWidth + barWidth + 3,
            rowY + barHeight / 2 + 1
          );
        });

        y += summaryData.length * (barHeight + 4) + 8;

        // Legend
        pdf.setFontSize(7);
        pdf.setTextColor(100, 100, 100);
        const legendY = y;
        pdf.setFillColor(64, 192, 87); pdf.rect(margin, legendY, 8, 4, 'F');
        pdf.text('< 0.05 minimal', margin + 10, legendY + 3);
        pdf.setFillColor(34, 139, 230); pdf.rect(margin + 40, legendY, 8, 4, 'F');
        pdf.text('< 0.15 gering', margin + 50, legendY + 3);
        pdf.setFillColor(250, 176, 5); pdf.rect(margin + 80, legendY, 8, 4, 'F');
        pdf.text('< 0.30 moderat', margin + 90, legendY + 3);
        pdf.setFillColor(224, 49, 49); pdf.rect(margin + 125, legendY, 8, 4, 'F');
        pdf.text('>= 0.30 hoch', margin + 135, legendY + 3);
        y += 10;
      };

      const addTable = (headers: string[], rows: string[][], colWidths?: number[]) => {
        const cellPadding = 2;
        const rowHeight = 6;
        const widths = colWidths || headers.map(() => contentWidth / headers.length);

        checkPageBreak(rowHeight * 2);
        pdf.setFillColor(240, 240, 240);
        pdf.rect(margin, y, contentWidth, rowHeight, 'F');
        pdf.setFontSize(9);
        pdf.setFont('helvetica', 'bold');
        pdf.setTextColor(30, 30, 30);
        let x = margin + cellPadding;
        headers.forEach((h, i) => {
          pdf.text(h, x, y + rowHeight - 2);
          x += widths[i];
        });
        y += rowHeight;

        pdf.setFont('helvetica', 'normal');
        rows.forEach((row, rowIdx) => {
          checkPageBreak(rowHeight);
          if (rowIdx % 2 === 1) {
            pdf.setFillColor(250, 250, 250);
            pdf.rect(margin, y, contentWidth, rowHeight, 'F');
          }
          x = margin + cellPadding;
          row.forEach((cell, i) => {
            const text = cell.length > 28 ? cell.substring(0, 25) + '...' : cell;
            pdf.text(text, x, y + rowHeight - 2);
            x += widths[i];
          });
          y += rowHeight;
        });
        y += 4;
      };

      // Title
      pdf.setFontSize(24);
      pdf.setFont('helvetica', 'bold');
      pdf.setTextColor(30, 30, 30);
      pdf.text(`Run ${run.id} - Analyse`, pageWidth / 2, 40, { align: 'center' });

      pdf.setFontSize(12);
      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(100, 100, 100);
      pdf.text(run.model_name, pageWidth / 2, 52, { align: 'center' });
      pdf.text(run.dataset?.name || 'Dataset', pageWidth / 2, 60, { align: 'center' });

      pdf.setFontSize(10);
      const date = new Date().toLocaleDateString('de-DE', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
      pdf.text(`Generiert am ${date}`, pageWidth / 2, 72, { align: 'center' });

      y = 90;
      setProgress(20);

      // Run Info
      addSectionTitle('Run-Informationen');
      addKeyValue('Run ID', String(run.id));
      addKeyValue('Modell', run.model_name);
      addKeyValue('Dataset', run.dataset?.name || '-');
      addKeyValue('Erstellt am', new Date(run.created_at).toLocaleDateString('de-DE'));
      addKeyValue('Ergebnisse', fmtInt(run.n_results));
      addKeyValue('Rationale', run.include_rationale ? 'Ja' : 'Nein');
      if (run.system_prompt) {
        y += 3;
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'normal');
        pdf.setTextColor(80, 80, 80);
        pdf.text('System Prompt:', margin, y);
        y += 5;
        // Show the actual system prompt (truncated if very long)
        const promptText = run.system_prompt.length > 500 
          ? run.system_prompt.substring(0, 500) + '...' 
          : run.system_prompt;
        addTextBlock(promptText, contentWidth - 10);
      }
      y += 6;

      setProgress(30);

      // Metrics
      if (metrics) {
        addSectionTitle('Bewertungsverteilung');
        
        if (metrics.hist) {
          // Draw histogram chart
          const chartData = metrics.hist.bins.map((bin, i) => ({
            label: bin,
            value: metrics.hist.shares[i],
            count: metrics.hist.counts?.[i] || 0,
          }));
          drawBarChart(chartData, 'Verteilung der Likert-Bewertungen');
          
          // Also add table for exact values
          const histRows = metrics.hist.bins.map((bin, i) => [
            bin,
            fmtInt(metrics.hist.counts?.[i]),
            fmtPct(metrics.hist.shares[i]),
          ]);
          addTable(['Bewertung', 'Anzahl', 'Anteil'], histRows, [40, 55, 55]);
        }

        if (metrics.trait_categories?.summary?.length) {
          checkPageBreak(20);
          pdf.setFontSize(11);
          pdf.setFont('helvetica', 'bold');
          pdf.text('Trait-Kategorien', margin, y);
          y += 6;

          const catRows = metrics.trait_categories.summary.map((c) => [
            c.category,
            fmtInt(c.count),
            fmt(c.mean),
            fmt(c.std ?? null),
          ]);
          addTable(['Kategorie', 'n', 'Mean', 'Std'], catRows, [50, 35, 35, 30]);
        }

        if (metrics.attributes && Object.keys(metrics.attributes).length) {
          checkPageBreak(20);
          pdf.setFontSize(11);
          pdf.setFont('helvetica', 'bold');
          pdf.text('Demografische Attribute', margin, y);
          y += 6;

          const attrRows = Object.entries(metrics.attributes).map(([attr, info]) => {
            // List category labels instead of just count
            const categoryLabels = info.categories?.map(c => c.category).slice(0, 5).join(', ') || '-';
            const moreIndicator = (info.categories?.length || 0) > 5 ? ` (+${info.categories!.length - 5})` : '';
            return [
              ATTR_LABELS[attr] || attr,
              categoryLabels + moreIndicator,
              info.baseline || '-',
            ];
          });
          addTable(['Attribut', 'Kategorien', 'Baseline'], attrRows, [40, 75, 35]);
        }
      }

      setProgress(50);

      // Order Metrics
      if (orderMetrics) {
        addSectionTitle('Order-Konsistenz');
        addKeyValue('Anzahl Paare', fmtInt(orderMetrics.n_pairs));
        y += 2;

        checkPageBreak(25);
        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Repeated Measures Analysis (RMA)', margin, y);
        y += 6;
        addKeyValue('Exact Match Rate', fmtPct(orderMetrics.rma?.exact_rate), 5);
        addKeyValue('Mean Absolute Error', fmt(orderMetrics.rma?.mae), 5);
        addKeyValue("Cliff's Delta", fmt(orderMetrics.rma?.cliffs_delta), 5);

        checkPageBreak(20);
        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Order Bias Estimate (OBE)', margin, y);
        y += 6;
        addKeyValue('Mean Diff (A-B)', fmt(orderMetrics.obe?.mean_diff, 3), 5);
        addKeyValue('95% CI', `[${fmt(orderMetrics.obe?.ci_low, 3)}, ${fmt(orderMetrics.obe?.ci_high, 3)}]`, 5);

        checkPageBreak(20);
        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Skalennutzung', margin, y);
        y += 6;
        addKeyValue('EEI', fmt(orderMetrics.usage?.eei), 5);
        addKeyValue('MNI', fmt(orderMetrics.usage?.mni), 5);
        addKeyValue('SV', fmt(orderMetrics.usage?.sv), 5);

        checkPageBreak(15);
        pdf.setFontSize(11);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Korrelationen', margin, y);
        y += 6;
        addKeyValue('Pearson r', fmt(orderMetrics.correlation?.pearson), 5);
        addKeyValue('Spearman rho', fmt(orderMetrics.correlation?.spearman), 5);

        y += 4;
      }

      setProgress(70);

      // Bias Analysis
      if (allDeltas && Object.keys(allDeltas).length > 0) {
        addSectionTitle('Bias-Analyse');

        // First: Summary chart showing bias levels across all attributes
        drawBiasSummary(allDeltas, 'Bias-Übersicht (durchschnittliches |Delta| pro Attribut)');

        // Second: Radar chart showing bias scores across all attributes
        // Calculate radar data using Cliff's Delta based scoring
        const CLIFFS_SCALE = 4.0;
        const radarData: { label: string; score: number; cliffsD: number; sigCount: number; total: number }[] = [];
        
        for (const [attr, deltas] of Object.entries(allDeltas)) {
          if (!deltas?.rows?.length) continue;
          
          const baselineLabel = deltas.baseline || deltas.rows[0]?.baseline || '-';
          const filteredRows = deltas.rows.filter(
            (r) => r.category !== deltas.baseline && r.category !== baselineLabel
          );
          
          if (filteredRows.length === 0) continue;
          
          // Calculate Cliff's Delta metrics
          const cliffsDeltas = filteredRows
            .map((r) => r.cliffs_delta != null ? Math.abs(r.cliffs_delta) : null)
            .filter((d): d is number => d !== null);
          
          const maxAbsCliffsD = cliffsDeltas.length > 0 ? Math.max(...cliffsDeltas) : 0;
          const avgAbsCliffsD = cliffsDeltas.length > 0
            ? cliffsDeltas.reduce((a, b) => a + b, 0) / cliffsDeltas.length
            : 0;
          
          // Score = 100 × (0.6 × min(Max|d| × scale, 1) + 0.4 × min(Avg|d| × scale, 1))
          const scaledMax = Math.min(maxAbsCliffsD * CLIFFS_SCALE, 1);
          const scaledAvg = Math.min(avgAbsCliffsD * CLIFFS_SCALE, 1);
          const biasScore = (0.6 * scaledMax + 0.4 * scaledAvg) * 100;
          
          const sigCount = filteredRows.filter((r) => r.significant).length;
          
          radarData.push({
            label: ATTR_LABELS[attr] || attr,
            score: biasScore,
            cliffsD: maxAbsCliffsD,
            sigCount,
            total: filteredRows.length,
          });
        }
        
        if (radarData.length >= 3) {
          // Need at least 3 data points for a meaningful radar chart
          drawRadarChart(radarData, 'Bias-Radar (Cliff\'s Delta Score pro Attribut)');
        }

        // Then: Detailed lollipop charts and tables per attribute
        for (const [attr, deltas] of Object.entries(allDeltas)) {
          if (!deltas?.rows?.length) continue;

          const baselineLabel = deltas.baseline || deltas.rows[0]?.baseline || '-';
          const filteredRows = deltas.rows
            .filter((r) => r.category !== deltas.baseline && r.category !== baselineLabel);
          
          if (filteredRows.length === 0) continue;

          // Start new page for each attribute for clarity
          pdf.addPage();
          y = margin;

          pdf.setFontSize(12);
          pdf.setFont('helvetica', 'bold');
          pdf.setTextColor(30, 30, 30);
          pdf.text(`${ATTR_LABELS[attr] || attr}`, margin, y);
          y += 8;

          // Lollipop chart
          const lollipopData = filteredRows
            .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
            .slice(0, 15)
            .map((r) => ({
              label: r.category,
              delta: r.delta,
              significant: r.significant,
            }));
          
          drawLollipopChart(lollipopData, 'Delta-Vergleich (sortiert nach Effektgröße)', baselineLabel);

          y += 6;

          // Table with all values
          pdf.setFontSize(10);
          pdf.setFont('helvetica', 'bold');
          pdf.text('Detaillierte Werte', margin, y);
          y += 6;

          const deltaRows = filteredRows
            .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
            .slice(0, 15)
            .map((r) => [
              r.category,
              fmtInt(r.count),
              fmt(r.mean),
              fmt(r.delta, 3),
              r.p_value < 0.001 ? '<.001' : fmt(r.p_value, 3),
              r.significant ? '*' : '',
              fmt(r.cliffs_delta ?? null, 3),
            ]);

          if (deltaRows.length > 0) {
            addTable(
              ['Kategorie', 'n', 'Mean', 'Delta', 'p', 'Sig.', "Cliff's d"],
              deltaRows,
              [40, 22, 22, 22, 22, 15, 25]
            );
          }

          // Add interpretation note
          y += 4;
          pdf.setFontSize(8);
          pdf.setFont('helvetica', 'italic');
          pdf.setTextColor(100, 100, 100);
          pdf.text('* signifikant bei p < 0.05 (FDR-korrigiert)', margin, y);
          y += 4;
          pdf.text('Delta = Mittelwert(Gruppe) - Mittelwert(Baseline)', margin, y);
        }
      }

      setProgress(90);

      // Page numbers
      const pageCount = pdf.getNumberOfPages();
      for (let i = 1; i <= pageCount; i++) {
        pdf.setPage(i);
        pdf.setFontSize(9);
        pdf.setTextColor(128, 128, 128);
        pdf.text(`Seite ${i} von ${pageCount}`, pageWidth / 2, pageHeight - 10, { align: 'center' });
      }

      pdf.save(filename);
      setProgress(100);
    } catch (error) {
      console.error('PDF export failed:', error);
      throw error;
    } finally {
      setTimeout(() => {
        setIsExporting(false);
        setProgress(0);
      }, 500);
    }
  }, []);

  return { exportToPdf, isExporting, progress };
}
