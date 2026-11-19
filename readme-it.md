<p align="center">
  <img src="docs/logo.svg" alt="flatnotes" width="300">
</p>

# flatnotes

Applicazione self-hosted per prendere appunti in Markdown, con ricerca, tag, personalizzazione grafica e pubblicazione selettiva delle note. I contenuti rimangono normali file `.md`; Whoosh gestisce l'indice di ricerca e SQLite conserva **soltanto i metadati di pubblicazione**.

[English README](README.md) · [Documentazione / Wiki](wiki/Home.md) · [Immagini Docker](https://github.com/erathaowl/flatnotes/pkgs/container/flatnotes) · [Release](https://github.com/erathaowl/flatnotes/releases)

## Funzionalità

- Interfaccia web responsive, editor Markdown/WYSIWYG, temi chiaro/scuro e ricerca full-text.
- Tag, collegamenti tra note (`[[Titolo Nota]]`), immagini e sezione di accesso rapido configurabile.
- Autenticazione `none`, `read_only`, `password` oppure `totp`.
- Pubblicazione di singole note tramite link casuale, derivato dal titolo o personalizzato, in sola lettura oppure con modifica anonima.
- Titolo, logo e favicon personalizzabili attraverso variabili d'ambiente.
- API REST, immagini Docker su GHCR, build automatizzate e release versionate.

## Installazione tramite wheel Python

Le release includono anche il file `flatnotes-6.0.0-py3-none-any.whl`,
contenente **backend FastAPI, frontend Vue già compilato e comando `flatnotes`**.
Sul server è sufficiente **Python 3.13**, senza bisogno di Node.js o Docker.

Scarica il wheel dalla [release](https://github.com/erathaowl/flatnotes/releases/tag/v6.0.0),
poi esegui:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install flatnotes-6.0.0-py3-none-any.whl

mkdir -p ./data
export FLATNOTES_PATH="$(pwd)/data"
export FLATNOTES_AUTH_TYPE=password
export FLATNOTES_USERNAME=admin
export FLATNOTES_PASSWORD="change-this-password"
export FLATNOTES_SECRET_KEY="replace-with-a-long-random-secret"

flatnotes --host 0.0.0.0 --port 8080
```

Il wheel contiene anche gli asset statici e funziona da qualunque directory.
Il comando accetta `--host`, `--port` e `--forwarded-allow-ips`. Per
l'esercizio su una VM è possibile configurare systemd e un reverse proxy HTTPS.
Note, allegati e metadati SQLite rimangono nella directory `FLATNOTES_PATH`,
esterna al pacchetto, così gli aggiornamenti dell'applicazione non li toccano.

Il wheel viene controllato in CI con installazione in un ambiente pulito e
verifiche su CLI, endpoint `/health`, pagina HTML, API e file JavaScript.

## Avvio con Docker Compose

Crea un file `compose.yaml`:

```yaml
services:
  flatnotes:
    image: ghcr.io/erathaowl/flatnotes:develop
    container_name: flatnotes
    ports:
      - "8080:8080"
    environment:
      PUID: "1000"
      PGID: "1000"
      FLATNOTES_AUTH_TYPE: "password"
      FLATNOTES_USERNAME: "admin"
      FLATNOTES_PASSWORD: "${FLATNOTES_PASSWORD}"
      FLATNOTES_SECRET_KEY: "${FLATNOTES_SECRET_KEY}"
    volumes:
      - ./data:/data
    restart: unless-stopped
```

Prepara un file `.env` contenente `FLATNOTES_PASSWORD` e `FLATNOTES_SECRET_KEY`, con valori forti e distinti. Per creare una chiave casuale puoi usare `openssl rand -hex 32`. Avvia:

```bash
docker compose up -d
```

Apri `http://localhost:8080`. Tutte le note e i metadati di pubblicazione sono persistenti nella cartella `./data`. Il tag `:develop` contiene le build del ramo di sviluppo; `:latest` è aggiornato soltanto dalle release versionate.

Maggiori informazioni: [Docker e release](wiki/Docker-and-Releases.md) e [variabili d'ambiente](wiki/Environment-Variables.md).

## Note protette con cifratura nel browser

Imposta `FLATNOTES_ENCRYPTION_ENABLED=true` per abilitare il pulsante
**Protect** e la creazione di note cifrate. L'app usa **Argon2id** per
derivare una chiave dalla password e **AES-256-GCM** per cifrare una
chiave casuale per nota e i suoi contenuti. Tutte le operazioni crittografiche
si svolgono in un Web Worker nel browser. Le API delle note cifrate
ricevono esclusivamente dati cifrati.

La struttura degli indirizzi è:

- `/n/{titolo}`: nota normale in Markdown, con autenticazione ordinaria.
- `/p/{slug}`: nota pubblicata, eventualmente cifrata.
- `/e/{id}`: nota cifrata identificata da un codice casuale.

I file cifrati sono salvati come `/data/{id}.md.enc`. Titoli e tag
rimangono dentro il contenuto cifrato; il server non li indicizza.
La password viene chiesta in una finestra nel browser e **non compare
mai nell'URL**. Se perdi la password, non è possibile recuperare il contenuto.

Le immagini possono essere incorporate nella nota in forma di data URL,
poi cifrate insieme al testo. Altri file possono essere allegati in forma
cifrata all'interno del file della nota, fino a 2 MiB complessivi. Prima di proteggere una nota esistente,
occorre rimuovere o incorporare eventuali allegati esterni non cifrati.
Puoi esportare una nota protetta come file Markdown direttamente dal
browser. La rimozione automatica della protezione non è prevista perché
richiederebbe la trasmissione del testo in chiaro al server.

Con `FLATNOTES_SHARING_ENABLED=false` disabiliti condivisioni e API
pubbliche senza cancellare i metadati di pubblicazione. La condivisione
è abilitata per impostazione predefinita, mentre la cifratura è disabilitata.
Le note già cifrate restano leggibili anche se la cifratura è disabilitata.

Per garantire il modello di sicurezza, usa HTTPS, password robuste e un
browser aggiornato. Una nota prima salvata in chiaro può lasciare copie
storiche in backup, snapshot e blocchi degli indici di ricerca.
Il browser esegue codice JavaScript fornito dal server: un server
compromesso potrebbe distribuire codice client dannoso.

Approfondimenti: [Encrypted Notes](wiki/Encrypted-Notes.md).

## Pubblicazione delle note

Apri una nota già salvata e premi **Share**. Le note sono inizialmente private. Puoi scegliere l'accesso pubblico in **sola lettura** o abilitare **la modifica da parte di chi possiede il collegamento**.

Il suffisso dell'URL può essere:

- **Casuale** (predefinito): ad esempio `/p/82eace7f63bc824b35a44dfb2958cdb0`.
- **Derivato dal titolo**: versione normalizzata del titolo della nota.
- **Personalizzato**: identificativo inserito manualmente, con lettere minuscole, numeri e trattini.

Il pulsante **Save** memorizza la configurazione e chiude la finestra. Riaprendo **Share** puoi copiare il link o revocare la pubblicazione. Un link precedente non funziona più dopo la revoca o la modifica dell'URL. La rinomina di una nota dall'app mantiene il link pubblico corrente.

Gli utenti anonimi, quando l'istanza usa `password` o `totp`, possono consultare soltanto le note pubblicate. Per le note modificabili possono intervenire **sul contenuto**, senza rinominare, cancellare, caricare allegati o alterare le impostazioni di condivisione. Le modifiche concorrenti vengono controllate tramite revisione (HTTP 409 in caso di conflitto).

**Sicurezza:** chiunque conosca un link modificabile può cambiare il contenuto. Un URL basato sul titolo o personalizzato può essere indovinato. Per rendere private le note non pubblicate, scegli `password` o `totp`: con `none` e `read_only` l'accesso anonimo è già esteso per definizione.

Approfondimenti: [Pubblicazione delle note](wiki/Publishing-Notes.md).

## Personalizzazione di titolo, logo e favicon

| Variabile | Esempio | Effetto |
| --- | --- | --- |
| `FLATNOTES_SITE_TITLE` | `Le mie note` | Titolo della scheda e nome mostrato nell'interfaccia |
| `FLATNOTES_LOGO_PATH` | `/data/branding/logo.svg` | Sostituisce il logo completo |
| `FLATNOTES_FAVICON_PATH` | `/data/branding/favicon.ico` | Cambia la favicon |

Con il volume dell'esempio, salva i file in `./data/branding/`. I percorsi devono essere assoluti **all'interno del container**. Se una variabile è assente, rimane il valore predefinito. Per il logo sono supportati SVG, PNG, JPEG e WebP; per la favicon anche ICO.

Guida: [Custom Branding](wiki/Custom-Branding.md).

## Abilitazione TOTP

Imposta `FLATNOTES_AUTH_TYPE=totp` e aggiungi `FLATNOTES_TOTP_KEY` con un segreto casuale e persistente. Riavvia il container e consulta:

```bash
docker compose logs flatnotes
```

All'avvio compare un QR code con cui configurare l'app Authenticator; viene mostrato anche il segreto per l'inserimento manuale. Per accedere dovrai fornire username, password e il codice corrente di sei cifre. I log contengono informazioni sensibili.

La durata standard della sessione JWT è di 30 giorni, modificabile con `FLATNOTES_SESSION_EXPIRY_DAYS`. Leggi la guida [Environment Variables](wiki/Environment-Variables.md#totp-setup).

## Persistenza e backup

- `/data/*.md`: note in Markdown.
- `/data/attachments/`: allegati.
- `/data/.flatnotes/`: indice Whoosh ricreabile.
- `/data/.flatnotes-publications.db`: database SQLite dei link pubblici e relativi permessi.

Salva note, allegati e database nei backup. A container avviato utilizza una procedura compatibile con SQLite, oppure arresta il servizio prima della copia. L'indice Whoosh può essere ricreato; il database delle pubblicazioni va conservato.

## CI/CD e release

I push su `develop` attivano compilazione frontend, test Python, creazione di un archivio `.tar.gz` e un wheel `.whl` e pubblicazione delle immagini `:develop` e `:sha-<commit>` su GHCR. Le pull request eseguono la validazione senza pubblicare immagini.

Un tag `vX.Y.Z` (oppure `vX.Y`, normalizzato in `vX.Y.0`) pubblica l'immagine versionata e aggiorna `:latest`, creando una [GitHub Release](https://github.com/erathaowl/flatnotes/releases) con archivio contenente backend e frontend compilato e wheel installabile con pip. L'archivio è un bundle del progetto e non un pacchetto wheel.

## Documentazione e licenza

Le pagine della wiki sono disponibili nella directory [`wiki/`](wiki/Home.md), versionate con il codice. Possono essere sincronizzate con la [Wiki GitHub del fork](https://github.com/erathaowl/flatnotes/wiki) una volta inizializzata. Consulta anche [CONTRIBUTING.md](CONTRIBUTING.md) e [LICENSE](LICENSE).

Questo fork deriva da [flatnotes](https://github.com/dullage/flatnotes) e utilizza [Whoosh](https://whoosh.readthedocs.io/) e [TOAST UI Editor](https://ui.toast.com/tui-editor).
