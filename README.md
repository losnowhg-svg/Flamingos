# Flamingos Studio 1.2

Generatore di grafiche e video *Starting 7* per Instagram, con editor a trascinamento. Scritto in Python + Streamlit, senza servizi AI a pagamento.

## Cosa puoi modificare

- Carica il **logo** personalizzato (PNG/JPG). Rimozione opzionale dello sfondo bianco.
- Carica un **font TTF oppure OTF**, fino a 5 MB. Seleziona `Font caricato` per usarlo nei titoli, nomi, numeri e footer. Anche il file finale usa il font scelto.
- Cambia tutte le **scritte, i nomi e i numeri dei 7 giocatori**.
- Trascina **logo, quattro scritte e sette giocatori** direttamente sull'anteprima. Trascinamento utilizzabile anche da touch. Con le coordinate X/Y puoi ottenere posizioni precise.
- Personalizza le **dimensioni di logo e testo** e tutti i colori principali.
- Scarica **PNG 1080 x 1920** (fotogramma completo) e **MP4** animato (540 x 960 oppure 1080 x 1920).
- Ripristina in qualsiasi momento il modulo **1-1-3-1**.

L'editor utilizza un piccolo componente web locale (in `frontend/index.html`), senza servizi remoti. Le posizioni aggiornano il renderer Python, quindi i file esportati riproducono il layout scelto. Il modello usa sette giocatori fissi; non è ancora un editor generico di elementi arbitrari.

## Avvio locale

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

## Pubblicazione gratuita su Streamlit Community Cloud

1. Estrai lo ZIP. In un repository GitHub carica **il contenuto della cartella** (inclusa `frontend/index.html`, `renderer.py`, `requirements.txt` e `assets/`).
2. Vai su https://share.streamlit.io/ e crea una nuova app collegando il repository.
3. Come entrypoint inserisci `app.py` e conferma.
4. Le librerie verranno installate tramite `requirements.txt`.

Per aggiornare la versione precedente puoi sostituire i file del repository con questi (assicurati di aggiungere anche la cartella `frontend`). I piani gratuiti hanno limiti di risorse: usa MP4 540x960 se il rendering Full HD supera i limiti della piattaforma.

## Note e limiti

- I font caricati sono usati per rasterizzare testi dentro le immagini esportate: non devi installarli sul server. Usa solo font per i quali hai la licenza necessaria.
- Il layout non viene salvato permanentemente tra sessioni browser. L'esportazione funziona nella sessione corrente.
- Non è prevista la riproduzione audio; l'audio può essere aggiunto in Instagram o con un editor dedicato.
- I PNG sono in formato ritratto 9:16; il MP4 è codificato con H.264. Non viene usata alcuna API AI.
