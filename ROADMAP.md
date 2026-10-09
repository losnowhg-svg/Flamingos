# Proposte per le prossime sezioni

Queste sono proposte, non funzionalita gia incluse nella versione 1.4.
Priorita e complessita sono valutazioni di progetto, non preventivi.

## 1. Rosa e convocazioni - priorita alta

Una rosa riutilizzabile con nome, numero, ruolo e foto per ogni giocatore.
La formazione si costruisce selezionando dalla rosa, senza riscrivere i nomi.
Aggiungere panchina, convocati/non convocati e importazione CSV.
Le foto richiedono gestione dei ritagli, consenso all'uso e backup piu capienti.

## 2. Match Center e risultato finale - priorita alta

Una scheda partita con avversario, stemma, data, ora, campo e competizione.
Da quella scheda generare Matchday, Starting 7, risultato finale, marcatori
con minuto e migliore in campo. I dati si inseriscono una sola volta.
Prevedere stati bozza/pubblicato e conferma del punteggio per evitare errori.
Nessuna raccolta automatica di risultati esterni senza una fonte verificata.

## 3. Kit grafico della squadra - priorita alta

Profili di identita con palette, stemma, sponsor e font diversi per titoli,
nomi e informazioni. Preset Clean, Retro CRT e Matchday scuro, tutti con le
stesse informazioni ma gerarchie tipografiche adatte ai rispettivi stili.
La 1.4 ha gia l'archivio di font e loghi: manca ancora un profilo di squadra
che applichi automaticamente tutte queste scelte ai modelli.

## 4. Formati e pacchetto social - priorita medio-alta

Layout distinti per quadrato 1:1, verticale 4:5 e Story 9:16, invece di limitarsi
a ritagliare la stessa composizione. Un comando genera un pacchetto ZIP con
nomi ordinati per partita e formato. Aggiungere controlli per elementi fuori
area, testo troppo piccolo e contrasto prima di esportare.
Il riadattamento richiede regole per ciascun modello, non un semplice resize.

## 5. Archivio partite e calendario editoriale - priorita media

Una galleria di progetti con anteprima, filtri per stagione/avversario e
pulsante Duplica. Un calendario distingue bozze, contenuti pronti e pubblicati.
Il calendario interno non equivale alla pubblicazione automatica sui social:
quest'ultima richiederebbe un'integrazione autorizzata separata.

## 6. Video e collaborazione - fase successiva

Per il video: ordine di comparsa, durata delle scene, transizioni, confronto
rapido con l'immagine statica e traccia audio di cui si possiedono i diritti.
Per l'uso fra telefono, computer e piu persone: account, archivio remoto
privato, permessi e versioni dei progetti. La libreria IndexedDB della 1.4
non svolge queste funzioni e non deve essere presentata come sincronizzazione.

## Ordine consigliato

Rosa riutilizzabile e Match Center prima, kit grafico subito dopo. Sono le
funzioni che evitano piu inserimenti ripetuti e dati incoerenti. Successivamente
formati indipendenti e archivio visuale; collaborazione e video avanzato solo
quando servono davvero a piu persone o a una pubblicazione regolare.
