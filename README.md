# Torino Culturale – il tuo hub

Una pagina web personale con: **cinema di Torino** (programmazione di 19 sale + calendario ufficiale del Massimo con ospiti e rassegne), **mostre**, **eventi e conferenze**, collegata a Letterboxd (watchlist, visti tuoi, e chi dei 24 che segui ha visto ogni film, con voto e recensione).

Si aggiorna **da sola ogni giorno** (GitHub Actions) e ti manda una **email il lunedì**. Tu apri solo un segnalibro.

## Installazione (circa 15 minuti, una volta sola)

1. **Account GitHub** (gratis): github.com → Sign up.
2. **Nuovo repository**: "New repository" → nome `hub-torino` → *Public* (serve per Pages gratuito) → Create.
3. **Carica i file**: nel repository clicca "uploading an existing file" e trascina tutto il contenuto di questa cartella (incluse le cartelle `.github`, `scripts`, `docs`, `data`, `tests`). Se `.github` non si trascina, usa "Add file → Create new file" e incolla `update.yml` col percorso `.github/workflows/update.yml`.
4. **Chiave TMDB** (gratis, serve ad abbinare i titoli italiani ai film Letterboxd): themoviedb.org → account → Settings → API → richiedi chiave "Developer" → copia la *API Key (v3)*.
5. **Segreti**: repository → Settings → Secrets and variables → Actions → New repository secret:
   - `TMDB_API_KEY` = la chiave di TMDB
   - (per l'email, facoltativo) `SMTP_USER` = il tuo indirizzo Gmail, `SMTP_PASS` = una *password per le app* di Google (account Google → Sicurezza → Verifica in 2 passaggi → Password per le app), `MAIL_TO` = dove ricevere il riepilogo.
6. **Abilita la scrittura**: Settings → Actions → General → Workflow permissions → *Read and write permissions* → Save.
7. **Pages**: Settings → Pages → Source: *Deploy from a branch* → Branch `main`, cartella `/docs` → Save. L'indirizzo sarà `https://TUOUTENTE.github.io/hub-torino/` → mettilo nei preferiti.
8. **Primo avvio**: tab *Actions* → "Aggiorna hub" → *Run workflow*. Dopo 2–5 minuti ricarica la pagina.

## Cosa fa ogni giorno
- Legge la programmazione di oggi per ogni cinema e il calendario del Massimo.
- Legge i diari Letterboxd tuoi e dei 24 seguiti (l'RSS dà ~50 film recenti a persona: la cronologia si **accumula nel tempo** nei file `data/diary_*.json`), la tua watchlist e gli avatar.
- Estrae mostre/eventi dalle pagine di arte.it, CAMERA, Museo del Cinema, Turismo Torino con GitHub Models (gratuito, con limiti).
- Se una fonte smette di funzionare, **non cancella i dati vecchi**: la pagina mostra "Fonti non aggiornate" e l'email del lunedì lo segnala.

## Limiti da sapere
- **Mai testato sui siti reali**: i parser sono scritti su strutture osservate. Il primo avvio può fallire su qualche fonte: guarda il banner giallo sulla pagina, oppure il log in *Actions*, e incollalo a Claude per sistemare.
- Senza chiave TMDB i titoli italiani non si abbinano ai film Letterboxd.
- Lo storico dei seguiti parte dagli ultimi ~50 film ciascuno. Per i tuoi visti vecchi: esporta i dati da Letterboxd (Settings → Import & Export) e carica `watched.csv` in `data/import/watched.csv`.
- MYmovies mostra la programmazione di **oggi**; i giorni successivi si riempiono per il Massimo (calendario completo). Verificare al primo avvio se il sito offre anche i giorni seguenti.
- Cinema Ambrosio e multisala di Moncalieri/Beinasco non sono inclusi (aggiungibili in `config.json`).
- Rispetta i termini dei siti: poche richieste al giorno. Uso personale.

## Correzioni
- Film non riconosciuto: aggiungi il titolo italiano normalizzato e l'id TMDB in `overrides.json`.
- Cinema da aggiungere/togliere: `config.json`.
- Test locale: `pip install -r requirements.txt && python -m tests.test_all`.
