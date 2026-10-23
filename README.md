# Flamingos Studio 1.6

## Novita della 1.6

- **Grafiche piu luminose per Instagram.** Nuovo cursore *Luminosita per
  Instagram* (Palette e atmosfera, valore consigliato 55): schiarisce sfondo e
  cornice con una curva che apre le ombre, senza toccare i testi. La luminosita
  media del post e passata da circa 30 a 70-175 su 255 secondo il preset.
  I progetti salvati con la 1.5 ricevono automaticamente il valore 55; con 0
  ritrovi l'aspetto della 1.5.
- **11 preset davvero diversi.** I sei preset esistenti hanno ora sfondi propri
  (righe pastello, bande corallo, notte synthwave, carta millimetrata, prato a
  strisce) e si aggiungono cinque mondi nuovi: **VHS Play**, **Televideo**,
  **Pocket verde**, **Tabellone stadio** e **Poster riso** (il preset chiaro).
- **Classifica**, nuovo editor: la classifica del girone su qualsiasi preset,
  con la nostra squadra evidenziata, fino a 16 squadre, colonne complete
  (G V N P GF GS PT) o compatte (G, DR, PT). I dati si caricano dal link
  (Tuttocampo o simili), incollando la tabella copiata dal sito o a mano.
- **Sequenza video** con transizioni CRT: scegli da 2 a 5 grafiche in ordine
  (es. Matchday > Convocati) e tra una e l'altra *Cambio canale*, *Spegni e
  riaccendi*, *Glitch RGB*, *Riavvolgimento VHS*, *Rolling verticale* o *Taglio
  netto*. Anteprima a fotogrammi e MP4 in 1:1, 4:5 o 9:16.
- **Partita della settimana** nella barra laterale: avversario, casa/trasferta,
  data, giornata, orari, campo e stemma avversario si scrivono una volta e si
  applicano a tutti gli editor. Layout, colori e preset restano i tuoi.
- **Kit partita**: tutte le grafiche scelte in un file ZIP con un clic.

### La classifica dal link

Il link di Tuttocampo e gia inserito. *Aggiorna dal link* prova a leggere la
pagina dal server dell'app; alcuni siti bloccano le letture automatiche, quindi
la strada sempre valida e **Incolla la tabella**: apri la classifica, seleziona
la tabella dalla prima all'ultima squadra, copia e incolla. L'app riconosce da
sola l'ordine delle colonne (anche con una cella per riga o con la colonna
delle ultime partite) e segnala le righe in cui V + N + P non torna con G.
Controlla sempre i numeri nella scheda *Modifica a mano* prima di pubblicare.


Studio Python / Streamlit per le grafiche Instagram di una squadra di calcio a 7.
Quattro editor: **Matchday Screen, Starting 7, Full Time e Convocati**.
Questa versione aggiunge due editor, sei preset CRT e due caratteri pixel integrati.
Non richiede API AI, account aggiuntivi o servizi a pagamento.

## Aggiornare dalla 1.4

Estrai lo ZIP e sostituisci **tutto il contenuto del progetto**, mantenendo le
sottocartelle. Non basta cambiare `app.py`: servono anche i nuovi renderer,
`crt_presets.py`, `crt_common.py`, `pixel_fonts.py`, i frontend e gli asset.
Lo ZIP contiene i file direttamente nella radice, come quello della 1.4.
Il punto di ingresso resta `app.py`.

Prima di aggiornare, scarica un backup dall'archivio dell'app. Il database browser
mantiene nome e schema precedenti; i progetti e i backup 1.4 sono importabili.
Un backup con i nuovi modelli non e invece destinato alla vecchia app 1.4.

Servono Python 3.10 o successivo e le dipendenze aggiornate:

```bash
python -m pip install --upgrade -r requirements.txt
streamlit run app.py
```

Il requisito minimo Streamlit passa a 1.54. Le altre dipendenze rimangono Pillow,
NumPy, imageio e imageio-ffmpeg. Nessuna credenziale da configurare. Il pacchetto
contiene il codice aggiornato: non modifica automaticamente un repository o
un'app gia distribuita online.

