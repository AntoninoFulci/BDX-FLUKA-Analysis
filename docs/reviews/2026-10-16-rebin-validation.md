# Rebin prima dello smoothing — verifica 16 ottobre 2026

Implementata opzione `rebin: N` per ciascun confronto, default `1` (inattiva). Richiesta utente: ROOT Rebin prima del plot e dello smoothing, conservando normalizzazione e integrale.

## Comportamento

- Ogni spettro TH1F/TH1D viene clonato, staccato dal file e affidato esplicitamente a Python per la distruzione.
- Densità ed errori moltiplicati per le larghezze originali; `Rebin(N)` somma i contenuti e propaga `Sumw2`; `Scale(1, "width")` ripristina le densità. Conservati anche entries e contributi di underflow/overflow.
- Fattore intero positivo, divisore esatto del numero di bin di ogni spettro. Questo mantiene l’intero range ed evita lo spostamento dei bin residui in overflow previsto da ROOT. Profili, TH2 e istogrammi interi rifiutati quando il rebin è attivo.
- Rebin su tutte le curve; successivamente smoothing delle sole curve selezionate. Sigma espresso nei nuovi bin. Nessun cambiamento all’algoritmo gaussiano.
- Excel calcolato sugli input originali. I file ROOT non vengono modificati. Lo smoothing resta visualizzazione: la conservazione dell’integrale è garantita dal rebin, non dalla successiva curva smussata.

Fonte primaria: [ROOT TH1::Rebin](https://root.cern.ch/doc/master/classTH1.html). Documentazione consultata tramite Context7 e riferimento ufficiale ROOT; esecuzione verificata con ROOT 6.40.04.

## Prove

- **107 test superati in 9,10 secondi**, senza warning.
- Ruff E7/E9/F, compilazione Python in memoria, caricamento degli esempi YAML e `git diff --check`: superati.
- Regressioni: bin uniformi e variabili, errori presenti/assenti, integrali e incertezze, flow bins, input immutati, fattori invalidi, rebin prima dello smoothing, selezione delle curve, file/canvas e ownership delle copie su successo/errore.
- Review indipendente: corretto rilascio delle copie ROOT; nessun rilievo residuo.

## propA_spectra_fullrange

Configurazione identificata tramite figura e descrizione dell’articolo: `ComparisonPlots/figure4/comparison_figure4_fullrange.yaml` (Pipe 1: 20×20, sopra il suolo: 100×100), non variante `_ALL`.

Tre spettri da 1000 bin logaritmici. Verificati fattori 2, 5 e 10: 500, 200 e 100 bin. Confrontato ogni contenuto ed errore raggruppato con somma pesata indipendente; confrontati integrale e incertezza sull’intero range. Massimo scarto relativo fra tutte le misure: **1,4795×10⁻¹⁵**.

Esempio fattore 5 (integrali n/EOT):

| Spettro | Prima | Dopo |
|---|---:|---:|
| Production - No Radiator | 0.1085681118627791 | 0.108568111862779 |
| BDX-Mini Well 1 - 20x20 | 1.118712013132473e-20 | 1.118712013132474e-20 |
| Above Soil - 100x100 | 2.133957539291796e-12 | 2.133957539291796e-12 |

Sei esecuzioni CLI in modalità batch ROOT, tutte riuscite: baseline, fattore 2 overlay, fattore 5 senza smoothing/overlay/replace, fattore 10 overlay. Ogni esecuzione ha prodotto PDF, macro ed Excel. Sigma nei nuovi bin impostato a 10/N per confrontare una larghezza di smoothing simile alla precedente; selezione `smooth_hists: [1, 2]` conservata.

Controllo visivo dei PDF baseline, rebin5 senza smoothing e rebin5 overlay: curve, legenda e assi presenti e coerenti. SHA-256 dei tre input ROOT e dello YAML esterno invariati.

Risultati prodotti e verificati in `tmp_validation/rebin/`: YAML delle varianti, grafici, misure JSON e log. Su richiesta dell’utente, l’intera cartella temporanea e le cache sono state rimosse prima del commit/push; questo report conserva gli esiti numerici.

Esempio da aggiungere alla configurazione:

```yaml
rebin: 5
smoothing: overlay
smoothing_sigma: 2
```
