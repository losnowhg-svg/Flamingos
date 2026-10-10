# Rapporto di verifica - Flamingos Studio 1.5

Data: 10 ottobre 2026. Sorgente iniziale: `flamingos_studio_v1_4.zip` fornito
dall'utente. Nessun accesso in scrittura al repository o alla distribuzione.

## Risultato sintetico

| Verifica | Esito locale |
| --- | --- |
| Compilazione di tutti i moduli Python | Superata |
| Suite unittest: rendering/schema originali | 12 superati |
| Suite unittest: Match Result e flussi 1.5 | 20 superati |
| Integrazione Streamlit AppTest | 3 saltati: dipendenza assente |
| Browser editor originale/fallback archivio | 6 scenari superati |
| Browser editor risultato/protocollo progetti | 7 scenari superati |
| Persistenza reale IndexedDB via server locale | Non completata: navigazione bloccata |
| Distribuzione pubblica Streamlit | Non eseguita e non verificata |

La suite unittest individua **35 test: 32 superati, 3 esplicitamente saltati**.
Un test saltato non viene presentato come una verifica superata. I tredici
scenari browser sono test dei componenti in un harness offline, non tredici
sessioni complete dell'app Streamlit.

## Ambiente effettivo

Python 3.13.5; Pillow 12.3.0; NumPy 2.3.5; imageio 2.37.3;
imageio-ffmpeg 0.6.0; Playwright 1.57.0; Chromium di sistema.
Streamlit non era installato. Il tentativo di installarlo con pip è fallito
per il blocco di rete / risoluzione DNS dell'ambiente.

## Cosa è stato eseguito

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
python tests/editor_smoke.py
python tests/editor_result_smoke.py
```

La verifica dei renderer comprende dimensioni e profilo dei PNG, supersampling,
font personalizzati disponibili nell'ambiente, composizione alfa e validazione
stemmi. I controlli 1.4 sono rimasti superati.

Per il risultato sono stati prodotti PNG Story 1080 x 1920, 4:5 1080 x 1350 e
quadrati 1080 x 1080. Sono stati controllati punteggi fino a 99, nomi lunghi,
sei righe di marcatori, campi opzionali, esito casa/trasferta, intervallo e rigori.
Le immagini di esempio dei tre formati e la tavola degli otto preset sono state
aperte per ispezione visiva; non sono screenshot dell'interfaccia Streamlit.

Sono stati codificati e riletti MP4 nei tre formati a 540 px, incluso il padding
675 -> 676 nel 4:5, e un 4:5 Full HD a 1080 x 1350. I test di codifica usano clip
brevi; il completamento dell'animazione viene verificato separatamente sul
fotogramma a quattro secondi. Non è stato misurato il tempo di rendering sul
server pubblico, né il comportamento con molti utenti simultanei.

Ogni preset ha prodotto un'immagine distinta in ciascuno dei tre modelli.
I test verificano che l'applicazione non muti testi, giocatori, punteggi, font,
stemmi o coordinate. Sono verificati anche la memoria delle posizioni per
formato, la compatibilità dello schema 1, il trasferimento dei dati dal Matchday,
le firme dei file esportati e i tre PNG nel pacchetto ZIP.

I test Chromium del nuovo editor verificano rapporto del canvas, menu livelli,
movimenti da tastiera, blocco di tastiera e trascinamento, centratura,
annulla/ripeti e adattamento a una larghezza ridotta. Il protocollo browser
accetta un progetto Match Result con posizioni e blocchi e unisce un backup
legacy. Un backup non supportato viene rifiutato senza sostituire i dati.

Nell'harness `srcdoc`, IndexedDB non è disponibile: sono stati verificati il
fallback e l'assenza di una falsa conferma di salvataggio permanente. Questa
prova **non verifica** la persistenza su disco tra due avvii del browser.

## Verifiche bloccate e limiti

Il test `tests/browser_smoke.py` è stato tentato, ma Chromium ha bloccato la
navigazione al server HTTP locale con `ERR_BLOCKED_BY_ADMINISTRATOR`. Nessuna
conclusione positiva viene quindi attribuita alla persistenza reale, alla
riapertura del browser o al backup scaricato in quel test.

I tre test `tests/test_streamlit_ui.py` sono pronti per verificare i modelli,
il passaggio preset/formati, l'esportazione PNG e l'importazione dal Matchday
con il vero AppTest. Non sono stati eseguiti qui. Il workflow GitHub incluso
installa Streamlit e Playwright e avvia la suite; va eseguito nel repository
prima di considerare verificata l'integrazione completa.

Non sono stati verificati Safari, Firefox, un telefono fisico, un audit di
accessibilità, font dell'utente non inclusi nell'allegato, carichi multiutente o
compatibilità con ogni versione ammessa dalle dipendenze. Il motore può ridurre
font e loghi per adattarli al formato; una foto o uno stemma piccolo non
acquisisce dettagli nuovi grazie al supersampling.

## Controllo consigliato prima di sostituire la versione pubblica

Aprire un backup reale della 1.4 su un'istanza di prova, salvare un Match Result,
ricaricare la pagina e riaprire il browser. Cambiare formato e verificare le
posizioni; applicare un preset e controllare che i dati restino invariati.
Esportare un PNG e un video, poi leggere i log della distribuzione. Solo dopo
questa prova integrare nel branch collegato alla versione pubblica.