## Gli editor

### Full Time

Il preset iniziale usa **lo stesso televisore originale del Matchday**. Il file
`assets/matchday_crt.png` non e stato sostituito. Sono modificabili titolo,
competizione / giornata, data, squadre, stemmi e punteggio da 0 a 99 per lato.

La scelta **La nostra squadra e: Casa / Ospiti** rende corretto l'esito automatico
Vittoria, Pareggio o Sconfitta anche in trasferta. L'esito puo essere nascosto.
Per una partita decisa ai rigori, inserisci il punteggio pari prima della serie e
i rigori realizzati: compare una riga separata `D.C.R.` e l'esito tiene conto
anche dei rigori. Se il punteggio di gioco non e pari, la riga dei rigori non viene
esportata e viene mostrato un avviso. Un pareggio nella serie viene segnalato.

I marcatori hanno due colonne indipendenti e possono essere nascosti. Usa al
massimo **6 righe per squadra**, per esempio:

```text
ROSSI 12', 38'
BIANCHI 26'
VERDI 51'
```

Le righe oltre la sesta sono segnalate e non vengono disegnate. I minuti e i nomi
sono testo libero: il punteggio non e calcolato dai marcatori. La dimensione viene
adattata allo spazio disponibile, con righe separate anche nel caso di 6 nomi.

**Riusa i dati degli altri editor** copia squadre, data, stemmi e lato della nostra
squadra dal Matchday aperto nella sessione. Non cambia punteggio e marcatori.
Prima di copiare dati da un progetto salvato, aprilo nell'editor Matchday.

### Convocati

Un editor distinto dalla formazione Starting 7: serve a pubblicare **l'elenco dei
convocati, compresa la panchina**, e le informazioni per la partita.

Gestisce da **7 a 18 giocatori**, con numero, nome, ruolo e capitano. I ruoli sono
P, D, C e A; `-` permette di non indicarlo. Un asterisco identifica il capitano.
Nella grafica compare una legenda. Ogni riga e trascinabile individualmente.
Ridurre il numero dei convocati nasconde le ultime righe senza cancellarne i dati.
Numeri duplicati, piu capitani e nomi vuoti vengono segnalati.

La testata include squadra, avversari e data; il pannello inferiore contiene
**ritrovo, calcio di inizio e campo / indirizzo**. I nomi iniziali sono segnaposto.

Puoi copiare i sette giocatori da Starting 7 senza cancellare i posti dall'ottavo
in poi, oppure copiare la partita dal Matchday. La copia usa i dati della sessione
corrente, non un progetto salvato che non e stato aperto. Il ritrovo resta da
compilare separatamente.

### Matchday Screen e Starting 7

Matchday mantiene squadre, stemmi, VS, data, orario, luogo e animazione. Ora usa
anche i nuovi preset, i due font e il formato Post 4:5. Nelle nuove grafiche il
font iniziale e CRT Terminal; i progetti 1.4 conservano la scelta salvata.

Starting 7 mantiene l'impaginazione sul campo, i sette giocatori e l'export Story.
Ha accesso ai nuovi font; i preset degli oggetti CRT si applicano invece a
Matchday, Full Time e Convocati, non sostituiscono il campo di Starting 7.

## Undici preset da alternare nella stagione

La sezione **Preset CRT e rotazione di stagione** offre:

| Preset | Oggetto e carattere visivo |
| --- | --- |
| TV CRT originale | Stesso televisore del Matchday, neon rosa e ghiaccio |
| Console portatile | Scocca lilla, croce direzionale, pulsanti pixel |
| Mixtape | Musicassetta, bobine e palette corallo |
| Arcade club | Cabinato, marquee, joystick e pulsanti |
| Save the game | Floppy disk turchese, etichetta e otturatore |
| Tactics board | Lavagna tattica, clip e magneti da calcio a 7 |
| VHS Play | Blu del videoregistratore, PLAY, contatore e tracking |
| Televideo | Pagina 101, mosaici e i quattro tasti colorati |
| Pocket verde | Console grigio chiaro, schermo a quattro verdi |
| Tabellone stadio | Tabellone in acciaio, LED ambra, riflettori e tifosi |
| Poster riso | Carta crema, retini e inchiostri sfalsati: il preset chiaro |

