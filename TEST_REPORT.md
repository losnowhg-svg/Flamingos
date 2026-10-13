# Flamingos Studio 1.5 - verifiche della consegna

Verifiche eseguite il 13 ottobre 2026 sul codice incluso nel pacchetto.
I dati nei render di esempio sono dimostrativi.

## Eseguito con esito positivo

La suite di rendering e validazione comprende **27 test superati**: i 12 della
versione precedente e 15 nuovi. Il test aggiuntivo AppTest e opzionale e viene
saltato in assenza di Streamlit.

Sono stati verificati i 18 abbinamenti fra i tre editor CRT e i sei preset,
l'assenza di elementi tagliati nei layout iniziali, le dimensioni PNG, il profilo
sRGB, il rendering ad alta risoluzione e l'adattamento delle scritte. Sono stati
controllati il punteggio fino a due cifre per lato, l'esito casa / ospiti, i
rigori, la visibilita e la spaziatura di sei righe di marcatori, i convocati da
7 a 18, i giocatori nascosti ma non cancellati e le animazioni.

I due alfabeti pixel sono verificati a scala 1, 2 e 4, anche con accenti italiani,
righe multicolore, limiti di larghezza / altezza e pixel a maschera binaria. La
rotazione di 80 giornate, la conservazione dei dati al cambio preset, i limiti dei
nuovi campi, gli input non validi e l'importazione dei progetti 1.4 sono coperti.

Sono stati generati e riletti MP4 con FFmpeg: numero di fotogrammi, dimensioni e
FPS verificati. I nuovi casi includono 1080 x 1080, 1080 x 1350, 1080 x 1920 e
540 x 676 con padding del formato ridotto 4:5. Sono test brevi di esportazione,
non prove di carico prolungato su un server cloud.

Tutti i file Python sono stati compilati con `py_compile`. Il catalogo e i render
di esempio sono stati generati dal codice effettivo e ispezionati visivamente;
la spaziatura dei marcatori e stata corretta dopo questa ispezione.

## Componenti browser, Chromium senza rete

`tests/editor_smoke.py`: **6 controlli superati** su movimento da tastiera,
trascinamento, annulla / ripeti, guide, zoom, storage non disponibile e rifiuto
di un font non valido.

`tests/v15_browser_smoke.py`: **5 controlli superati** sui layer Full Time e
Convocati, annulla e guide 4:5, salvataggio in sessione dei nuovi tipi di progetto,
conservazione di font e preset, export e reimport del backup JSON.

Questi test usano il protocollo reale dei componenti in un iframe locale senza
rete. Il backup testato contiene progetti, non font copiati dal sistema.
**Non dimostrano persistenza di IndexedDB dopo la chiusura del browser.**

## Non verificato nell'ambiente di consegna

L'installazione di Streamlit non e riuscita per il blocco di rete / risoluzione
DNS dell'ambiente. Il test `test_streamlit_app.py` e quindi saltato; non e stato
avviato un server Streamlit completo. La navigazione Chromium a `127.0.0.1` e
stata bloccata con `ERR_BLOCKED_BY_ADMINISTRATOR`, impedendo il completamento
originario di `tests/browser_smoke.py` sulla persistenza reale.

Non sono stati verificati il deploy su Streamlit Cloud, Safari / iOS, profili
browser multipli o limiti di memoria di un server specifico. Non e stata
eseguita alcuna pubblicazione su Instagram.

## Riprodurre le verifiche

```bash
python -m pip install --upgrade -r requirements.txt
python -m unittest discover -s tests -v
python tests/editor_smoke.py
python tests/v15_browser_smoke.py
python tests/browser_smoke.py
```

I test browser richiedono Playwright e Chromium. Con Streamlit installato,
AppTest controlla anche il rendering dei widget delle quattro pagine.
L'ultimo test richiede un'origine HTTP locale accessibile.
