# Flamingos Studio 1.4

Editor Python / Streamlit per Starting 7 e Matchday Screen CRT.
Questa versione corregge il rendering a bassa risoluzione e aggiunge un archivio
browser per font, stemmi e progetti. Non richiede API AI o servizi a pagamento.

## Avvio e aggiornamento

Serve Python 3.10 o successivo, con le dipendenze installate:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Per aggiornare il repository esistente, estrai lo ZIP e copia **tutto il contenuto**
nella radice del repository, mantenendo le sottocartelle e sovrascrivendo i file
omonimi. Il punto di ingresso resta `app.py`. Non basta sostituire solo `app.py`:
sono necessari anche `studio_ui.py`, `studio_state.py`, `library.py`,
`render_utils.py`, `library_frontend/index.html` e il nuovo `frontend/index.html`.
Mantieni entrambi i file nella cartella `assets`.

La cartella `.streamlit` contiene il tema. Nessuna credenziale da configurare.
Questo pacchetto non modifica da solo il repository o la distribuzione online.

## Cosa cambia nella grafica

La 1.3 disegnava a 540 x 960 e ingrandiva il risultato. In Starting 7 usava
NEAREST anche per l'esportazione finale: aumentavano i pixel, non il dettaglio.
In Matchday alcune righe di testo venivano ridimensionate con NEAREST anche
quando era selezionato un font non pixel.

La 1.4 mantiene le coordinate logiche 540 x 960, ma disegna caratteri, contorni,
cerchi e pannelli direttamente a risoluzione superiore. Il font viene ridotto
alla dimensione necessaria prima di essere rasterizzato, invece di comprimere
un'immagine di testo gia piccola. Le scritte multicolore condividono la baseline.
La composizione alfa e corretta e non applica due volte la trasparenza ai bordi.

- **PNG Fine**, predefinito: composizione a 2160 x 3840, ridotta con LANCZOS a
  1080 x 1920. Per il post Matchday il ritaglio finale e 1080 x 1080.
- **PNG Standard**: composizione nativa a 1080 px di larghezza, senza
  supersampling aggiuntivo; utile per ridurre il carico di elaborazione.
- **Editor**: immagini a 1080 px di larghezza, mostrate alle dimensioni disponibili.
- **Video**: rendering nativo a 540 o 1080 px; H.264, CRF 18, 12/15/24/30 FPS.
  La scelta predefinita e 1080 px / 24 FPS. Audio non incluso.

`Sans Bold` e il nuovo predefinito. `Monospace Bold` rimane disponibile.
`Pixel Arcade` e un effetto a blocchi intenzionale, da scegliere esplicitamente.
I font personalizzati mantengono maiuscole e minuscole. Nessun file di font di
sistema e distribuito con questo progetto: vengono cercati sul computer che
esegue l'app; in mancanza, Pillow offre il proprio font incorporato scalabile.
Un file personale caricato garantisce la stessa scelta tipografica sui server.

La fotografia CRT originale e 945 x 945: il nuovo renderer non inventa dettagli
mancanti nella foto o in loghi piccoli. Per giudicare le scritte apri il PNG
scaricato al 100%, non uno screenshot dell'anteprima ridotta.

## Caricare e conservare un font

1. Apri **Archivio font, stemmi e backup** nella barra laterale.
2. Premi **+ Font TTF / OTF** e carica il file, massimo 5 MB.
3. Attendi la conferma **Salvato su questo browser**.
4. In **Font e tipografia > Carattere**, seleziona `Salvato: nome del file`.

I file vengono archiviati in **IndexedDB del browser**, con deduplicazione del
contenuto. Sono disponibili in entrambi i modelli senza doverli ricaricare.
La libreria ammette 24 file complessivi e 32 MB; gli stemmi possono occupare
fino a 12 MB ciascuno, nei formati PNG, JPEG e WebP, massimo 20 megapixel.

Il salvataggio riguarda **lo stesso browser, profilo, sito e dispositivo**.
Non e una libreria cloud e non si sincronizza fra telefono e computer.
Cancellare i dati del sito, cambiare indirizzo dell'app o usare una sessione
privata puo rendere i dati indisponibili. Anche i criteri di spazio del browser
possono rimuovere archivi non protetti.