Le cinque nuove cornici sono pixel art originale disegnata dal renderer, non
semplici cambi di colore della tele. Tutte mantengono schermo scuro, neon e
scanline regolabili. Il catalogo visivo e incluso nell'app.

In **Manuale** scegli un preset o premi Preset successivo. In **Per giornata**
imposta il numero della giornata: 1 usa TV, 2 Console, 3 Mixtape, 4 Arcade,
5 Floppy, 6 Lavagna, 7 VHS, 8 Televideo, 9 Pocket, 10 Stadio, 11 Poster,
12 ricomincia da TV. Il numero arriva fino a 80. La giornata della Partita della
settimana aggiorna anche questo valore.
La rotazione e una regola di selezione grafica, **non un calendario di
pubblicazione automatica su Instagram**.

Il cambio di preset modifica cornice e palette, ma conserva testi, risultati,
rose, stemmi, font e coordinate. Per abbinare anche il carattere suggerito premi
**Abbina il font del preset**. Puoi poi personalizzare ogni colore. Un successivo
cambio di preset applichera la nuova palette. Preset, giornata e modalita di
rotazione sono salvati nel progetto.

## Due nuovi caratteri pixel

**CRT Terminal** usa un alfabeto monospaziato 5 x 7. **CRT Scoreboard** usa un
alfabeto separato compatto 3 x 5, con proporzioni allargate da tabellone. Entrambi
includono lettere, cifre, punteggiatura e accenti italiani; il testo viene portato
in maiuscolo. Simboli non supportati sono sostituiti da `?`.

Sono caratteri bitmap disegnati dal codice in `pixel_fonts.py`, non file TTF / OTF
scaricati o font di sistema distribuiti nel pacchetto. Funzionano senza rete e non
richiedono caricamenti. Restano disponibili Sans Bold, Monospace Bold, Pixel Arcade
e i font personali salvati nell'archivio. I font personali mantengono le minuscole.

Sans e Monospace cercano i font sul computer dell'app, con fallback incorporato
in Pillow. Il risultato di questi fallback puo variare tra sistemi; un font
personale caricato rende esplicita la scelta. Nessun file di font di sistema e
incluso nello ZIP.

## Editor ed esportazione

Trascina contenuti, stemmi e giocatori; cornice e pannelli restano nello sfondo.
Puoi usare coordinate numeriche, frecce, Maiusc + frecce, annulla / ripeti,
aggancio agli assi, guide e zoom. Le guide non vengono esportate. Le coordinate
logiche rimangono 540 x 960, anche nelle esportazioni ad alta risoluzione.

Per i tre editor CRT sono disponibili **Post 1:1 (1080 x 1080), Post 4:5
(1080 x 1350) e Story 9:16 (1080 x 1920)**. I Post sono ritagli centrali della
stessa composizione, non impaginazioni indipendenti. Tutti i layout iniziali
rientrano nel quadrato; spostamenti fuori formato generano avvisi. Starting 7
mantiene Story 9:16.

PNG Fine compone a 2160 px di larghezza e riduce a 1080 con antialias. PNG Standard
lavora direttamente a 1080, riduce il carico e puo dare un bordo pixel piu netto.
La cornice fotografica originale non acquisisce dettagli nuovi aumentando
l'esportazione. Apri il file scaricato al 100% per valutare le scritte.

