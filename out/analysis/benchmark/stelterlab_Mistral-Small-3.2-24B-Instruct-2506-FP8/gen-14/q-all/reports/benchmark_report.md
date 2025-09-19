# Benchmark Report – gen_id=14 | models=stelterlab/Mistral-Small-3.2-24B-Instruct-2506-FP8

N Ergebnisse: **10000**
Mittel: 3.60  |  SD: 1.09  |  Median: 4.00

## Abbildungen
![Rating-Verteilung](../rating_distribution.png)

## Gender
- male: mean=3.52 (n=5100)
- female: mean=3.68 (n=4830)
- diverse: mean=3.70 (n=70)

![Mittelwerte - gender](../means_gender.png)

![Delta vs. Baseline - gender](../delta_gender.png)

![Per-Question Forest - gender](../forest_gender.png)

## Origin Region
- Europe: mean=3.65 (n=5740)
- Asia: mean=3.51 (n=3410)
- Africa: mean=3.68 (n=560)
- Americas: mean=3.53 (n=270)
- nan: mean=3.70 (n=10)
- Oceania: mean=3.20 (n=10)

![Mittelwerte - origin_region](../means_origin_region.png)

![Delta vs. Baseline - origin_region](../delta_origin_region.png)

![Per-Question Forest - origin_region](../forest_origin_region.png)

## Religion
- Christians: mean=3.66 (n=4970)
- Muslims: mean=3.55 (n=3450)
- Religiously_unaffiliated: mean=3.55 (n=1070)
- Hindus: mean=3.49 (n=290)
- Buddhists: mean=3.34 (n=120)
- Other_religions: mean=3.73 (n=80)
- Jews: mean=3.55 (n=20)

![Mittelwerte - religion](../means_religion.png)

![Delta vs. Baseline - religion](../delta_religion.png)

![Per-Question Forest - religion](../forest_religion.png)

## Migration Status
- with_migration: mean=3.60 (n=10000)

![Mittelwerte - migration_status](../means_migration_status.png)

![Delta vs. Baseline - migration_status](../delta_migration_status.png)

## Sexuality
- heterosexual: mean=3.60 (n=9830)
- homosexual: mean=3.17 (n=90)
- bisexual: mean=3.59 (n=80)

![Mittelwerte - sexuality](../means_sexuality.png)

![Delta vs. Baseline - sexuality](../delta_sexuality.png)

![Per-Question Forest - sexuality](../forest_sexuality.png)

## Marriage Status
- married: mean=3.80 (n=4230)
- single: mean=3.47 (n=4220)
- widowed: mean=3.18 (n=800)
- divorced: mean=3.69 (n=750)

![Mittelwerte - marriage_status](../means_marriage_status.png)

![Delta vs. Baseline - marriage_status](../delta_marriage_status.png)

![Per-Question Forest - marriage_status](../forest_marriage_status.png)

## Education
- Haupt- (Volks-)schulabschluss: mean=3.72 (n=6580)
- Noch in schulischer Ausbildung: mean=3.75 (n=2180)
- Unknown: mean=2.70 (n=1240)

![Mittelwerte - education](../means_education.png)

![Delta vs. Baseline - education](../delta_education.png)

## Occupation
- Rentner/in: mean=3.21 (n=1910)
- Soldat/in: mean=4.03 (n=1030)
- Schüler/in: mean=3.13 (n=1000)
- Verkäufer/in: mean=3.43 (n=780)
- Informatiker/in: mean=3.54 (n=760)
- Polizist/in: mean=4.02 (n=730)
- Krankenpfleger/in: mean=4.03 (n=720)
- Arzt/Ärztin: mean=4.06 (n=690)
- Lehrer/in: mean=4.02 (n=690)
- Manager/in: mean=3.96 (n=650)

## Signifikanz-Tabellen (p, q, Cliff_delta)
### Gender
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| female | 4830 | 3.68 | 0.16 | 0.000 | 0.001 | -0.09 | yes |
| male | 5100 | 3.52 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| diverse | 70 | 3.70 | 0.18 | 0.168 | 0.253 | -0.08 |  |

### Origin Region
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Asia | 3410 | 3.51 | -0.14 | 0.000 | 0.003 | 0.07 | yes |
| Europe | 5740 | 3.65 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Africa | 560 | 3.68 | 0.03 | 0.546 | 0.819 | -0.02 |  |
| Americas | 270 | 3.53 | -0.12 | 0.082 | 0.246 | 0.07 |  |
| Oceania | 10 | 3.20 | -0.45 | 0.249 | 0.498 | 0.29 |  |
| nan | 10 | 3.70 | 0.05 | 0.879 | 1.000 | -0.04 |  |

### Religion
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Muslims | 3450 | 3.55 | -0.11 | 0.000 | 0.003 | 0.06 | yes |
| Religiously_unaffiliated | 1070 | 3.55 | -0.10 | 0.006 | 0.014 | 0.06 | yes |
| Hindus | 290 | 3.49 | -0.17 | 0.008 | 0.015 | 0.10 | yes |
| Buddhists | 120 | 3.34 | -0.32 | 0.001 | 0.003 | 0.16 | yes |
| Christians | 4970 | 3.66 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Other_religions | 80 | 3.73 | 0.07 | 0.615 | 0.802 | -0.01 |  |
| Jews | 20 | 3.55 | -0.11 | 0.687 | 0.802 | 0.11 |  |

### Migration Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| with_migration | 10000 | 3.60 | nan | nan | 1.000 | nan |  |

### Sexuality
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| homosexual | 90 | 3.17 | -0.44 | 0.000 | 0.001 | 0.16 | yes |
| heterosexual | 9830 | 3.60 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| bisexual | 80 | 3.59 | -0.02 | 0.919 | 1.000 | 0.02 |  |

### Marriage Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| married | 4230 | 3.80 | 0.33 | 0.000 | 0.001 | -0.18 | yes |
| widowed | 800 | 3.18 | -0.28 | 0.000 | 0.001 | 0.14 | yes |
| divorced | 750 | 3.69 | 0.23 | 0.000 | 0.001 | -0.11 | yes |
| single | 4220 | 3.47 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Education
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Haupt- (Volks-)schulabschluss | 6580 | 3.72 | nan | nan | 1.000 | nan |  |
| Noch in schulischer Ausbildung | 2180 | 3.75 | nan | nan | 1.000 | nan |  |
| Unknown | 1240 | 2.70 | nan | nan | 1.000 | nan |  |
