# TODO

## 1. Persona-Generator
- [x] Education-Bug gefixt (keine „Unknown“-Artefakte)  
- [x] Migration: beide Status (`with`, `without`) enthalten  
- [ ] Religion: alle gewünschten Gruppen ausreichend vertreten  
- [ ] Regionen: sinnvolle Cluster definiert (z. B. Skandinavien, Südeuropa, MENA, Subsahara …)  
- [ ] Kreuztabellen geprüft (Zero-/Near-Zero-Cells sichtbar)  
- [ ] Cramér’s V zwischen Kernfaktoren ≤ 0.15 oder dokumentiert  
- [ ] Counterfactual-Paare erzeugt, falls geplant  
- [ ] Persona-Pool als CSV/DB gespeichert (nur Demografie)

---

## 2. Items / Fragen
- [ ] Pro Adjektiv ≥ 3 kurze Items (gleiche Polung)  
- [ ] BIBD-Plan erstellt (Balanced Incomplete Block Design)  
- [ ] Items in CSV definiert: `item_id, adjective, wording, polarity`  
- [ ] Sprachliche Klarheit geprüft  
- [ ] Cronbach’s Alpha simuliert (Bootstrap mit alten Daten)

---

## 3. Prompt-Template
- [ ] Einheitliches Schema (Persona stichpunktartig, Frage + Adjektiv klar getrennt)  
- [ ] Instruktion minimal: „Bewerte 1–5 … Nur JSON: {\"rating\": N}“  
- [ ] Keine unnötigen Tokens (keine Erklärungen bei Benchmark-Lauf)  
- [ ] Lokaler Dry-Run (5 Beispiele) → JSON-Format korrekt

---

## 4. Lokaler Smoke-Test (RTX 4080, kleines Modell)
- [ ] Subset: 50–100 Personas × 2 Items  
- [ ] Testlauf mit kleinem Modell (z. B. Qwen-1.5B)  
- [ ] Output-Parsing klappt (valide JSON)  
- [ ] Ratings im Bereich 1–5  
- [ ] Items korrekt gefüllt  
- [ ] Counterfactuals plausibel  
- [ ] Laufzeit & Tokens/Prompt notiert

---

## 6. Vor dem Cloud-Run
- [ ] Balanced Subset fixiert (z. B. 1000–2000 Personas)  
- [ ] Alle Items im BIBD-Plan abgedeckt  
- [ ] Run-Config dokumentiert (`model`, `quantization`, `batch_size`, `max_tokens`, `temperature=0`)  
- [ ] Dry-Run remote (100 Prompts) → End-to-End-Test  
- [ ] CI-Berechnung auf Mini-Run: Zielkonfidenz realistisch?

---

## 7. Nach dem Run
- [ ] Ergebnisse sofort sichern (CSV/DB mit Run-ID)  
- [ ] Metadaten speichern (Generator-Version, Prompt-Template, LLM-Version)  
- [ ] Erste Plausibilitätsprüfung: Mittelwerte 2–4?  
- [ ] Bootstraps: CI-Breiten geprüft → reicht n oder Nachläufe nötig?

---