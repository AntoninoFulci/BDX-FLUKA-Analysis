# Review completa e semplificazione — 16 ottobre 2026

Esaminati tutti i moduli Python in `src/`, entry point, test, configurazioni di esempio e documentazione. Applicata la skill `code-simplification`; review indipendente prima e dopo le modifiche. Nessun commit eseguito.

Preservate le modifiche inizialmente presenti in `src/export_histograms.py` e il test non tracciato `tests/test_export_histogram_statistics.py`: le mappe TH2 vengono integrate senza area del pixel; gli spettri TH1 con larghezza dei bin.

## Correzioni completate

| Problema | Risultato |
|---|---|
| Istogramma mancante spostava identità degli input successivi. | Conservati indici originali per etichette, colori, ordine legenda e selezione smoothing. |
| Autoscale considerava soltanto la prima curva. | Massimo su tutte le curve nel range X visibile; limiti Y espliciti prioritari. |
| Range diversi producevano nomi arrotondati identici e sovrascritture. | Preflight rifiuta nomi duplicati entro una configurazione, prima della scrittura degli istogrammi. Formato predefinito invariato. |
| Prerequisito condiviso interpretato come ciclo. | Rilevamento sulla catena di chiamate attiva; cicli veri continuano a fallire. |
| EOT riutilizzato senza verifica degli input. | Warning esplicito quando viene letta la cache; nessun ricalcolo automatico. L'utente sceglie directory separata o `--remove-runsummary`. |
| Export limitato ai nomi predefiniti; etichette energetiche basate su underscore/sottostringhe. | `OutputConfig` possiede pattern di discovery e riconoscimento dei range. Supportati prefissi, separatori, sottodirectory, timestamp e formati dei campi. Test 1.0GeV contro 11.0GeV e ordinamento di range multipli. |
| `variable_2d` accettato senza produrre output. | Rimossi configurazione, classe e ramo inutilizzati; opzione rifiutata con messaggio esplicito. Nessun uso nei YAML del progetto o dell'articolo. |
| `import src` richiedeva modifiche a `sys.path`. | Import relativi di package; funzionano API, `run_analysis.py` e `python3 -m src.analysis`. |
| Con meno di due istogrammi il confronto poteva dichiarare successo. | Errore propagato fino alla CLI, exit status 1, nessun nuovo PDF/Excel del confronto insufficiente. Con almeno due istogrammi validi restano warning per quelli mancanti. |
| File e canvas ROOT non sempre chiusi. | Ownership circoscritta con context manager, `ExitStack` e `finally`; verificati successo ed eccezioni. Errori di salvataggio macro propagati. |
| Durata totale nulla causava divisione per zero. | Media ed errore dei job paralleli a zero per durata non positiva. |
| Excel saltato senza `xlsxwriter` anche con `openpyxl` disponibile. | Selezione automatica del motore pandas. |
| PDF e macro salvati due volte. | Un salvataggio per formato. |

## Schema e semplificazioni

Unico formato YAML/JSON dei confronti, confermato dall'utente:

```yaml
comparisons:
  - output: comparison
    hists:
      - [file_a.root, histogram_a, Sample A, kP6Blue, 0]
      - [file_b.root, histogram_b, Sample B, kP6Yellow, 1]
```

Ogni riga contiene esattamente file, istogramma, etichetta, colore e ordine intero. `ComparisonConfig.from_dict` valida e normalizza le righe; `AnalysisConfig.from_file` carica le sezioni. I vecchi campi separati `files`, `labels`, `colors`, `legend_order`, `labels_and_colors` e `files_name*` sono rifiutati con indicazione di migrazione. Il costruttore Python mantiene le liste normalizzate usate internamente.

Esempi e README migrati; rimossi i due esempi dedicati esclusivamente ai formati obsoleti. Condivisi booking degli spettri, costruzione delle righe statistiche e risoluzione della destinazione dei confronti. Rimossi import inutilizzati, senza nuove dipendenze.

## Verifica finale

- **79 test superati in 10,21 secondi**, senza warning.
- `ruff check --isolated --no-cache --select E7,E9,F src tests run_analysis.py`: superato.
- Compilazione in memoria di sorgenti, entry point e test: superata, senza creare bytecode.
- Caricamento di tutti i **6 YAML** rimasti nel progetto: superato.
- `git diff --check`: pulito.
- Confronto AST rispetto allo snapshot precedente a questi fix: invariati `BoxSurfaceConfig`, filtri e booking scientifico in `core.py`, `_smooth_hist_logspace` e `_build_smoothed_clone`.
- Review indipendente finale: risolti entrambi i rilievi sui template personalizzati; nessuna ulteriore regressione concreta nel perimetro approvato.

La suite include import da subprocess, CLI, warning EOT senza ricalcolo, schema obsoleto/invalido, resa ed errori ponderati, sei facce dei box, collisioni di nomi, autoscale, output personalizzati ROOT/PDF/macro/Excel e conteggi delle risorse ROOT su successo ed errore.