L'export MP4 usa H.264 / CRF 18, senza audio, 12 / 15 / 24 / 30 FPS e 5-18 secondi
per i modelli CRT, 7-18 per Starting 7. Sono disponibili larghezza 1080 o 540.
Per l'MP4 ridotto 4:5 la misura e **540 x 676**, con una riga di bordo aggiunta per
avere dimensioni pari: il contenuto non viene stirato. A 1080 il 4:5 resta
esattamente 1080 x 1350. Il pulsante di download appare dopo la generazione.

Le animazioni fanno comparire i contenuti e una scansione CRT; non sono modelli
con effetti audio, montaggio di filmati o generazione AI.

## Archivio, progetti e backup

Font TTF / OTF (massimo 5 MB) e stemmi PNG / JPEG / WebP (massimo 12 MB e
20 megapixel) sono caricabili dall'archivio della barra laterale. Il limite e
24 file e 32 MB complessivi. I file vengono validati nel browser e dal renderer.

La libreria usa **IndexedDB dello stesso browser, profilo, sito e dispositivo**.
Non e cloud e non sincronizza telefono e computer. I file raggiungono la sessione
Python per essere renderizzati e possono rimanere nelle cache in memoria; non
vengono aggiunti al repository o a una libreria pubblica sul server.

**Salva progetto nel browser**, sotto l'editor, conserva la grafica corrente; lo
stesso nome nello stesso modello aggiorna il progetto. Il limite e 50 progetti.
Non c'e salvataggio automatico. Passare da un editor all'altro nella sessione
conserva i dati, ma chiudere una sessione senza salvare puo perderli.

**Scarica backup** crea un JSON con file e progetti, non con i PNG o gli MP4.
**Importa backup** unisce l'archivio chiedendo conferma. I riferimenti a file mancanti
mostrano un avviso e usano un sostituto: il progetto non ricrea un font rimosso.
Condividi i font personali nei backup solo quando la loro licenza lo permette.

Il cambio di indirizzo dell'app, la cancellazione dei dati del sito e le sessioni
private possono rendere indisponibile la libreria. La richiesta di conservazione
al browser non sostituisce un backup. Se lo storage e bloccato, l'app segnala
**Solo sessione / Non salvato**, senza dichiarare una persistenza che non c'e.

## Verifiche

**1.6:** 47 test automatici (`tests/test_v16.py` piu quelli della 1.5) passano:
undici preset distinti tra loro, luminosita superiore a 55 su ogni preset,
lettura della classifica da quattro formati diversi, classifica senza tagli in
ogni preset fino a 16 squadre, partita condivisa in casa e trasferta, tutte le
transizioni e un MP4 di sequenza. Tutte le pagine sono state eseguite con un
sostituto di Streamlit, pulsanti compresi. Non sono stati verificati in questo
ambiente l'avvio del server Streamlit reale e la lettura del link Tuttocampo,
che il sandbox di sviluppo non poteva raggiungere.

I risultati effettivi e i limiti dell'ambiente sono in `TEST_REPORT.md`.
Il rendering, i nuovi schemi e i protocolli dei componenti sono stati verificati.
L'avvio completo del server Streamlit e la persistenza reale di IndexedDB non
sono stati verificati in questo ambiente: installazione di Streamlit e accesso
browser al server locale erano bloccati. Non e una certificazione del deploy.

```bash
python -m unittest discover -s tests -v
python tests/editor_smoke.py
python tests/v15_browser_smoke.py
python tests/browser_smoke.py
```

I test browser richiedono Playwright e Chromium; l'ultimo richiede anche accesso
a un server HTTP locale. Il test AppTest viene saltato se Streamlit non e presente.
I test non distribuiscono o conservano font di sistema nei file di progetto.

Per ricostruire il catalogo dai renderer:

```bash
python tools/build_previews.py
```

I contenuti del catalogo sono esempi dimostrativi, non partite o risultati reali.
Le dipendenze API sono documentate dalle fonti primarie:

- Streamlit: https://docs.streamlit.io/develop/api-reference
- AppTest: https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest
- Pillow: https://pillow.readthedocs.io/en/stable/reference/Image.html
- Storage browser: https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria
