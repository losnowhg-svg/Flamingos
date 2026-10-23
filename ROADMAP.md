# Flamingos Studio - dopo la 1.6

## Gia realizzato

Starting 7, Matchday Screen, Full Time e Convocati; sei preset CRT a oggetti,
rotazione per giornata, due caratteri pixel integrati; archivio font / stemmi,
progetti e backup browser; editor trascinabile; PNG HD e MP4; formati quadrato,
4:5 e Story per i modelli CRT.

Dalla 1.6: undici preset con luminosita regolabile per Instagram, editor
Classifica con import da link o copia-incolla, sequenze video con sei
transizioni CRT, Partita della settimana condivisa e kit partita in ZIP.

Dalla 1.9: mockup su televisore a tubo (PNG, video e sequenze con manopola che
gira), animazioni Retro (scrittura, glitch, contatore, righe, accensione) e temi
per eventi e stagioni con scelta automatica.

## Idee successive, non incluse in questa consegna

Un editor Player of the Match con foto e statistiche; risultati della giornata
del girone; GOL in diretta, pagelle, figurine; diario della stagione con backup; layout indipendenti per ogni rapporto;
transizioni anche nel video del singolo editor; salvataggio della Partita della
settimana nell'archivio browser.

Pubblicazione programmata, sincronizzazione cloud, gestione utenti e importazione
automatica dei risultati richiederebbero integrazioni separate. Questa versione
non le attiva e non collega l'account Instagram.

## Prima del deploy

Eseguire il test AppTest con Streamlit installato e la suite browser su un'origine
HTTP consentita, inclusa la persistenza dopo la chiusura del browser. Verificare
anche Safari / iOS e la memoria disponibile sul server di destinazione.
