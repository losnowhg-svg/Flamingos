# Rapporto di verifica - versione 1.4

Data della verifica: 9 ottobre 2026.

## Eseguito: 12 test automatici Python, tutti superati

Comando: `python -m unittest discover -s tests -v`.

Verificati formato e dimensioni dei PNG, metadato sRGB, rendering nativo ad
alta risoluzione, antialias sui glifi, adattamento dei testi lunghi, alpha
compositing, coordinate non valide / non finite, segnalazioni di ritaglio,
caricamento di un font di sistema solo per il test, validazione dei loghi,
schema di importazione e rifiuto di archivi non validi.

Gli MP4 sono stati realmente scritti e riaperti con ImageIO/FFmpeg:
Starting 7 a 540 x 960 e 1080 x 1920; Matchday a 540 x 540, 1080 x 1080 e
1080 x 1920. I test automatici usano clip brevi, 3 frame a 12 FPS, per
verificare dimensioni, codec utilizzabile, lettura e conteggio dei frame.

## Eseguito: 6 controlli del componente in Chromium, tutti superati

Comando: `python tests/editor_smoke.py`.

- Frecce e Maiusc + frecce, con coordinate logiche corrette.
- Annulla/ripeti e selezione durante la simulazione dei rerun del server.
- Trascinamento con il puntatore indipendente dalla scala dell'anteprima.
- Guide di ritaglio, visibilita delle guide e zoom.
- Archivio non disponibile: messaggio Solo sessione, senza bloccare il caricamento.
- Rifiuto di un font non valido da parte del browser.

Il test usa iframe `srcdoc` in una pagina senza navigazione. Lo storage
IndexedDB reale non e accessibile in tale origine: viene verificato il
comportamento di errore, non la persistenza su disco.

## Altri controlli eseguiti

Sintassi Python verificata con `py_compile`. I due script JavaScript sono
stati verificati con `node --check`. PNG di entrambi i modelli sono stati
ispezionati visivamente. Entrambi i percorsi dell'interfaccia Python sono stati
eseguiti con un doppio minimale dell'API Streamlit per cercare errori di logica;
questo non sostituisce una prova con Streamlit reale.

## Non completato in questo ambiente

La dipendenza Streamlit non era installata; il tentativo di installazione e
fallito per assenza di accesso alla rete. Il browser ha rifiutato la navigazione
al server locale con `ERR_BLOCKED_BY_ADMINISTRATOR`.

Di conseguenza, non sono stati verificati end-to-end: avvio di Streamlit,
comunicazione componente/server nel deployment, persistenza IndexedDB dopo
chiusura e riapertura del browser, import/export del backup nel deployment,
Safari, Firefox, dispositivi mobili e Streamlit Community Cloud.

Il test riproducibile `tests/browser_smoke.py` e incluso ma **non risulta
superato qui**. E progettato per coprire caricamento, deduplicazione, salvataggio
progetti, reload, riapertura del browser, backup, rimozione e ripristino in un
ambiente che permetta un server HTTP locale.

Prima dell'uso operativo, apri l'app distribuita, carica un tuo font, attendi
Salvato su questo browser, salva un progetto e scarica un backup. Chiudi e
riapri il browser: verifica che font e progetto siano ancora selezionabili.
Non affidare l'unica copia dei file allo storage del browser.
