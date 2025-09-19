# Benchmark Report – gen_id=13 | models=stelterlab/Mistral-Small-3.2-24B-Instruct-2506-FP8

N Ergebnisse: **10000**
Mittel: 3.47  |  SD: 1.06  |  Median: 4.00

## Abbildungen
![Rating-Verteilung](../rating_distribution.png)

## Gender
- diverse: mean=3.59 (n=3460)
- male: mean=3.27 (n=3410)
- female: mean=3.54 (n=3130)

![Mittelwerte - gender](../means_gender.png)

![Delta vs. Baseline - gender](../delta_gender.png)

![Per-Question Forest - gender](../forest_gender.png)

## Origin Region
- Europe: mean=3.45 (n=6260)
- Asia: mean=3.47 (n=1240)
- Africa: mean=3.54 (n=1230)
- Americas: mean=3.45 (n=970)
- Oceania: mean=3.41 (n=270)
- nan: mean=3.53 (n=30)

![Mittelwerte - origin_region](../means_origin_region.png)

![Delta vs. Baseline - origin_region](../delta_origin_region.png)

![Per-Question Forest - origin_region](../forest_origin_region.png)

## Religion
- Christians: mean=3.41 (n=1700)
- Other_religions: mean=3.52 (n=1590)
- Muslims: mean=3.52 (n=1530)
- Hindus: mean=3.48 (n=1420)
- Buddhists: mean=3.37 (n=1410)
- Religiously_unaffiliated: mean=3.42 (n=1400)
- Jews: mean=3.57 (n=950)

![Mittelwerte - religion](../means_religion.png)

![Delta vs. Baseline - religion](../delta_religion.png)

![Per-Question Forest - religion](../forest_religion.png)

## Migration Status
- without_migration: mean=3.46 (n=5240)
- with_migration: mean=3.48 (n=4760)

![Mittelwerte - migration_status](../means_migration_status.png)

![Delta vs. Baseline - migration_status](../delta_migration_status.png)

![Per-Question Forest - migration_status](../forest_migration_status.png)

## Sexuality
- heterosexual: mean=3.44 (n=3510)
- homosexual: mean=3.49 (n=3390)
- bisexual: mean=3.47 (n=3100)

![Mittelwerte - sexuality](../means_sexuality.png)

![Delta vs. Baseline - sexuality](../delta_sexuality.png)

![Per-Question Forest - sexuality](../forest_sexuality.png)

## Marriage Status
- divorced: mean=3.43 (n=2640)
- widowed: mean=3.44 (n=2610)
- single: mean=3.44 (n=2500)
- married: mean=3.57 (n=2250)

![Mittelwerte - marriage_status](../means_marriage_status.png)

![Delta vs. Baseline - marriage_status](../delta_marriage_status.png)

![Per-Question Forest - marriage_status](../forest_marriage_status.png)

## Education
- Haupt- (Volks-)schulabschluss: mean=3.56 (n=6640)
- Noch in schulischer Ausbildung: mean=3.74 (n=1890)
- Unknown: mean=2.71 (n=1470)

![Mittelwerte - education](../means_education.png)

![Delta vs. Baseline - education](../delta_education.png)

## Occupation
- Rentner/in: mean=3.18 (n=3400)
- Schüler/in: mean=3.17 (n=1090)
- Verkäufer/in: mean=3.45 (n=660)
- Polizist/in: mean=4.06 (n=650)
- Arbeitslos: mean=2.14 (n=600)
- Krankenpfleger/in: mean=4.02 (n=590)
- Richter/in: mean=4.01 (n=580)
- Soldat/in: mean=4.01 (n=570)
- Informatiker/in: mean=3.45 (n=520)
- Arzt/Ärztin: mean=4.12 (n=490)

## Signifikanz-Tabellen (p, q, Cliff_delta)
### Gender
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| diverse | 3460 | 3.59 | 0.32 | 0.000 | 0.001 | -0.17 | yes |
| female | 3130 | 3.54 | 0.27 | 0.000 | 0.001 | -0.14 | yes |
| male | 3410 | 3.27 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Origin Region
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Africa | 1230 | 3.54 | 0.09 | 0.008 | 0.048 | -0.05 | yes |
| Europe | 6260 | 3.45 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Asia | 1240 | 3.47 | 0.02 | 0.626 | 1.000 | -0.01 |  |
| Americas | 970 | 3.45 | 0.00 | 1.000 | 1.000 | 0.01 |  |
| Oceania | 270 | 3.41 | -0.05 | 0.478 | 1.000 | 0.02 |  |
| nan | 30 | 3.53 | 0.08 | 0.732 | 1.000 | -0.00 |  |

### Religion
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Other_religions | 1590 | 3.52 | 0.11 | 0.003 | 0.012 | -0.04 | yes |
| Muslims | 1530 | 3.52 | 0.10 | 0.008 | 0.020 | -0.04 | yes |
| Jews | 950 | 3.57 | 0.15 | 0.001 | 0.007 | -0.07 | yes |
| Christians | 1700 | 3.41 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Hindus | 1420 | 3.48 | 0.06 | 0.126 | 0.221 | -0.02 |  |
| Buddhists | 1410 | 3.37 | -0.04 | 0.291 | 0.407 | 0.03 |  |
| Religiously_unaffiliated | 1400 | 3.42 | 0.01 | 0.808 | 0.943 | 0.01 |  |

### Migration Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| without_migration | 5240 | 3.46 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| with_migration | 4760 | 3.48 | 0.02 | 0.471 | 0.943 | -0.01 |  |

### Sexuality
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| heterosexual | 3510 | 3.44 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| homosexual | 3390 | 3.49 | 0.05 | 0.065 | 0.196 | -0.02 |  |
| bisexual | 3100 | 3.47 | 0.02 | 0.407 | 0.611 | -0.00 |  |

### Marriage Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| married | 2250 | 3.57 | 0.13 | 0.000 | 0.002 | -0.06 | yes |
| divorced | 2640 | 3.43 | -0.02 | 0.584 | 1.000 | 0.02 |  |
| widowed | 2610 | 3.44 | -0.00 | 0.973 | 1.000 | 0.01 |  |
| single | 2500 | 3.44 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Education
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Haupt- (Volks-)schulabschluss | 6640 | 3.56 | nan | nan | 1.000 | nan |  |
| Noch in schulischer Ausbildung | 1890 | 3.74 | nan | nan | 1.000 | nan |  |
| Unknown | 1470 | 2.71 | nan | nan | 1.000 | nan |  |
