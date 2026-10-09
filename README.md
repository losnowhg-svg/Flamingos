# Flamingos Studio 1.3

App gratuita in Python e Streamlit per creare immagini e video per Instagram.
Ora include **Starting 7** (modulo 1-1-3-1) e **Matchday Screen CRT**.

## Matchday Screen

Il nuovo modello replica il look del vostro televisore retro: cornice CRT fotografica, griglia blu, font pixel, riquadri scuri, due stemmi, scritta VS gialla e pannello con orario/campo. La foto CRT e' stata ricavata da un'immagine fornita dai Flamingos: lo schermo e' stato ripulito e ridisegnato per consentire modifiche future.

Dal pannello laterale puoi:

- Scegliere **Starting 7** oppure **Matchday Screen**.
- Modificare titolo, data, nomi delle due squadre, orario, campo e le etichette inferiori.
- Caricare il logo Flamingos e quello avversario (PNG/JPG/JPEG).
- Regolare separatamente dimensioni e posizione dei due stemmi.
- Caricare qualsiasi font `.ttf` o `.otf` standard (fino a 5 MB), oppure selezionare Pixel Arcade o Monospace Bold.
- Cambiare dimensioni di titolo, nomi, informazione e VS, oltre ai colori rosa, ciano, giallo e bianco.
- Spostare trascinando data, titoli, stemmi, VS, nomi, orario e campo nell'editor visuale (posizioni X/Y anche manuali).
- Scaricare PNG in **1080 x 1080** per i post o **1080 x 1920** per le storie.
- Generare MP4 animato (H.264) quadrato oppure verticale, 540 px o 1080 px.

Le due esportazioni usano la stessa composizione. Per il post quadrato si utilizza la parte centrale dell'editor 9:16, in modo che il televisore risulti a tutto campo.

I dati iniziali sono segnaposto, **non** l'annuncio di una partita reale. Prima di pubblicare aggiorna data, avversario e indirizzo.

## Aggiorna il repository GitHub esistente

1. Scarica `flamingos_studio_v1_3.zip` ed estrai tutti i file.
2. Apri il repository GitHub `losnowhg-svg/Flamingos` (oppure il tuo repository personale).
3. Carica **tutti i file contenuti** nella cartella estratta mantenendo la struttura delle directory.
4. Sovrascrivi `app.py` e `README.md`. Lascia o sostituisci gli altri file preesistenti. Aggiungi i nuovi `matchday_renderer.py`, `matchday_ui.py` e `assets/matchday_crt.png`.
5. Premi **Commit changes**. Streamlit Community Cloud in genere aggiorna automaticamente l'app collegata dopo un commit sul ramo pubblicato.
6. Ricarica la pagina Streamlit e cerca la scelta `Starting 7 / Matchday Screen` in alto nella barra laterale.

**Se GitHub non mostra subito il caricamento multiplo**: sul repository apri `Add file` -> `Upload files`. Per ogni file esistente (es. `app.py`) puoi anche aprirlo e usare l'icona matita, ma caricare gli elementi estratti e' piu' rapido. La cartella `frontend` deve contenere `index.html`.

Il punto d'ingresso Streamlit rimane `app.py`. Non e' necessario creare un'altra app.

## Avvio da PC (opzionale)

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Note tecniche

- Rendering con Pillow, NumPy e ImageIO/FFmpeg; non usa API o crediti AI.
- Per un font proprietario, assicurati di possedere la licenza d'uso: la grafica esportata lo incorpora come immagine, ma il file del font non viene pubblicato con il progetto.
- I layout e i file caricati non vengono memorizzati permanentemente sul server; restano nella sessione. Scarica gli export prima di chiuderla.
- L'audio non e' incluso nell'MP4; puoi aggiungerlo su Instagram o CapCut.
- Il rendering Full HD richiede piu' risorse e potrebbe superare i limiti del servizio gratuito. In quel caso usa 540 px.
- L'interfaccia Streamlit e il trascinamento devono essere verificati nel tuo ambiente dopo l'aggiornamento. Il renderer PNG/MP4 e' stato verificato separatamente.
