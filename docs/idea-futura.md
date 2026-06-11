# Idea futura — redirect al login su sessione scaduta, senza toccare ogni widget

> Stato: **proposta**, non implementata. Annotata per non perderla.

## Problema

Vogliamo che, quando il JWT è davvero scaduto (sessione finita, non solo
l'access token dei 30 minuti), l'utente venga riportato alla pagina di login —
**anche dalle chiamate fatte dai widget**.

La prima idea era far emettere a ogni widget un evento `auth-expired` che l'host
(`RemoteWidget`) ascolta. Va rifiutata: è boilerplate per-widget. Ogni nuovo
widget dovrebbe ricordarsi di emettere l'evento, contro l'obiettivo di fondo
"aggiungo un widget senza plumbing ripetuto né edit all'host".

## Idea: un interceptor globale su `window.fetch` (un solo seam, pagato una volta)

Fatto chiave: **tutti i widget girano nello stesso `window` dell'host**. Lo
Shadow DOM isola stile e markup, **non** il realm JavaScript — quindi la `fetch`
interna di un widget risolve nella stessa `window.fetch` che l'host può
wrappare. Un singolo interceptor installato dall'host copre automaticamente
anche le chiamate di ogni widget, presente e futuro, **senza che il widget
importi o emetta nulla**.

### Come funziona

All'avvio dell'app, in browser, l'host wrappa `window.fetch`:

- Su risposta **401** verso l'origine del gateway/API: prova
  `ensureValidAccessToken()`.
  - Refresh riuscito → ri-esegue la chiamata sostituendo l'header
    `Authorization` col token fresco (recupero **trasparente**: il widget non se
    ne accorge).
  - Refresh fallito → `redirectToLogin()`.
- Qualsiasi altra risposta passa intatta.

Un nuovo widget usa `fetch` normale ed eredita il comportamento. Zero codice
per-widget. È lo stesso spirito del seam `RemoteWidget` / edge-gateway: un punto
generico pagato una volta sola.

### Caveat da gestire nell'implementazione

1. **Scoping per URL** — agire solo sulle chiamate verso l'origine gateway/API,
   per non toccare le `fetch` interne di Next (HMR, RSC).
2. **Escludere `/auth/refresh`** dall'intercettazione → niente loop infiniti.
3. **Idempotenza** — un flag per non ri-patchare a ogni render/HMR.
4. **Solo browser** — no-op durante l'SSR.

### Rapporto con ciò che esiste già

- `middleware.ts` copre già il redirect **su navigazione** quando manca il
  cookie di sessione (`ju_auth_session`, TTL del refresh token).
- Il fix in `lib/fetch-wrapper.ts` copre le chiamate **dell'app** (get/post/...)
  quando il refresh fallisce.
- Questo interceptor sarebbe la **rete di sicurezza universale** che include
  anche i widget (bundle separati con la loro `fetch`).
- Opzionale: spostare *tutta* la logica 401 nell'interceptor e semplificare il
  fetch-wrapper — passo in più, non necessario per far funzionare l'idea.

### Forma proposta

Un modulo `lib/auth-fetch-interceptor.ts` con una funzione
`installAuthFetchInterceptor()` idempotente, chiamata una volta
nell'`AuthProvider` (lato browser).

## Perché NON nell'edge-gateway

Il redirect deve avvenire nel browser: il gateway non vede l'header
`Authorization` sulle navigazioni, distinguerebbe male "access scaduto" da
"sessione scaduta", e per ADR-0002 resta puro reverse-proxy senza logica di
dominio né secret al confine.
