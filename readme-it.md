<p align="center">
  <img src="docs/logo.svg" alt="flatnotes" width="300">
</p>

# flatnotes

Applicazione self-hosted per prendere appunti in Markdown, con ricerca, tag, personalizzazione grafica e pubblicazione selettiva delle note. Le note ordinarie rimangono file `.md`; quelle protette vengono salvate in file `.md.enc` cifrati e decifrati soltanto nel browser. Whoosh indicizza le note ordinarie e SQLite conserva i metadati di pubblicazione.

[English README](README.md) · [Documentazione / Wiki](wiki/Home.md) · [Immagini Docker](https://github.com/erathaowl/flatnotes/pkgs/container/flatnotes) · [Release](https://github.com/erathaowl/flatnotes/releases)

## Funzionalità

- Interfaccia web responsive, editor Markdown/WYSIWYG, temi chiaro/scuro e ricerca full-text.
- Tag, collegamenti tra note (`[[Titolo Nota]]`), immagini e sezione di accesso rapido configurabile.
- Autenticazione `none`, `read_only`, `password` oppure `totp`.
- Pubblicazione di singole note tramite link casuale, derivato dal titolo o personalizzato, in sola lettura oppure con modifica anonima.
- Note cifrate con Argon2id e AES-256-GCM, password richiesta solo nel browser e allegati protetti.
- Lunghezza e complessità delle nuove password configurabili, cancellazione delle note cifrate anche senza conoscere la password.
- Variabili d'ambiente per abilitare la cifratura e sospendere tutte le pubblicazioni.
- Titolo, logo e favicon personalizzabili attraverso variabili d'ambiente.
- API REST, immagini Docker su GHCR, build automatizzate e release versionate.

## Guide rapide

| Argomento | Documentazione |
| --- | --- |
| Installazione Docker o wheel | [Docker and Releases](wiki/Docker-and-Releases.md) |
| Tutte le variabili d'ambiente | [Environment Variables](wiki/Environment-Variables.md) |
| Creazione e modifica delle note | [Notes and Editor](wiki/Notes-and-Editor.md) |
| Cifratura e gestione password | [Encrypted Notes](wiki/Encrypted-Notes.md), [Security and Cryptography](wiki/Security-and-Cryptography.md) |
| Condivisione | [Publishing Notes](wiki/Publishing-Notes.md) |
| Backup, manutenzione e problemi comuni | [Operations and Backup](wiki/Operations-and-Backup.md), [Troubleshooting](wiki/Troubleshooting.md) |
| API | [API Reference](wiki/API-Reference.md) |

## Installazione tramite wheel Python

Le release includono anche il file `flatnotes-6.4.0-py3-none-any.whl`,
contenente **backend FastAPI, frontend Vue già compilato e comando `flatnotes`**.
Sul server è sufficiente **Python 3.13**, senza bisogno di Node.js o Docker.

Scarica il wheel dalla [release](https://github.com/erathaowl/flatnotes/releases/tag/v6.4.0),
poi esegui:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install flatnotes-6.4.0-py3-none-any.whl

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
    image: ghcr.io/erathaowl/flatnotes:v6.4.0
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
      FLATNOTES_ENCRYPTION_ENABLED: "true"
      FLATNOTES_SHARING_ENABLED: "true"
      FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH: "12"
      FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES: "0"
    volumes:
      - ./data:/data
    restart: unless-stopped
```

Prepara un file `.env` contenente `FLATNOTES_PASSWORD` e `FLATNOTES_SECRET_KEY`, con valori forti e distinti. Per creare una chiave casuale puoi usare `openssl rand -hex 32`. Avvia:

```bash
docker compose up -d
```

Apri `http://localhost:8080`. Tutte le note e i metadati di pubblicazione sono persistenti nella cartella `./data`. L'esempio utilizza la versione stabile `:v6.4.0`; `:latest` indica l'ultima release pubblicata, mentre `:master` è destinato ai test dei commit più recenti del branch principale.

Maggiori informazioni: [Docker e release](wiki/Docker-and-Releases.md) e [variabili d'ambiente](wiki/Environment-Variables.md).

## Note protette con cifratura nel browser

Imposta `FLATNOTES_ENCRYPTION_ENABLED=true` per abilitare il pulsante
**Protect** e la creazione di note cifrate. L'app usa **Argon2id** per
derivare una chiave dalla password e **AES-256-GCM** per cifrare una
chiave casuale per nota e i suoi contenuti. Tutte le operazioni crittografiche
si svolgono in un Web Worker nel browser. Le API delle note cifrate
ricevono esclusivamente dati cifrati.

La politica per le password delle note cifrate è configurabile tramite due
variabili d'ambiente:

| Variabile | Default | Significato |
| --- | --- | --- |
| `FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH` | `12` | Lunghezza minima (0 disabilita il controllo sulla lunghezza) |
| `FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES` | `0` | Numero minimo di categorie da 0 a 4: minuscole, maiuscole, numeri e simboli |

I controlli vengono eseguiti soltanto nel browser quando si crea o si
protegge una nota. Le password delle note già cifrate rimangono valide
indipendentemente dalle modifiche alla politica. Dalla pagina **Protected
Notes** si può eliminare una nota anche senza conoscere la sua password,
confermando la cancellazione e usando il normale accesso all'applicazione.

### Uso delle note protette

1. Premi **New Protected** oppure apri **Protected Notes** (`/encrypted`) e scegli **New protected note**.
2. Imposta la password di protezione e confermala. I requisiti configurati vengono mostrati nella finestra.
3. Inserisci titolo e contenuto, quindi premi **Save**. Il server riceve soltanto dati cifrati.
4. Per riaprire la nota usa `/e/{id}` e inserisci la password nel browser.
5. Usa **Lock** al termine. Con **Share** puoi pubblicare un collegamento cifrato `/p/{slug}`.

Puoi premere **Protect** direttamente durante la modifica di una nota normale, anche quando è una nuova bozza ancora da salvare. Il browser cifra il titolo e il contenuto presenti nell'editor senza inviare prima una copia in chiaro al server. Per le note già esistenti, la conversione sostituisce il file Markdown attivo e revoca le condivisioni precedenti. Per le nuove bozze viene creato direttamente il file cifrato. Gli allegati esterni devono prima essere rimossi o incorporati.

La lista **Protected Notes** mostra identificativi casuali. Il pulsante rosso Delete consente di eliminare una nota anche senza conoscerne la password, purché l'utente possa modificare i dati dell'applicazione. Il recupero della password, il suo cambio e la conversione automatica della nota cifrata in Markdown non sono attualmente previsti.

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

## Scadenza delle condivisioni ed eliminazione automatica

La scadenza si imposta **solo nel modale Share**, sia per le note normali sia per quelle cifrate. Riguarda il link pubblico e non limita l'accesso privato del proprietario.

- **Never** (predefinito): nessuna scadenza.
- **After N hours / After N days**: il link scade dopo il periodo scelto.
- **Single view**: la prima visualizzazione pubblica consuma il link, soltanto per condivisioni in lettura.

Il flag **Automatically delete this note when the share expires** è **deselezionato per impostazione predefinita** e compare quando è configurata una scadenza. Se attivato, il server elimina anche la nota originale; altrimenti scade soltanto il link. Il comando **Unpublish** conserva sempre la nota.

L'apertura privata non consuma mai la singola visualizzazione pubblica. Le note Markdown restano disponibili nella ricerca. Nel caso cifrato, la password rimane nel browser, che invia al server soltanto una prova crittografica dopo la decifratura. I file cifrati già scaricati possono comunque essere conservati.

**Non esistono più variabili d'ambiente per scadenza e valore predefinito.** Ogni nuova condivisione nasce senza scadenza e con l'eliminazione automatica disattivata.

**Aggiornamento dalla 6.3.0:** le scadenze delle note condivise passano ai link, mantenendo il termine e la precedente politica di eliminazione. Le scadenze delle note private non condivise vengono rimosse, preservando le note. Esegui prima il backup del database SQLite.

Guida dettagliata: [Publishing Notes](wiki/Publishing-Notes.md).

### Interfaccia unificata

Le note Markdown e cifrate condividono campo titolo, barra comandi e interruttore **Edit**. **Share** è evidenziato quando la condivisione è attiva, attenuato quando è privata o scaduta; **Delete** è rosso. Il modale Share è utilizzabile prima del primo Save, configurando anche scadenza ed eliminazione automatica. Le impostazioni vengono applicate dopo il salvataggio della nota; un errore di pubblicazione non cancella il contenuto. **Protect** può cifrare direttamente una bozza non salvata.


## Pubblicazione delle note

Apri una nota già salvata e premi **Share**. Le note sono inizialmente private. Puoi scegliere l'accesso pubblico in **sola lettura** o, per le sole note Markdown, abilitare **la modifica da parte di chi possiede il collegamento**.

Il suffisso dell'URL può essere:

- **Casuale** (predefinito): ad esempio `/p/82eace7f63bc824b35a44dfb2958cdb0`.
- **Derivato dal titolo**: versione normalizzata del titolo della nota.
- **Personalizzato**: identificativo inserito manualmente, con lettere minuscole, numeri e trattini.

Il pulsante **Save** memorizza la configurazione e chiude la finestra. Riaprendo **Share** puoi copiare il link o revocare la pubblicazione. Un link precedente non funziona più dopo la revoca o la modifica dell'URL. La rinomina di una nota dall'app mantiene il link pubblico corrente.

Gli utenti anonimi, quando l'istanza usa `password` o `totp`, possono consultare soltanto le note pubblicate. Per le note Markdown modificabili possono intervenire **sul contenuto**, senza rinominare, cancellare, caricare allegati o alterare le impostazioni di condivisione. Le condivisioni di note cifrate sono sempre in sola lettura, anche se create in precedenza con permesso di modifica. Le modifiche concorrenti alle note Markdown vengono controllate tramite revisione (HTTP 409 in caso di conflitto). In modalità `read_only` anche le API pubbliche di modifica sono bloccate.

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

- `/data/*.md`: note ordinarie in Markdown.
- `/data/*.md.enc`: note cifrate, da conservare insieme alle relative password.
- `/data/attachments/`: allegati.
- `/data/.flatnotes/`: indice Whoosh ricreabile.
- `/data/.flatnotes-publications.db`: database SQLite dei link pubblici e relativi permessi.

Salva note ordinarie, file cifrati, allegati e database nei backup. A container avviato utilizza una procedura compatibile con SQLite, oppure arresta il servizio prima della copia. L'indice Whoosh può essere ricreato; il database delle pubblicazioni va conservato.

## CI/CD e release

I push su `master` attivano compilazione frontend, test Python, creazione di un archivio `.tar.gz` e un wheel `.whl` e pubblicazione delle immagini `:master` e `:sha-<commit>` su GHCR. Le pull request eseguono la validazione senza pubblicare immagini.

Un tag `vX.Y.Z` (oppure `vX.Y`, normalizzato in `vX.Y.0`) pubblica l'immagine versionata e aggiorna `:latest`, creando una [GitHub Release](https://github.com/erathaowl/flatnotes/releases) con archivio contenente backend e frontend compilato e wheel installabile con pip. L'archivio è un bundle del progetto e non un pacchetto wheel.

## Documentazione e licenza

Le pagine della wiki sono disponibili nella directory [`wiki/`](wiki/Home.md), versionate con il codice. Sono sincronizzate con la [Wiki GitHub del fork](https://github.com/erathaowl/flatnotes/wiki) tramite GitHub Actions. Consulta anche [CONTRIBUTING.md](CONTRIBUTING.md) e [LICENSE](LICENSE).

Questo fork deriva da [flatnotes](https://github.com/dullage/flatnotes) e utilizza [Whoosh](https://whoosh.readthedocs.io/) e [TOAST UI Editor](https://ui.toast.com/tui-editor).
