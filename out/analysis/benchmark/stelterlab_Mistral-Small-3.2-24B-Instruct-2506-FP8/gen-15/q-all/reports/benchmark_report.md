# Benchmark Report – gen_id=15 | models=stelterlab/Mistral-Small-3.2-24B-Instruct-2506-FP8

N Ergebnisse: **10000**
Mittel: 3.60  |  SD: 1.14  |  Median: 4.00

## Abbildungen
![Rating-Verteilung](../rating_distribution.png)

## Gender
- female: mean=3.60 (n=10000)

![Mittelwerte - gender](../means_gender.png)

![Delta vs. Baseline - gender](../delta_gender.png)

## Origin Region
- Europe: mean=3.63 (n=5790)
- Asia: mean=3.57 (n=3430)
- Africa: mean=3.43 (n=530)
- Americas: mean=3.70 (n=240)
- Oceania: mean=4.00 (n=10)

![Mittelwerte - origin_region](../means_origin_region.png)

![Delta vs. Baseline - origin_region](../delta_origin_region.png)

![Per-Question Forest - origin_region](../forest_origin_region.png)

## Religion
- Muslims: mean=3.58 (n=8970)
- Jews: mean=3.80 (n=1030)

![Mittelwerte - religion](../means_religion.png)

![Delta vs. Baseline - religion](../delta_religion.png)

## Migration Status
- with_migration: mean=3.60 (n=10000)

![Mittelwerte - migration_status](../means_migration_status.png)

![Delta vs. Baseline - migration_status](../delta_migration_status.png)

## Sexuality
- heterosexual: mean=3.60 (n=9830)
- bisexual: mean=3.56 (n=100)
- homosexual: mean=3.27 (n=70)

![Mittelwerte - sexuality](../means_sexuality.png)

![Delta vs. Baseline - sexuality](../delta_sexuality.png)

![Per-Question Forest - sexuality](../forest_sexuality.png)

## Marriage Status
- single: mean=3.47 (n=4580)
- married: mean=3.81 (n=4190)
- widowed: mean=3.07 (n=620)
- divorced: mean=3.64 (n=610)

![Mittelwerte - marriage_status](../means_marriage_status.png)

![Delta vs. Baseline - marriage_status](../delta_marriage_status.png)

![Per-Question Forest - marriage_status](../forest_marriage_status.png)

## Education
- Haupt- (Volks-)schulabschluss: mean=3.73 (n=6240)
- Noch in schulischer Ausbildung: mean=3.81 (n=2400)
- Unknown: mean=2.64 (n=1360)

![Mittelwerte - education](../means_education.png)

![Delta vs. Baseline - education](../delta_education.png)

## Occupation
- Rentner/in: mean=3.22 (n=1850)
- Schüler/in: mean=3.19 (n=1000)
- Verkäufer/in: mean=3.36 (n=950)
- Krankenpfleger/in: mean=4.03 (n=850)
- Arzt/Ärztin: mean=4.14 (n=790)
- Informatiker/in: mean=3.53 (n=750)
- Lehrer/in: mean=4.06 (n=720)
- Polizist/in: mean=4.06 (n=690)
- Soldat/in: mean=4.09 (n=650)
- Manager/in: mean=4.06 (n=620)

## Signifikanz-Tabellen (p, q, Cliff_delta)
### Gender
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| female | 10000 | 3.60 | nan | nan | 1.000 | nan |  |

### Origin Region
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Asia | 3430 | 3.57 | -0.06 | 0.015 | 0.037 | 0.03 | yes |
| Africa | 530 | 3.43 | -0.20 | 0.000 | 0.002 | 0.11 | yes |
| Europe | 5790 | 3.63 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Americas | 240 | 3.70 | 0.07 | 0.351 | 0.439 | -0.02 |  |
| Oceania | 10 | 4.00 | 0.37 | 0.318 | 0.439 | -0.22 |  |

### Religion
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Muslims | 8970 | 3.58 | nan | nan | 1.000 | nan |  |
| Jews | 1030 | 3.80 | nan | nan | 1.000 | nan |  |

### Migration Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| with_migration | 10000 | 3.60 | nan | nan | 1.000 | nan |  |

### Sexuality
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| homosexual | 70 | 3.27 | -0.33 | 0.019 | 0.057 | 0.14 | yes |
| heterosexual | 9830 | 3.60 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| bisexual | 100 | 3.56 | -0.04 | 0.733 | 1.000 | 0.02 |  |

### Marriage Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| married | 4190 | 3.81 | 0.34 | 0.000 | 0.001 | -0.17 | yes |
| widowed | 620 | 3.07 | -0.40 | 0.000 | 0.001 | 0.19 | yes |
| divorced | 610 | 3.64 | 0.17 | 0.001 | 0.001 | -0.08 | yes |
| single | 4580 | 3.47 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Education
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Haupt- (Volks-)schulabschluss | 6240 | 3.73 | nan | nan | 1.000 | nan |  |
| Noch in schulischer Ausbildung | 2400 | 3.81 | nan | nan | 1.000 | nan |  |
| Unknown | 1360 | 2.64 | nan | nan | 1.000 | nan |  |
