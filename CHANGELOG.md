# Changelog

## 1.5 - 10 ottobre 2026

### Aggiunto

- Modello Match Result: gol, stato partita, rigori separati, esito dal punto di
  vista della propria squadra, marcatori casa/ospiti, MVP e metadati.
- Layout dedicati Story, post 4:5 e quadrato; posizioni ricordate per formato.
- Otto preset stagionali condivisi dai tre modelli, con annullamento dell'ultimo
  cambio di stile senza ripristinare dati sportivi vecchi.
- Sfondi grafici alternativi al CRT originale e personalizzazione dei pannelli.
- Blocco dei livelli, selezione dal menu e centratura orizzontale.
- Importazione dei dati dal Matchday della sessione o da un progetto salvato.
- Pacchetto PNG multiformato con avvisi, didascalia TXT e duplicazione progetti.
- Test del risultato, test AppTest opzionali, test browser del nuovo protocollo,
  workflow GitHub Actions e anteprime dimostrative.

### Migliorato

- Interfaccia divisa in creazione, export e progetti; barra laterale alleggerita.
- Contrasto, etichette, dimensione dei testi nei componenti e gerarchia visiva.
- PNG finale su richiesta, invece del supersampling a ogni interazione.
- Invalidazione dei download dopo modifiche, nomi dei file descrittivi e
  segnalazione di contenuti incompleti o tagliati.
- Controllo dei margini basato sull'altezza effettiva del formato.
- Conferma di salvataggio distinta tra scrittura nel browser e sola sessione.

### Mantenuto

Starting 7, Matchday CRT, PNG ad alta risoluzione, export MP4, caricamento font e
stemmi, backup JSON, schema archivio 1 e identificativo del componente archivio.
I backup della 1.4 vengono accettati dalla nuova versione. Le dipendenze di
produzione sono quelle già richieste dalla 1.4.

### Limiti noti

L'integrazione Streamlit completa e la persistenza reale IndexedDB non sono
state verificate in questo ambiente. Vedi `TEST_REPORT.md` per i risultati
misurati e le prove ancora necessarie. Questa consegna non esegue push o deploy.
