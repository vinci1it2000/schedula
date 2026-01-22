# API Reference (server)

> Generato automaticamente dal codice presente in `server.zip`.

## Indice & Convenzioni

- I path sotto includono già gli `url_prefix` registrati (es. `/item` e `/items` sono alias).

- Dove indicato, alcune route esistono solo se il servizio viene inizializzato (flag config nel `basic_app`).

- **Flask-Security** registra anche endpoint interni non presenti nel codice di questa repo: li elenco in un blocco dedicato.


## OpenAPI / Docs

| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/docs` | `openapi/__init__.py` |
| `GET` | `/openapi.json` | `openapi/__init__.py` |
| `GET` | `/openapi.yaml` | `openapi/__init__.py` |


## Security – Flask-Security (core)

Mount: `SECURITY_URL_PREFIX` (default: `/user`).

Feature flags (defaults nel codice): `CONFIRMABLE`, `CHANGEABLE`, `REGISTERABLE`, `RECOVERABLE`, `TRACKABLE`.


### Endpoint Flask-Security (auto-registrati)

**Nota**: i path possono variare leggermente in base alla versione di Flask-Security(-Too) installata e alla configurazione; qui trovi l’elenco *completo e tipico* per le feature abilitate.

| Metodi | Path | Sorgente |
|---|---|---|
| `POST` | `/user/login` | `Flask-Security` |
| `POST` | `/user/logout` | `Flask-Security` |
| `POST` | `/user/register` | `Flask-Security (REGISTERABLE)` |
| `GET` | `/user/confirm/<token>` | `Flask-Security (CONFIRMABLE)` |
| `POST` | `/user/confirm` | `Flask-Security (CONFIRMABLE) – re-send/trigger (se abilitato)` |
| `POST` | `/user/reset` | `Flask-Security (RECOVERABLE) – request reset (forgot)` |
| `POST` | `/user/reset/<token>` | `Flask-Security (RECOVERABLE) – perform reset` |
| `POST` | `/user/change` | `Flask-Security (CHANGEABLE) – change password` |
| `GET` | `/user/verify` | `Flask-Security – verify (solo se abilitato in config)` |


## Security – Route custom aggiuntive del progetto

| Metodi | Path | Sorgente |
|---|---|---|
| `POST, PATCH` | `/user/edit` | `security/__init__.py` |
| `GET` | `/user/plasmic` | `security/__init__.py` |
| `GET, POST, PATCH, PUT` | `/user/settings` | `security/__init__.py` |


## Groups / Workspace / RBAC

Default `url_prefix` nel servizio Groups: `/groups`.


| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/groups` | `security/groups.py` |
| `POST` | `/groups` | `security/groups.py` |
| `GET` | `/groups/<gid>` | `security/groups.py` |
| `PUT, PATCH` | `/groups/<gid>` | `security/groups.py` |
| `PATCH` | `/groups/<gid>/memberships` | `security/groups.py` |


## Casbin Admin Panel

| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/admin/casbin/grouping` | `security/admin_panel.py` |
| `POST, DELETE` | `/admin/casbin/grouping` | `security/admin_panel.py` |
| `GET` | `/admin/casbin/policies` | `security/admin_panel.py` |
| `POST, DELETE` | `/admin/casbin/policies` | `security/admin_panel.py` |


## Items – CRUD

Alias: tutte le route sono montate sia su `/item` che su `/items`.

| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/item/<category>` | `items/crud.py` |
| `POST` | `/item/<category>` | `items/crud.py` |
| `DELETE` | `/item/<category>/<item_id>` | `items/crud.py` |
| `GET` | `/item/<category>/<item_id>` | `items/crud.py` |
| `PUT, PATCH` | `/item/<category>/<item_id>` | `items/crud.py` |
| `GET` | `/items/<category>` | `items/crud.py` |
| `POST` | `/items/<category>` | `items/crud.py` |
| `DELETE` | `/items/<category>/<item_id>` | `items/crud.py` |
| `GET` | `/items/<category>/<item_id>` | `items/crud.py` |
| `PUT, PATCH` | `/items/<category>/<item_id>` | `items/crud.py` |


## Items – ACL / Manage

Alias: tutte le route sono montate sia su `/item` che su `/items`.

| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/item/<category>/<item_id>/acl/publish` | `items/manage.py` |
| `POST` | `/item/<category>/<item_id>/acl/publish` | `items/manage.py` |
| `GET` | `/item/<category>/<item_id>/acl/share` | `items/manage.py` |
| `PUT` | `/item/<category>/<item_id>/acl/share` | `items/manage.py` |
| `POST` | `/item/<category>/<item_id>/acl/unpublish` | `items/manage.py` |
| `GET` | `/items/<category>/<item_id>/acl/publish` | `items/manage.py` |
| `POST` | `/items/<category>/<item_id>/acl/publish` | `items/manage.py` |
| `GET` | `/items/<category>/<item_id>/acl/share` | `items/manage.py` |
| `PUT` | `/items/<category>/<item_id>/acl/share` | `items/manage.py` |
| `POST` | `/items/<category>/<item_id>/acl/unpublish` | `items/manage.py` |


## Items – Files

Alias: tutte le route sono montate sia su `/item-file` che su `/items-file`.

| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/item-file/<item_id>/<file_name>` | `items/files.py` |
| `GET` | `/items-file/<item_id>/<file_name>` | `items/files.py` |


## Schemas

Alias: tutte le route sono montate sia su `/admin/item-schema` che su `/admin/items-schema`.

| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/admin/item-schema/` | `items/schema.py` |
| `GET` | `/admin/item-schema/<category>` | `items/schema.py` |
| `POST` | `/admin/item-schema/<category>/drafts` | `items/schema.py` |
| `PUT` | `/admin/item-schema/<category>/drafts/<version>` | `items/schema.py` |
| `POST` | `/admin/item-schema/<category>/drafts/<version>/publish` | `items/schema.py` |
| `POST` | `/admin/item-schema/<category>/versions/<version>/disable` | `items/schema.py` |
| `POST` | `/admin/item-schema/<category>/versions/<version>/enable` | `items/schema.py` |
| `GET` | `/admin/items-schema/` | `items/schema.py` |
| `GET` | `/admin/items-schema/<category>` | `items/schema.py` |
| `POST` | `/admin/items-schema/<category>/drafts` | `items/schema.py` |
| `PUT` | `/admin/items-schema/<category>/drafts/<version>` | `items/schema.py` |
| `POST` | `/admin/items-schema/<category>/drafts/<version>/publish` | `items/schema.py` |
| `POST` | `/admin/items-schema/<category>/versions/<version>/disable` | `items/schema.py` |
| `POST` | `/admin/items-schema/<category>/versions/<version>/enable` | `items/schema.py` |


## Export

Disponibile solo se `SCHEDULA_EXPORT_FORM_ENABLED` è attivo.

| Metodi | Path | Sorgente |
|---|---|---|
| `GET, POST` | `/export-form/<path:form>` | `export/__init__.py` |


## Credits / Billing (Stripe)

Disponibile solo se `SCHEDULA_CREDITS_ENABLED` è attivo.

| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/stripe/balance` | `credits.py` |
| `GET` | `/stripe/balance/<int:wallet_id>` | `credits.py` |
| `POST` | `/stripe/create-checkout-session` | `credits.py` |
| `POST` | `/stripe/create-customer-portal-session` | `credits.py` |
| `POST` | `/stripe/create-customer-pricing-table-session` | `credits.py` |
| `GET` | `/stripe/session-status/<session_id>` | `credits.py` |
| `GET` | `/stripe/subscription` | `credits.py` |
| `GET` | `/stripe/subscription/<int:wallet_id>` | `credits.py` |
| `POST` | `/stripe/webhooks` | `credits.py` |


## GDPR

Disponibile solo se `SCHEDULA_GDPR_ENABLED` è attivo.

| Metodi | Path | Sorgente |
|---|---|---|
| `POST` | `/gdpr/consent` | `gdpr.py` |
| `GET` | `/gdpr/consent/<consent_id>` | `gdpr.py` |
| `GET` | `/gdpr/files/cookies-policy` | `gdpr.py` |
| `GET` | `/gdpr/files/terms-conditions` | `gdpr.py` |


## Contact

Disponibile solo se `CONTACT_ENABLED` è attivo.

| Metodi | Path | Sorgente |
|---|---|---|
| `POST` | `/mail/contact` | `contact.py` |


## Locales / i18n

Disponibile solo se `SCHEDULA_LOCALE_ENABLED` è attivo.

| Metodi | Path | Sorgente |
|---|---|---|
| `GET` | `/locales/<lang>` | `locale/__init__.py` |
| `POST` | `/locales/<lang>` | `locale/__init__.py` |
| `GET` | `/locales/<language>/<namespace>` | `locale/__init__.py` |
| `GET` | `/locales/languages.json` | `locale/__init__.py` |


## Files generici

Disponibile solo se `FILES_STORAGE_ENABLED` è attivo.

| Metodi | Path | Sorgente |
|---|---|---|
| `GET, POST` | `/file/<category>` | `files.py` |
| `GET, PUT, PATCH, DELETE` | `/file/<category>/<int:id_item>` | `files.py` |
