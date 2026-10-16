# Rebin selettivo e varianti — 16 ottobre 2026

Implementate due estensioni dei confronti:

```yaml
rebin: [5, 10]
rebin_hists: [1, 2]
smoothing: overlay
smooth_hists: [1, 2]
smoothing_sigma: 2
```

`rebin_hists` usa indici da zero riferiti alle righe `hists` originali, etichette esatte o una combinazione dei due. Omesso/null seleziona tutti; lista vuota nessuno. Indici fuori intervallo, etichette inesistenti o ambigue e tipi invalidi producono errore. Le curve non selezionate mantengono il binning originale; quelle mancanti non spostano gli indici.

Una lista `rebin` produce figure indipendenti nell’ordine richiesto, con suffissi `_rebin5`, `_rebin10`, ecc. Excel e macro opzionali usano gli stessi suffissi. Valore scalare conserva nomi e comportamento precedenti. Anche una lista con un solo elemento aggiunge il suffisso; `1` permette una variante senza rebin. Liste vuote, fattori duplicati e valori non interi positivi sono rifiutati.

Ogni variante ricarica gli input originali: nessun rebin cumulativo o riuso di range/stili modificati dal disegno precedente. Preservate opzioni runtime come `save_macro` e configurazione originale. Verifica divisibilità applicata soltanto agli istogrammi selezionati e disponibili. Ogni variante viene eseguita separatamente: se una successiva fallisce, la CLI segnala errore e gli output precedenti rimangono disponibili.

Algoritmi di conservazione della densità e smoothing invariati. Selezioni `rebin_hists` e `smooth_hists` indipendenti; sigma resta costante fra varianti e si misura nei bin di ciascuna curva dopo il rebin eventualmente applicato. Excel continua a usare gli input originali.

## Verifiche

- **134 test superati in 8,70 secondi**, senza warning.
- Ruff E7/E9/F, compilazione in memoria, parsing degli esempi YAML e `git diff --check`: superati.
- Test nuovi: configurazione YAML, selezione per indice/etichetta/mista, selezione vuota, input mancante, divisibilità dei soli selezionati, fattori invalidi/duplicati, label ambigue, suffissi, indipendenza delle varianti e configurazione non mutata.
- Integrazione in modalità smoothing off/overlay/replace: PDF/macro/Excel separati, binning selettivo corretto, integrali/errori conservati, workbook equivalenti, risorse ROOT chiuse, file input immutati.
- Review indipendente: nessuna regressione concreta rilevata.

## Dati reali propA

Configurazione di partenza: `ComparisonPlots/figure4/comparison_figure4_fullrange.yaml`. Copia locale con `output: propA_spectra_fullrange`, fattori `[5, 10]`, selezione mista `[1, "Above Soil - 100x100"]`, smoothing overlay sui due spettri selezionati e sigma 2.

| Spettro | Bin originali | Variante 5 | Variante 10 |
|---|---:|---:|---:|
| Production - No Radiator | 1000 | 1000 | 1000 |
| BDX-Mini Well 1 - 20x20 | 1000 | 200 | 100 |
| Above Soil - 100x100 | 1000 | 200 | 100 |

CLI batch riuscita: due PDF, due macro ROOT, due workbook. Gli input dello smoothing hanno rispettivamente 200/200 e 100/100 bin. Contenuti/errori dello spettro di produzione esattamente invariati. Massimo scarto relativo su integrali e incertezze delle due varianti: **1,2105×10⁻¹⁵**. Celle dei due workbook identiche; SHA-256 degli input ROOT e dello YAML originale invariati. Nessun file/canvas ROOT aperto al termine.

Output e configurazione di verifica creati in `tmp_validation/rebin_sets/`. Controllati anche visivamente entrambi i grafici. Su richiesta dell’utente, temporanei, grafici, log e cache sono stati eliminati prima del commit/push; risultati conservati in questo report e test automatizzati nella suite.
