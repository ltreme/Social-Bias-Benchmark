# Benchmark Report – gen_id=12 | models=stelterlab/Mistral-Small-3.2-24B-Instruct-2506-FP8

N Ergebnisse: **10000**
Mittel: 3.61  |  SD: 1.10  |  Median: 4.00

## Abbildungen
![Rating-Verteilung](../rating_distribution.png)

## Gender
- female: mean=3.68 (n=5170)
- male: mean=3.52 (n=4760)
- diverse: mean=3.97 (n=70)

![Mittelwerte - gender](../means_gender.png)

![Delta vs. Baseline - gender](../delta_gender.png)

![Per-Question Forest - gender](../forest_gender.png)

## Origin Region
- Europe: mean=3.59 (n=8380)
- Asia: mean=3.66 (n=1310)
- Africa: mean=3.70 (n=210)
- Americas: mean=3.77 (n=100)

![Mittelwerte - origin_region](../means_origin_region.png)

![Delta vs. Baseline - origin_region](../delta_origin_region.png)

![Per-Question Forest - origin_region](../forest_origin_region.png)

## Religion
- Christians: mean=3.64 (n=5450)
- Religiously_unaffiliated: mean=3.51 (n=2390)
- Muslims: mean=3.65 (n=1930)
- Hindus: mean=3.67 (n=80)
- Buddhists: mean=3.10 (n=80)
- Other_religions: mean=3.30 (n=60)
- Jews: mean=4.10 (n=10)

![Mittelwerte - religion](../means_religion.png)

![Delta vs. Baseline - religion](../delta_religion.png)

![Per-Question Forest - religion](../forest_religion.png)

## Migration Status
- without_migration: mean=3.57 (n=6020)
- with_migration: mean=3.66 (n=3980)

![Mittelwerte - migration_status](../means_migration_status.png)

![Delta vs. Baseline - migration_status](../delta_migration_status.png)

![Per-Question Forest - migration_status](../forest_migration_status.png)

## Sexuality
- heterosexual: mean=3.61 (n=9770)
- homosexual: mean=3.62 (n=130)
- bisexual: mean=3.55 (n=100)

![Mittelwerte - sexuality](../means_sexuality.png)

![Delta vs. Baseline - sexuality](../delta_sexuality.png)

![Per-Question Forest - sexuality](../forest_sexuality.png)

## Marriage Status
- married: mean=3.78 (n=4370)
- single: mean=3.48 (n=4230)
- divorced: mean=3.58 (n=820)
- widowed: mean=3.29 (n=580)

![Mittelwerte - marriage_status](../means_marriage_status.png)

![Delta vs. Baseline - marriage_status](../delta_marriage_status.png)

![Per-Question Forest - marriage_status](../forest_marriage_status.png)

## Education
- Haupt- (Volks-)schulabschluss: mean=3.73 (n=6610)
- Noch in schulischer Ausbildung: mean=3.75 (n=2170)
- Unknown: mean=2.69 (n=1220)

![Mittelwerte - education](../means_education.png)

![Delta vs. Baseline - education](../delta_education.png)

![Per-Question Forest - education](../forest_education.png)

## Occupation
- Rentner/in: mean=3.28 (n=1950)
- Schüler/in: mean=3.18 (n=970)
- Verkäufer/in: mean=3.37 (n=890)
- Lehrer/in: mean=4.06 (n=850)
- Soldat/in: mean=4.05 (n=800)
- Polizist/in: mean=4.03 (n=750)
- Arzt/Ärztin: mean=4.07 (n=710)
- Krankenpfleger/in: mean=4.05 (n=710)
- Informatiker/in: mean=3.48 (n=680)
- Richter/in: mean=3.92 (n=660)

## Signifikanz-Tabellen (p, q, Cliff_delta)
### Gender
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| female | 5170 | 3.68 | 0.17 | 0.000 | 0.001 | -0.10 | yes |
| diverse | 70 | 3.97 | 0.45 | 0.001 | 0.001 | -0.24 | yes |
| male | 4760 | 3.52 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Origin Region
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Europe | 8380 | 3.59 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Asia | 1310 | 3.66 | 0.06 | 0.066 | 0.197 | -0.02 |  |
| Africa | 210 | 3.70 | 0.11 | 0.147 | 0.197 | -0.06 |  |
| Americas | 100 | 3.77 | 0.18 | 0.120 | 0.197 | -0.08 |  |

### Religion
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Religiously_unaffiliated | 2390 | 3.51 | -0.14 | 0.000 | 0.002 | 0.07 | yes |
| Buddhists | 80 | 3.10 | -0.54 | 0.000 | 0.002 | 0.27 | yes |
| Other_religions | 60 | 3.30 | -0.34 | 0.016 | 0.037 | 0.19 | yes |
| Christians | 5450 | 3.64 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Muslims | 1930 | 3.65 | 0.01 | 0.715 | 0.928 | 0.00 |  |
| Hindus | 80 | 3.67 | 0.03 | 0.795 | 0.928 | 0.01 |  |
| Jews | 10 | 4.10 | 0.46 | 0.205 | 0.359 | -0.24 |  |

### Migration Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| with_migration | 3980 | 3.66 | 0.09 | 0.001 | 0.002 | -0.04 | yes |
| without_migration | 6020 | 3.57 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Sexuality
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| heterosexual | 9770 | 3.61 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| homosexual | 130 | 3.62 | 0.01 | 0.941 | 1.000 | 0.01 |  |
| bisexual | 100 | 3.55 | -0.06 | 0.618 | 1.000 | -0.01 |  |

### Marriage Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| married | 4370 | 3.78 | 0.30 | 0.000 | 0.001 | -0.15 | yes |
| divorced | 820 | 3.58 | 0.10 | 0.019 | 0.026 | -0.04 | yes |
| widowed | 580 | 3.29 | -0.19 | 0.000 | 0.001 | 0.09 | yes |
| single | 4230 | 3.48 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Education
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Haupt- (Volks-)schulabschluss | 6610 | 3.73 | nan | nan | 1.000 | nan |  |
| Noch in schulischer Ausbildung | 2170 | 3.75 | nan | nan | 1.000 | nan |  |
| Unknown | 1220 | 2.69 | nan | nan | 1.000 | nan |  |
