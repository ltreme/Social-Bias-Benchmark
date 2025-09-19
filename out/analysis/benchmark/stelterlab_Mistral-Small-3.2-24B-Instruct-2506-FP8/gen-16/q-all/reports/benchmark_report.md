# Benchmark Report – gen_id=16 | models=stelterlab/Mistral-Small-3.2-24B-Instruct-2506-FP8

N Ergebnisse: **10000**
Mittel: 3.51  |  SD: 1.10  |  Median: 4.00

## Abbildungen
![Rating-Verteilung](../rating_distribution.png)

## Gender
- male: mean=3.40 (n=4690)
- female: mean=3.60 (n=4630)
- diverse: mean=3.64 (n=680)

![Mittelwerte - gender](../means_gender.png)

![Delta vs. Baseline - gender](../delta_gender.png)

![Per-Question Forest - gender](../forest_gender.png)

## Origin Region
- Europe: mean=3.50 (n=7340)
- Asia: mean=3.46 (n=1420)
- Africa: mean=3.66 (n=780)
- Americas: mean=3.54 (n=400)
- Oceania: mean=3.35 (n=40)
- nan: mean=3.40 (n=20)

![Mittelwerte - origin_region](../means_origin_region.png)

![Delta vs. Baseline - origin_region](../delta_origin_region.png)

![Per-Question Forest - origin_region](../forest_origin_region.png)

## Religion
- Christians: mean=3.56 (n=3980)
- Religiously_unaffiliated: mean=3.39 (n=2430)
- Muslims: mean=3.53 (n=2430)
- Buddhists: mean=3.53 (n=380)
- Other_religions: mean=3.51 (n=350)
- Hindus: mean=3.50 (n=270)
- Jews: mean=3.69 (n=160)

![Mittelwerte - religion](../means_religion.png)

![Delta vs. Baseline - religion](../delta_religion.png)

![Per-Question Forest - religion](../forest_religion.png)

## Migration Status
- without_migration: mean=3.50 (n=5240)
- with_migration: mean=3.52 (n=4760)

![Mittelwerte - migration_status](../means_migration_status.png)

![Delta vs. Baseline - migration_status](../delta_migration_status.png)

![Per-Question Forest - migration_status](../forest_migration_status.png)

## Sexuality
- heterosexual: mean=3.49 (n=8310)
- bisexual: mean=3.53 (n=850)
- homosexual: mean=3.69 (n=840)

![Mittelwerte - sexuality](../means_sexuality.png)

![Delta vs. Baseline - sexuality](../delta_sexuality.png)

![Per-Question Forest - sexuality](../forest_sexuality.png)

## Marriage Status
- single: mean=3.37 (n=4550)
- married: mean=3.74 (n=3280)
- divorced: mean=3.58 (n=1240)
- widowed: mean=3.28 (n=930)

![Mittelwerte - marriage_status](../means_marriage_status.png)

![Delta vs. Baseline - marriage_status](../delta_marriage_status.png)

![Per-Question Forest - marriage_status](../forest_marriage_status.png)

## Education
- Haupt- (Volks-)schulabschluss: mean=3.63 (n=6420)
- Noch in schulischer Ausbildung: mean=3.77 (n=1980)
- Unknown: mean=2.69 (n=1600)

![Mittelwerte - education](../means_education.png)

![Delta vs. Baseline - education](../delta_education.png)

## Occupation
- Rentner/in: mean=3.13 (n=2310)
- Schüler/in: mean=3.14 (n=1190)
- Krankenpfleger/in: mean=4.06 (n=790)
- Polizist/in: mean=4.03 (n=750)
- Verkäufer/in: mean=3.39 (n=740)
- Informatiker/in: mean=3.55 (n=690)
- Lehrer/in: mean=4.04 (n=660)
- Soldat/in: mean=3.97 (n=650)
- Arbeitslos: mean=2.11 (n=630)
- Arzt/Ärztin: mean=4.05 (n=590)

## Signifikanz-Tabellen (p, q, Cliff_delta)
### Gender
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| female | 4630 | 3.60 | 0.20 | 0.000 | 0.001 | -0.11 | yes |
| diverse | 680 | 3.64 | 0.24 | 0.000 | 0.001 | -0.12 | yes |
| male | 4690 | 3.40 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Origin Region
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Africa | 780 | 3.66 | 0.16 | 0.000 | 0.003 | -0.08 | yes |
| Europe | 7340 | 3.50 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Asia | 1420 | 3.46 | -0.04 | 0.161 | 0.484 | 0.02 |  |
| Americas | 400 | 3.54 | 0.03 | 0.577 | 0.807 | -0.02 |  |
| Oceania | 40 | 3.35 | -0.15 | 0.374 | 0.749 | 0.09 |  |
| nan | 20 | 3.40 | -0.10 | 0.672 | 0.807 | 0.04 |  |

### Religion
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Religiously_unaffiliated | 2430 | 3.39 | -0.17 | 0.000 | 0.003 | 0.10 | yes |
| Christians | 3980 | 3.56 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| Muslims | 2430 | 3.53 | -0.03 | 0.361 | 0.614 | 0.03 |  |
| Buddhists | 380 | 3.53 | -0.03 | 0.699 | 0.815 | 0.04 |  |
| Other_religions | 350 | 3.51 | -0.05 | 0.439 | 0.614 | 0.03 |  |
| Hindus | 270 | 3.50 | -0.06 | 0.419 | 0.614 | 0.05 |  |
| Jews | 160 | 3.69 | 0.13 | 0.160 | 0.560 | -0.04 |  |

### Migration Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| without_migration | 5240 | 3.50 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| with_migration | 4760 | 3.52 | 0.02 | 0.275 | 0.551 | -0.02 |  |

### Sexuality
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| homosexual | 840 | 3.69 | 0.20 | 0.000 | 0.001 | -0.09 | yes |
| heterosexual | 8310 | 3.49 | 0.00 | 1.000 | 1.000 | 0.00 |  |
| bisexual | 850 | 3.53 | 0.04 | 0.323 | 0.484 | -0.02 |  |

### Marriage Status
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| married | 3280 | 3.74 | 0.37 | 0.000 | 0.001 | -0.19 | yes |
| divorced | 1240 | 3.58 | 0.20 | 0.000 | 0.001 | -0.10 | yes |
| widowed | 930 | 3.28 | -0.09 | 0.028 | 0.037 | 0.04 | yes |
| single | 4550 | 3.37 | 0.00 | 1.000 | 1.000 | 0.00 |  |

### Education
| Kategorie | n | Mittel | Delta | p | q | Cliff_delta | Sig |
|---|---:|---:|---:|---:|---:|---:|:--:|
| Haupt- (Volks-)schulabschluss | 6420 | 3.63 | nan | nan | 1.000 | nan |  |
| Noch in schulischer Ausbildung | 1980 | 3.77 | nan | nan | 1.000 | nan |  |
| Unknown | 1600 | 2.69 | nan | nan | 1.000 | nan |  |