Il pulsante **Richiedi conservazione al browser** usa la Storage API: il browser
puo accettare o rifiutare. Non sostituisce un backup. Se IndexedDB e bloccato o
la scrittura fallisce, l'app segnala **Solo sessione / Non salvato** e non finge
che il file sia stato conservato.

I file dell'archivio vengono trasmessi alla sessione dell'app e validati in
Python per poter generare PNG e MP4. Non sono pubblicati nel repository ne
scritti in una libreria condivisa sul disco del server; possono rimanere nelle
cache in memoria del processo. Non caricare font che non puoi usare per questo
scopo. Il backup contiene i font originali caricati: condividilo solo quando
la licenza lo consente.

## Progetti e backup

**Salva progetto nel browser**, sotto l'editor, conserva testi, colori,
coordinate, giocatori, formato, impostazioni di export e riferimenti a font e
stemmi presenti nell'archivio. Lo stesso nome, nello stesso modello, aggiorna
il progetto precedente. Il limite e 50 progetti.

**Il progetto non viene salvato automaticamente.** Le modifiche non salvate
rimangono solo nella sessione. Per riaprirlo usa **Progetti salvati** sopra
l'editor. Passando fra i modelli durante la stessa sessione, i controlli di
ciascuno mantengono i valori inseriti.

**Scarica backup** genera un JSON con tutti i font caricati, gli stemmi e i
progetti salvati. I PNG e gli MP4 non sono inclusi. **Importa backup** unisce i
dati alla libreria del browser e chiede conferma: i progetti con lo stesso
identificativo vengono aggiornati. Il decoder ricontrolla i file prima dell'uso.

Se rimuovi un font o uno stemma ancora usato da un progetto, il progetto non
puo ricostruirlo da solo: reimporta il backup o scegli un sostituto. Per un font
mancante l'app segnala il fallback. L'archivio e personale al browser, non un
sistema di autenticazione o collaborazione fra utenti.

## Editor

Trascina gli elementi o usa le coordinate numeriche. Dopo aver selezionato un
elemento, le frecce lo spostano di 1 unita logica, Maiusc + frecce di 10.
Sono disponibili annulla/ripeti, anche con Ctrl/Cmd + Z e Ctrl/Cmd + Maiusc + Z.
La cronologia dell'editor non viene conservata quando il componente si chiude.

Le guide centrali, l'aggancio agli assi, i margini indicativi e il ritaglio
quadrato aiutano a comporre il layout. **Le guide non vengono esportate.**
I margini non sono una garanzia di compatibilita con tutte le interfacce social.
Lo zoom ingrandisce l'area di lavoro senza modificare la posizione degli elementi.

L'app segnala elementi fuori dal formato di esportazione e numeri di maglia
duplicati. In Matchday, Post 1:1 resta un ritaglio centrale della Story:
non e ancora un'impaginazione indipendente. I dati iniziali sono segnaposto,
non una partita realmente annunciata.

## Verifiche e limiti della consegna

Vedi `TEST_REPORT.md` per risultati e limiti effettivi. Il motore PNG / MP4 e
stato eseguito e verificato. I comandi dell'editor sono stati verificati in
Chromium con un harness senza rete. Il test completo di persistenza reale e
l'integrazione Streamlit non sono stati completati in questo ambiente:
l'installazione della dipendenza e la navigazione al server locale erano
bloccate. Non e una certificazione della distribuzione su Streamlit Cloud.

Test del renderer e dello schema, con le dipendenze dell'app:

```bash
python -m unittest discover -s tests -v
```

Test browser opzionali, con Playwright e Chromium installati:

```bash
python tests/editor_smoke.py
python tests/browser_smoke.py
```

Il secondo test usa un server HTTP locale e una directory browser temporanea;
controlla ricaricamento, riapertura del browser, import/export e cancellazione.
Non conserva i font usati nel test o i profili del browser.

Il rendering Full HD richiede piu memoria e CPU della modalita 540 px. In caso
di limiti del server scegli PNG Standard o video 540 px. Il progetto non
introduce account, database remoti o costi di servizio.

## Documentazione tecnica di riferimento

- Pillow ImageFont: https://pillow.readthedocs.io/en/stable/reference/ImageFont.html
- Streamlit componenti bidirezionali v1: https://docs.streamlit.io/develop/concepts/custom-components/components-v1/intro
- MDN, limiti e conservazione dello storage: https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria

Le proposte per nuove sezioni, distinte da quanto gia realizzato, sono in
`ROADMAP.md`.