### Dati reali

Input letti da `/Users/tonyf/Work/BDX/2025-11-21_BDX_NeutronArticle`; durante la verifica iniziale nessun originale esterno modificato (migrazione successiva descritta sotto). Tutti gli output di verifica sono stati creati nella cartella temporanea del progetto.

Analisi GeometryC2prop eseguita prima e dopo questi fix su **10 file ROOT**, sette range energetici e due superfici. ROOT 6.40.04, un worker per confronto deterministico:

- EOT: **10.000.000** in entrambe le esecuzioni.
- **30 istogrammi**, **60 array di contenuti e Sumw2 esattamente uguali**, inclusi underflow/overflow.
- Metadati di titolo, entries e numero di bin esattamente uguali.

Confronti dell'articolo:

- Tutti i **10 YAML già canonici** eseguiti: PDF, macro ROOT ed Excel prodotti.
- I due originali legacy `ComparisonPlots/figure2/comparison_figure2_r1.yaml` e `comparison_figure2_r2.yaml` ora vengono rifiutati correttamente. **Successivamente migrati anche negli originali, su richiesta dell’utente; vedere sotto.**
- Migrazione delle sole copie temporanee: `r1` genera tutti e tre i formati; `r2` fallisce esplicitamente perché gli istogrammi `_log` richiesti sono assenti. Non produce un nuovo grafico o workbook fuorviante.
- Totale: **11 confronti riusciti**, un fallimento atteso per dati mancanti; nessun file/canvas ROOT aperto al termine di ciascun confronto.
- Sette configurazioni figure2 indicano la directory obsoleta `ComparisonPlots/simulation_results`; corretta soltanto nelle copie temporanee verso `ComparisonPlots/figure2_simulation_results`.
- Alcune configurazioni figure5 contengono indici `smooth_hists` fuori intervallo: warning già previsti, indici ignorati.

La prima fase della sessione aveva inoltre verificato equivalenza visiva di 41 PDF dopo il refactor puro. Tre figure5 cambiano dopo il fix dell'autoscale: scala Y corretta, dati invariati. Questa verifica storica non è stata ripetuta dopo gli ultimi fix; le prove finali sopra riguardano numeri, file prodotti, risorse e regressioni automatizzate.

## Scelte conservate e limiti

- Cache EOT: avviso soltanto, come richiesto; identità degli input non verificata automaticamente.
- Box: invariati limiti inclusivi, uguaglianza floating point delle facce e selezioni trasverse.
- Smoothing: sola visualizzazione, errori originali conservati; nessuna nuova propagazione delle incertezze.
- Collisioni: protezione entro una configurazione. Directory condivise tra configurazioni o esecuzioni separate mantengono la precedente semantica di sovrascrittura.
- Template senza entrambi i campi energetici non permettono di riconoscere il range; etichetta `unknown`.

## Pulizia e riproduzione

Rimossi gli artefatti della review precedente prima dei fix. Rimossi anche `tmp_validation/` e cache generate al termine; questo documento conserva risultati e limiti, senza collegamenti a log eliminati.

Dalla root del progetto, nell'ambiente ROOT/Python disponibile:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider --basetemp=/tmp/bdx-validation
ruff check --isolated --no-cache --select E7,E9,F src tests run_analysis.py
git diff --check
```

Per ripetere i confronti esterni, correggere in copie locali i percorsi figure2 ancora obsoleti; impostare esplicitamente `output_directory` di ogni confronto in una nuova cartella temporanea. I due YAML r1/r2 sono già migrati e hanno percorsi corretti.

## Migrazione degli originali esterni r1/r2

Su successiva richiesta dell’utente, modificati `ComparisonPlots/figure2/comparison_figure2_r1.yaml` e `comparison_figure2_r2.yaml`:

- Liste separate convertite in cinque righe `hists` da cinque campi. Etichette, colori, ordine, nomi degli istogrammi e impostazioni del grafico conservati.
- Percorsi di entrambi aggiornati da `simulation_results` a `figure2_simulation_results`; verificata presenza di tutti i file ROOT richiesti.
- Tutti i **12 YAML esterni** ora vengono caricati dal parser canonico.
- Test tramite entry point CLI su copie con output temporaneo: **r1 exit 0**, PDF/macro/Excel generati; **r2 exit 1 atteso**, cinque file aperti ma zero istogrammi richiesti disponibili, nessun output parziale.
- Test eseguiti con `ROOT.gROOT.SetBatch(True)`: il tentativo senza batch ha incontrato un abort nell’inizializzazione Cocoa nell’ambiente di esecuzione. Il rendering batch è riuscito; nessuna modifica al codice CLI.
- Gli originali scritti sono stati confrontati byte per byte con le versioni testate, poi ricaricati. Output e log temporanei eliminati dopo verifica.
