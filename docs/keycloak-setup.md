# Keycloak — autenticazione, SPID e registrazione (runbook)

> Deliverable della **Fase 5** dell'issue **#235**. Come allestire l'Identity
> Provider OIDC self-hosted che autentica `opendata-ai`: login, **SPID** e
> **registrazione con email + codice**. Il codice di app è già pronto (backend
> OIDC-neutrale #237, RBAC #239/#240, dashboard admin #242, frontend OIDC #241):
> qui si configura l'IdP e lo si collega alle env.

## Perché Keycloak

Il progetto è open source e ogni Regione lo ospita in casa. Keycloak è un IdP
**self-hostable, standard OIDC/SAML**, adatto alle policy della PA: gestisce login,
sessioni, registrazione con verifica email/OTP e — tramite broker — **SPID**. La
nostra app non implementa nulla di tutto ciò: riceve solo i **JWT OIDC** che
Keycloak emette (verificati via JWKS) e legge i ruoli dal proprio DB.

```
Browser (opendata-ai-ui)  ──OIDC Auth Code + PKCE──▶  Keycloak (realm opendata)
      │  access_token (JWT)                                  │  broker SPID
      ▼                                                      └─ registrazione email+OTP
opendata-backend  ──verifica JWT via JWKS ${OIDC_ISSUER}/.well-known/jwks.json──▶
      └─ autorizzazione: ruolo da opendata.users.role (dashboard /admin)
```

> **Divisione delle responsabilità.** Keycloak = **autenticazione** (chi sei).
> `opendata.users.role` + `/admin` = **autorizzazione** (cosa puoi fare). Non
> mettere i ruoli applicativi in Keycloak: restano nel nostro DB.

## 1. Realm e client

1. Crea un **realm** dedicato, es. `opendata`. L'issuer diventa
   `https://<sso-host>/realms/opendata` → è il valore di `OIDC_ISSUER`
   (backend) e `NEXT_PUBLIC_OIDC_AUTHORITY` (frontend).
2. Crea un **client pubblico** per la SPA (il frontend è static export, nessun
   client secret):
   - **Client ID**: `opendata-ui` (→ `NEXT_PUBLIC_OIDC_CLIENT_ID`).
   - **Client authentication**: OFF (public client).
   - **Standard flow**: ON (Authorization Code). **PKCE**: `S256` (obbligatorio).
   - **Valid redirect URIs**: `https://<ui-host>/*` (il nostro client usa la
     root come `redirect_uri`; il wildcard copre eventuali basePath).
   - **Valid post-logout redirect URIs**: `https://<ui-host>/*`.
   - **Web origins**: `https://<ui-host>` (o `+` per derivarli dai redirect).
3. **Audience** (opzionale ma consigliato): se imposti `OIDC_AUDIENCE` sul
   backend, aggiungi un *audience mapper* al client così il token porta l'`aud`
   atteso (Keycloak per default non emette l'`aud` del client). Se lasci
   `OIDC_AUDIENCE` vuoto, il backend non valida l'audience.

## 2. Registrazione con email + codice

1. Realm → **Login** → abilita **User registration** = ON.
2. **Email verification** = ON: alla registrazione Keycloak invia un link/codice
   di conferma. Per il codice OTP via email usa il required action / authenticator
   **"Email OTP"** (disponibile come estensione/authenticator) oppure il flow di
   *Verify Email* standard.
3. Realm → **Email**: configura l'SMTP (mittente, host, TLS) — senza, la verifica
   email non parte.
4. Il nostro frontend invia `prompt=create` (OIDC): con *User registration* attiva
   l'utente atterra direttamente sulla schermata di registrazione.

Il campo email/nome/cognome del form corrisponde ai claim standard OIDC
(`email`, `given_name`/`family_name`, `name`) che il backend legge dal JWT.

## 3. SPID (broker)

SPID richiede un **Service Provider certificato AgID**. Due strade, entrambe
lasciano Keycloak come IdP verso la nostra app:

- **Aggregatore SPID** (consigliato per un ente che non vuole certificare un SP
  proprio): l'aggregatore è il SP certificato; lo colleghi a Keycloak come
  **Identity Provider OIDC/SAML** (Realm → *Identity providers* → aggiungi il
  provider dell'aggregatore). Gli utenti scelgono "Entra con SPID" sulla pagina
  Keycloak.
- **Plugin keycloak-spid** (SP SAML SPID direttamente in Keycloak): richiede
  metadata, certificati e la registrazione presso AgID. Più controllo, più
  compliance a carico dell'ente.

In entrambi i casi mappa gli attributi SPID (codice fiscale, nome, cognome,
email) sui claim OIDC standard con gli *attribute mappers* dell'identity provider.

> **Dato personale (§7 del pivot).** Il codice fiscale SPID è dato personale:
> non va pubblicato negli open data. Resta nell'IdP / nel profilo utente; l'app
> ne usa al più `sub`/`email` per identificare la sessione.

## 4. Ruoli e primo amministratore

- I ruoli applicativi (`admin`/`regione`/`comune`/`cittadino`) **non** stanno in
  Keycloak: vivono in `opendata.users.role`. Un nuovo utente è `cittadino`.
- **Primo admin**: imposta `BOOTSTRAP_ADMIN_EMAIL` sul backend con l'email
  dell'RTD. Al primo login quell'utente è promosso ad `admin` e da lì assegna i
  ruoli agli altri dalla dashboard **`/admin`**.

## 5. Collegamento alle env

Backend (`.env` / `.env.production`):

```bash
AUTH_ENABLED=true
OIDC_ISSUER=https://<sso-host>/realms/opendata
OIDC_AUDIENCE=opendata-ui          # solo se hai aggiunto l'audience mapper
BOOTSTRAP_ADMIN_EMAIL=rtd@regione.example
```

Frontend (`opendata-ai-ui`, baked al build — static export):

```bash
NEXT_PUBLIC_OIDC_AUTHORITY=https://<sso-host>/realms/opendata
NEXT_PUBLIC_OIDC_CLIENT_ID=opendata-ui
# NEXT_PUBLIC_OIDC_SCOPE=openid profile email   # opzionale (default)
```

> `NEXT_PUBLIC_OIDC_AUTHORITY` e `OIDC_ISSUER` **devono coincidere** (stesso
> issuer): il frontend prende i token da quell'issuer e il backend li verifica
> contro lo stesso JWKS.

## 6. Verifica end-to-end

1. Apri la UI → «Accedi»: sei rediretto a Keycloak; login o «Entra con SPID».
2. «Registrati» (o `prompt=create`): form email → codice di conferma → sessione.
3. Torni alla UI: il badge utente compare; le chiamate API portano il Bearer JWT.
4. Con `BOOTSTRAP_ADMIN_EMAIL` = la tua email, vedi la voce **Amministrazione**
   nel menu utente → `/admin` elenca gli utenti e ne cambia il ruolo.
5. Logout: sei rediretto all'end-session di Keycloak e la sessione è chiusa.

## 7. Modalità dev (senza Keycloak)

Lasciando `NEXT_PUBLIC_OIDC_*` vuote (frontend) e `AUTH_ENABLED=false` (backend)
l'app gira **senza auth**: utente sintetico `dev-user` trattato come `admin`, così
puoi sviluppare la dashboard e le viste senza un IdP. È il default di sviluppo.

## Riferimenti

- Backend OIDC-neutrale + rate limit: #237 · RBAC: #239/#240 · Dashboard admin +
  `/me`: #242 · Frontend OIDC/PKCE: #241 · CLAUDE.md **R7**.
- Contratti: `docs/cruscotto-regionale.md` §6-bis · issue #235 (commento design).
