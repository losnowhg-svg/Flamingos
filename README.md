# Flamingos Studio 1.5

Editor Python / Streamlit per **Starting 7**, **Matchday Screen** e **Match Result**.
Otto preset stagionali, editor visuale, PNG e MP4. Nessuna API AI, credenziale o
nuova dipendenza di produzione rispetto alla versione 1.4.

Questa consegna contiene i sorgenti aggiornati: non modifica automaticamente
il repository GitHub o il sito Streamlit già pubblicato. Risultati e limiti delle
verifiche sono documentati in `TEST_REPORT.md`.

## Avvio

Python 3.10 o successivo, con le dipendenze del progetto:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

Il punto di ingresso resta **app.py**. Il nuovo editor riutilizza il motore di
rendering e i due componenti browser della 1.4. I renderer sono stati verificati
qui con Python 3.13.5; la matrice completa di versioni Python/Streamlit non è
stata verificata. Il workflow incluso usa Python 3.11.

## Aggiornare il repository e la versione pubblica

1. Nella vecchia app scarica prima il backup da **Archivio font, stemmi e backup**.
2. Estrai lo ZIP e copia **tutto il contenuto nella radice del repository**,
   mantenendo `assets`, `frontend`, `library_frontend` e `.streamlit`.
   Non sostituire soltanto `app.py`. Non cancellare eventuali configurazioni o
   segreti personali presenti nel tuo repository.
3. Esegui i test, preferibilmente in un branch di prova, quindi integra il branch
   collegato alla distribuzione Streamlit. Il file principale resta `app.py`.

I moduli nuovi necessari sono `match_result_renderer.py`, `presets.py`,
`scene_styles.py` e `studio_tools.py`; anche gli altri moduli Python e i due HTML
sono aggiornati. `.github/workflows/tests.yml` aggiunge una verifica automatica
su push e pull request, quando GitHub Actions è abilitato nel repository.
Il workflow è fornito, ma non è stato eseguito sul tuo repository.

Streamlit Community Cloud usa il repository/branch configurato come sorgente;
le modifiche alle dipendenze provocano una nuova installazione. Se qualcosa non
parte, controlla i log in **Manage app**, non soltanto la schermata pubblica.
I riferimenti ufficiali sono riportati in fondo a questo documento.

Il nome del componente archivio, il database e lo schema 1 sono mantenuti.
La 1.5 accetta i backup della 1.4; non è garantito il percorso inverso per i nuovi
progetti Match Result. Mantieni lo stesso indirizzo dell'app per ritrovare i dati
locali, e conserva comunque un backup. La persistenza effettiva sulla tua
istanza pubblica va verificata dopo l'aggiornamento.

## Come usare l'interfaccia

La barra laterale contiene la scelta del modello e l'archivio, chiuso inizialmente
per lasciare spazio ai contenuti. Il lavoro è diviso in tre schede:

**Crea la grafica**: compila i contenuti a sinistra e sistema la composizione
nell'editor a destra. Palette, font, stemmi e coordinate precise sono raccolti
in sezioni espandibili. Il formato del Match Result si sceglie sopra l'editor.

**Esporta e pubblica**: genera i PNG, i pacchetti multiformato e i video; prepara
la didascalia. Non avviene alcuna pubblicazione automatica sui social.

**Progetti**: riapri, salva o duplica una grafica. Il salvataggio non è automatico.
Un nome già presente nello stesso modello aggiorna il progetto; **Salva come nuova
copia** crea un identificativo e un nome distinti.

Il tema usa testi chiari, etichette più marcate, bordi visibili e meno controlli
aperti contemporaneamente. Non viene dichiarata una certificazione di
accessibilità o una verifica completa su tutti i dispositivi.

## Match Result

Il modello include punteggi casa/ospiti da 0 a 99, nomi e stemmi, titolo, data,
competizione, giornata, marcatori, MVP e testo inferiore. I blocchi marcatori e
MVP vuoti non vengono disegnati.

Lo stato può essere **FINALE**, **INTERVALLO**, **DOPO SUPPLEMENTARI** oppure
**DOPO I RIGORI**. Indica se la tua squadra gioca in casa o in trasferta:
l'esito vittoria/pareggio/sconfitta segue quella scelta, non sempre la squadra
a sinistra. All'intervallo non viene presentata una vittoria definitiva.

Per i rigori, il punteggio grande resta quello prima della serie; i due campi
aggiuntivi descrivono il solo risultato dei rigori. L'app segnala dati incoerenti,
ma non impedisce di esportare una bozza.

**Marcatori**: una riga per giocatore, per esempio `Rossi 12', 47'`.
La grafica mostra al massimo sei righe per squadra, fino a 80 caratteri per riga.
I testi vengono ridotti per entrare nello spazio disponibile. In caso di eccesso,
un avviso segnala che occorre raggruppare le marcature; la didascalia conserva
anche le righe non entrate nella grafica. Le marcature sono testo libero e non
vengono confrontate automaticamente con il totale dei gol.

### Tre impaginazioni, non tre ritagli

| Formato Match Result | PNG finale | Coordinate logiche |
| --- | --- | --- |
| Story 9:16 | 1080 x 1920 | 540 x 960 |
| Post 4:5 | 1080 x 1350 | 540 x 675 |
| Post 1:1 | 1080 x 1080 | 540 x 540 |

Ogni formato ha posizioni iniziali dedicate. Passando da un formato all'altro
vengono conservati gli spostamenti già fatti in ciascuno. Questa memoria fa parte
del progetto salvato. Contenuti, dimensioni dei font e palette restano condivisi;
le dimensioni massime dei loghi e del punteggio si adattano al formato.

Starting 7 mantiene la Story. Matchday conserva Story e post quadrato, ancora
come ritaglio centrale del layout originale. Non viene promesso un layout 4:5
per questi due modelli.

### Da Matchday a Match Result

Nel nuovo modello apri **Riparti dai dati del Matchday**. Puoi scegliere il
Matchday della sessione corrente oppure un suo progetto salvato. L'importazione
copia squadre, data, competizione, giornata, font, stemmi e palette; azzera
punteggio, marcatori e MVP e ripristina i layout del risultato. Richiede una
conferma esplicita per evitare di sostituire accidentalmente il lavoro corrente.

## Preset stagionali

| Preset | Uso suggerito | Motivo |
| --- | --- | --- |
| Flamingos Original | Identità di squadra | Pulito; CRT nel Matchday |
| Kickoff Bold | Avvio stagione e presentazioni | Diagonali |
| Neon Night | Partite serali | Griglia |
| Autumn Copper | Giornate autunnali | Fasce |
| Winter Ice | Inverno e ripresa | Orbita |
| Spring Mint | Primavera e ritorno | Diagonali |
| Derby Contrast | Derby e sfide speciali | Fasce |
| Final Gold | Ultime giornate e finali | Coriandoli |

I preset sono disponibili in tutti e tre i modelli. Cambiano palette, pannelli e
atmosfera, senza riscrivere nomi, risultato, giocatori, font, stemmi o posizioni.
Scegli il preset e premi **Applica preset**; la semplice selezione nel menu non
lo applica. **Annulla preset** ripristina l'ultimo stile precedente, senza perdere
contenuti modificati nel frattempo. Questa azione non è una cronologia illimitata.

Nel Matchday rimane disponibile la fotografia **CRT originale**. Gli altri
preset usano **Studio grafico**, un fondale generato dal renderer. I controlli
sfondo/pannelli/motivo non ricolorano la fotografia CRT: questa distinzione è
indicata anche nell'interfaccia.

## Editor visuale

Trascina un elemento oppure selezionalo dal menu, utile quando gli elementi si
sovrappongono. Le frecce spostano di una unità logica, Maiusc + frecce di dieci.
**Centra X** allinea il centro dell'elemento all'asse verticale della composizione.
**Blocca/Sblocca** impedisce spostamenti accidentali; il blocco è salvato nel
progetto e viene rispettato anche dai campi delle coordinate numeriche.

Annulla/ripeti, guide, aggancio agli assi e zoom restano disponibili. La
cronologia annulla/ripeti riguarda le posizioni e dura finché il componente resta
aperto: cambiare modello, applicare preset o caricare un progetto può ricrearlo.
La cronologia non è salvata nel backup. Le guide non vengono esportate e i margini
sono indicativi, non una garanzia rispetto a tutte le interfacce social.

**Ripristina layout e sblocca livelli** agisce sul formato corrente. Nel Match
Result non cancella i layout degli altri formati.

## Export e prestazioni

L'editor usa immagini di lavoro a 1080 px di larghezza. Il PNG finale viene
calcolato soltanto premendo **Genera / aggiorna PNG**: non viene ricreato in
supersampling a ogni trascinamento.

**PNG Fine**: composizione a 2160 px di larghezza, riduzione LANCZOS a 1080.
**PNG Standard**: composizione direttamente a 1080. I testi sono rasterizzati
alla risoluzione di lavoro; `Pixel Arcade` resta un effetto volutamente a blocchi.
Font di sistema mancanti possono produrre un fallback: carica un tuo font
licenziato per ottenere lo stesso carattere su server differenti.

Quando cambiano dati o stile, i download precedenti non vengono presentati come
aggiornati: occorre rigenerarli. Spostamenti e cambi di font sono inclusi nel
controllo; bloccare un livello non rende obsoleto un PNG identico.

**Pacchetto ZIP**: tre PNG per Match Result, due per Matchday, con un `LEGGIMI.txt`
contenente eventuali avvisi. Vengono usati i layout salvati dei singoli formati,
o quelli iniziali se non sono stati modificati. Verifica ogni immagine prima
di pubblicarla: un layout personalizzato può comunque avere elementi tagliati.

**MP4**: H.264, CRF 18, 12/15/24/30 FPS, larghezza 1080 oppure 540; niente audio.
Il nuovo risultato anima anche punteggio, marcatori ed MVP. Nel solo post 4:5 a
540 px il file misura 540 x 676: l'ultima riga viene duplicata per avere un'altezza
pari compatibile con yuv420p. A 1080 px il 4:5 mantiene 1080 x 1350.

I file hanno nomi descrittivi con modello, squadre, data e formato. I caratteri
non adatti ai nomi dei file vengono normalizzati.

**Didascalia**: una bozza testuale viene costruita dai dati, senza API AI. Puoi
modificarla e scaricarla in TXT. Se cambi i dati di origine viene creata una
nuova bozza: le modifiche manuali non sono incluse nel progetto o nel backup;
scaricale separatamente. Nessun collegamento automatico a Instagram o altri
social è stato aggiunto.

## Archivio, privacy e compatibilità

Font TTF/OTF: massimo 5 MB. Stemmi PNG/JPEG/WebP: massimo 12 MB e 20 megapixel.
Archivio: 24 file, 32 MB complessivi, 50 progetti. I file sono validati prima
del rendering; le firme del contenuto consentono di deduplicarli.

L'archivio usa IndexedDB nello stesso browser, profilo, dispositivo e origine
del sito. Non aggiunge account, sincronizzazione cloud o collaborazione tra
utenti. Dati del sito cancellati, navigazione privata o spazio insufficiente
possono rendere l'archivio indisponibile. La richiesta di conservazione al browser
non sostituisce un backup. In assenza di storage, l'interfaccia segnala
**Solo sessione**, senza fingere un salvataggio permanente.

I file caricati vengono trasmessi alla sessione Python per il rendering e possono
restare in cache di memoria del processo. Non sono aggiunti al repository o a
una cartella condivisa sul server. I backup dell'utente contengono gli originali
caricati: vanno condivisi soltanto quando licenze e permessi lo consentono.
Questo pacchetto non distribuisce file di font di sistema.

## Test e anteprime

```bash
python -m unittest discover -s tests -v
```

Per i test browser opzionali:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tests/editor_smoke.py
python tests/editor_result_smoke.py
python tests/browser_smoke.py
```

`browser_smoke.py` richiede anche l'accesso a un server HTTP locale.
`test_streamlit_ui.py` usa Streamlit AppTest; i tre test vengono esplicitamente
saltati se Streamlit non è installato. I test dei componenti JavaScript non
sostituiscono una prova end-to-end della distribuzione Streamlit.

In `examples` trovi una tavola degli otto preset, tre PNG del risultato e un
backup dimostrativo importabile. Punteggi, avversari, date, marcatori e MVP sono
**dati di esempio, non una partita reale**. Le immagini sono output del renderer,
non screenshot della pagina Streamlit pubblicata.

Le funzionalità ancora proposte, distinte da quelle implementate, sono in
`ROADMAP.md`. Il riepilogo delle modifiche è in `CHANGELOG.md`.

## Riferimenti ufficiali consultati il 10 ottobre 2026

- Gestione degli aggiornamenti Community Cloud:
  `https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app`
- Dipendenze e organizzazione dei file:
  `https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies`
- Componenti bidirezionali v1:
  `https://docs.streamlit.io/develop/concepts/custom-components/components-v1/intro`
- Streamlit AppTest:
  `https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest`


## Caricamento semplice da macOS / GitHub web

Questa edizione dello ZIP non contiene cartelle o file nascosti. Estrai lo ZIP e trascina su GitHub tutti i file e le cartelle estratti. Non caricare direttamente il file ZIP: GitHub non lo decomprime. Il file .streamlit/config.toml originale conteneva soltanto preferenze opzionali (tema, upload massimo e telemetria); il tema principale dell app e gia applicato da app.py. Su Streamlit Cloud puoi avviare normalmente app.py.
