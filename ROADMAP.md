# Funzioni proposte per le prossime versioni

Queste proposte **non sono implementate nella 1.5**. La 1.5 include già Match
Result, preset, importazione dal Matchday, pacchetti PNG e didascalie.

## 1. Rosa stagionale e moduli tattici - priorità alta

Una scheda per giocatore con numero, nome, ruolo e disponibilità. La formazione
si compone selezionando sette giocatori, senza riscriverli a ogni partita.
I moduli ridistribuiscono le posizioni e mostrano chiaramente se il portiere
è incluso nella notazione. Una conferma separa il cambio di modulo dalla
sostituzione dei convocati.

Valore pratico: meno lavoro ripetitivo nella funzione Starting 7. La rosa
potrebbe inizialmente usare lo stesso archivio browser, senza nuovi servizi.

## 2. Calendario partite condiviso - priorità alta

Un record unico per partita con avversario, casa/trasferta, data, ora, campo,
giornata e competizione. Starting 7, Matchday e Match Result leggono lo stesso
record, mantenendo ciascuno il proprio stile. Duplicazione della giornata
precedente e segnalazione dei campi ancora da compilare.

Valore pratico: evita incongruenze tra le grafiche della stessa partita.
L'inserimento iniziale può restare manuale; non serve una fonte esterna di risultati.

## 3. Sponsor e partner - priorità medio-alta

Una fascia sponsor facoltativa, con più loghi, dimensioni massime e distanza dal
bordo gestite per formato. Scelta tra sponsor stagionali e sponsor della singola
partita, senza inserire elementi fissi nella fotografia CRT.

Valore pratico: uniformità delle pubblicazioni e meno correzioni manuali.
Usare soltanto loghi autorizzati, senza rendere pubblico l'archivio personale.

## 4. Riepilogo mensile - priorità media

Dai risultati salvati, generare una grafica con partite, gol fatti/subiti e
marcatori del periodo. Prima occorre strutturare le marcature: i testi liberi
attuali non bastano per calcolare statistiche affidabili. Definire separatamente
amichevoli, annullamenti, risultati a tavolino e serie dei rigori.

## 5. Bozze automatiche e sincronizzazione - fase successiva

Prima introdurre un recupero delle bozze locale distinto dal pulsante Salva,
con una chiara indicazione dell'ultima scrittura riuscita. La sincronizzazione
tra dispositivi richiede invece identità, autorizzazioni, archiviazione remota e
politiche per i file/font caricati: non equivale al semplice uso di IndexedDB.
Non aggiungere un cloud condiviso implicitamente a un'app pubblica.

Ordine suggerito: rosa stagionale, calendario condiviso, sponsor. Sono le
aggiunte che riducono più direttamente il lavoro ripetuto durante la stagione.
