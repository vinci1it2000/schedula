# API Reference (server)

## Index & Conventions

- The paths below already include the registered `url_prefix` values (e.g. `/item` and `/items` are aliases).
- Some routes exist only when the service is initialized with the related config flags in `basic_app`.
- **Flask-Security** registers internal endpoints not defined in this repo; they are listed in a dedicated block.

## OpenAPI / Docs

| Methods | Path            | Source                |
|---------|-----------------|-----------------------|
| `GET`   | `/docs`         | `openapi/__init__.py` |
| `GET`   | `/openapi.json` | `openapi/__init__.py` |
| `GET`   | `/openapi.yaml` | `openapi/__init__.py` |

## Security – Flask-Security (core)

Mount: `SECURITY_URL_PREFIX` (default: `/user`).

Feature flags (defaults in code): `CONFIRMABLE`, `CHANGEABLE`, `REGISTERABLE`, `RECOVERABLE`, `TRACKABLE`.

### Flask-Security endpoints (auto-registered)

**Note**: paths can vary slightly by Flask-Security(-Too) version and configuration; this is the typical set for enabled
features.

| Methods | Path                    | Source                                                        |
|---------|-------------------------|---------------------------------------------------------------|
| `POST`  | `/user/login`           | `Flask-Security`                                              |
| `POST`  | `/user/logout`          | `Flask-Security`                                              |
| `POST`  | `/user/register`        | `Flask-Security (REGISTERABLE)`                               |
| `GET`   | `/user/confirm/<token>` | `Flask-Security (CONFIRMABLE)`                                |
| `POST`  | `/user/confirm`         | `Flask-Security (CONFIRMABLE) – re-send/trigger (if enabled)` |
| `POST`  | `/user/reset`           | `Flask-Security (RECOVERABLE) – request reset (forgot)`       |
| `POST`  | `/user/reset/<token>`   | `Flask-Security (RECOVERABLE) – perform reset`                |
| `POST`  | `/user/change`          | `Flask-Security (CHANGEABLE) – change password`               |
| `GET`   | `/user/verify`          | `Flask-Security – verify (only if enabled in config)`         |

## Security – Project custom routes

| Methods                 | Path             | Source                 |
|-------------------------|------------------|------------------------|
| `POST, PATCH`           | `/user/edit`     | `security/__init__.py` |
| `GET`                   | `/user/plasmic`  | `security/__init__.py` |
| `GET, POST, PATCH, PUT` | `/user/settings` | `security/__init__.py` |

## Groups / Workspace / RBAC

Default `url_prefix` for Groups service: `/groups`.

| Methods      | Path                        | Source               |
|--------------|-----------------------------|----------------------|
| `GET`        | `/groups`                   | `security/groups.py` |
| `POST`       | `/groups`                   | `security/groups.py` |
| `GET`        | `/groups/<gid>`             | `security/groups.py` |
| `PUT, PATCH` | `/groups/<gid>`             | `security/groups.py` |
| `PATCH`      | `/groups/<gid>/memberships` | `security/groups.py` |

## Casbin Admin Panel

| Methods        | Path                     | Source                    |
|----------------|--------------------------|---------------------------|
| `GET`          | `/admin/casbin/grouping` | `security/admin_panel.py` |
| `POST, DELETE` | `/admin/casbin/grouping` | `security/admin_panel.py` |
| `GET`          | `/admin/casbin/policies` | `security/admin_panel.py` |
| `POST, DELETE` | `/admin/casbin/policies` | `security/admin_panel.py` |

## Items – CRUD

Alias: all routes are mounted on both `/item` and `/items`.

| Methods      | Path                          | Source          |
|--------------|-------------------------------|-----------------|
| `GET`        | `/item/<category>`            | `items/crud.py` |
| `POST`       | `/item/<category>`            | `items/crud.py` |
| `DELETE`     | `/item/<category>/<item_id>`  | `items/crud.py` |
| `GET`        | `/item/<category>/<item_id>`  | `items/crud.py` |
| `PUT, PATCH` | `/item/<category>/<item_id>`  | `items/crud.py` |
| `GET`        | `/items/<category>`           | `items/crud.py` |
| `POST`       | `/items/<category>`           | `items/crud.py` |
| `DELETE`     | `/items/<category>/<item_id>` | `items/crud.py` |
| `GET`        | `/items/<category>/<item_id>` | `items/crud.py` |
| `PUT, PATCH` | `/items/<category>/<item_id>` | `items/crud.py` |

## Items – ACL / Manage

Alias: all routes are mounted on both `/item` and `/items`.

| Methods | Path                                        | Source            |
|---------|---------------------------------------------|-------------------|
| `GET`   | `/item/<category>/<item_id>/acl/publish`    | `items/manage.py` |
| `POST`  | `/item/<category>/<item_id>/acl/publish`    | `items/manage.py` |
| `GET`   | `/item/<category>/<item_id>/acl/share`      | `items/manage.py` |
| `PUT`   | `/item/<category>/<item_id>/acl/share`      | `items/manage.py` |
| `POST`  | `/item/<category>/<item_id>/acl/unpublish`  | `items/manage.py` |
| `GET`   | `/items/<category>/<item_id>/acl/publish`   | `items/manage.py` |
| `POST`  | `/items/<category>/<item_id>/acl/publish`   | `items/manage.py` |
| `GET`   | `/items/<category>/<item_id>/acl/share`     | `items/manage.py` |
| `PUT`   | `/items/<category>/<item_id>/acl/share`     | `items/manage.py` |
| `POST`  | `/items/<category>/<item_id>/acl/unpublish` | `items/manage.py` |

## Items – Files

Alias: all routes are mounted on both `/item-file` and `/items-file`.

| Methods | Path                                | Source           |
|---------|-------------------------------------|------------------|
| `GET`   | `/item-file/<item_id>/<file_name>`  | `items/files.py` |
| `GET`   | `/items-file/<item_id>/<file_name>` | `items/files.py` |

## Schemas

Alias: all routes are mounted on both `/admin/item-schema` and `/admin/items-schema`.

| Methods | Path                                                        | Source            |
|---------|-------------------------------------------------------------|-------------------|
| `GET`   | `/admin/item-schema/`                                       | `items/schema.py` |
| `GET`   | `/admin/item-schema/<category>`                             | `items/schema.py` |
| `POST`  | `/admin/item-schema/<category>/drafts`                      | `items/schema.py` |
| `PUT`   | `/admin/item-schema/<category>/drafts/<version>`            | `items/schema.py` |
| `POST`  | `/admin/item-schema/<category>/drafts/<version>/publish`    | `items/schema.py` |
| `POST`  | `/admin/item-schema/<category>/versions/<version>/disable`  | `items/schema.py` |
| `POST`  | `/admin/item-schema/<category>/versions/<version>/enable`   | `items/schema.py` |
| `GET`   | `/admin/items-schema/`                                      | `items/schema.py` |
| `GET`   | `/admin/items-schema/<category>`                            | `items/schema.py` |
| `POST`  | `/admin/items-schema/<category>/drafts`                     | `items/schema.py` |
| `PUT`   | `/admin/items-schema/<category>/drafts/<version>`           | `items/schema.py` |
| `POST`  | `/admin/items-schema/<category>/drafts/<version>/publish`   | `items/schema.py` |
| `POST`  | `/admin/items-schema/<category>/versions/<version>/disable` | `items/schema.py` |
| `POST`  | `/admin/items-schema/<category>/versions/<version>/enable`  | `items/schema.py` |

## Notifications

Watchers (user-scoped):

| Methods         | Path                                  | Source                 |
|-----------------|---------------------------------------|------------------------|
| `GET, POST`     | `/notification/watchers`              | `notifications/api.py` |
| `PATCH, DELETE` | `/notification/watchers/<watcher_id>` | `notifications/api.py` |

Settings rules (admin):

| Methods         | Path                                           | Source                       |
|-----------------|------------------------------------------------|------------------------------|
| `GET, POST`     | `/admin/notification/settings/rules`           | `notifications/admin_api.py` |
| `PATCH, DELETE` | `/admin/notification/settings/rules/<rule_id>` | `notifications/admin_api.py` |

Templates (admin):

| Methods | Path                                          | Source                       |
|---------|-----------------------------------------------|------------------------------|
| `GET`   | `/admin/notification/templates`               | `notifications/admin_api.py` |
| `GET`   | `/admin/notification/templates/<template_id>` | `notifications/admin_api.py` |
| `POST`  | `/admin/notification/templates`               | `notifications/admin_api.py` |

Admin notify:

| Methods | Path                         | Source                       |
|---------|------------------------------|------------------------------|
| `POST`  | `/admin/notification/notify` | `notifications/admin_api.py` |

## Contracts

Contracts API routes are mounted from the contracts service blueprint.

| Methods      | Path                                      | Source                |
|--------------|-------------------------------------------|-----------------------|
| `POST`       | `/contracts/templates`                    | `contracts/routes.py` |
| `GET`        | `/contracts/templates`                    | `contracts/routes.py` |
| `GET`        | `/contracts/templates/<template_id>`      | `contracts/routes.py` |
| `PUT`        | `/contracts/templates/<template_id>`      | `contracts/routes.py` |
| `POST`       | `/contracts/<template_id>`                | `contracts/routes.py` |
| `GET`        | `/contracts/<contract_id>`                | `contracts/routes.py` |
| `DELETE`     | `/contracts/<contract_id>`                | `contracts/routes.py` |
| `POST, GET`  | `/contracts/<contract_id>/<path:dyn_path>` | `contracts/routes.py` |

## Export

Available only if `SCHEDULA_EXPORT_FORM_ENABLED` is enabled.

| Methods     | Path                       | Source               |
|-------------|----------------------------|----------------------|
| `GET, POST` | `/export-form/<path:form>` | `export/__init__.py` |

## Credits / Billing (Stripe)

Available only if `SCHEDULA_CREDITS_ENABLED` is enabled.

| Methods | Path                                            | Source       |
|---------|-------------------------------------------------|--------------|
| `GET`   | `/user/balance`                               | `credits.py` |
| `GET`   | `/user/balance/<int:wallet_id>`               | `credits.py` |
| `POST`  | `/stripe/create-checkout-session`               | `credits.py` |
| `POST`  | `/stripe/create-customer-portal-session`        | `credits.py` |
| `POST`  | `/stripe/create-customer-pricing-table-session` | `credits.py` |
| `GET`   | `/stripe/session-status/<session_id>`           | `credits.py` |
| `GET`   | `/user/subscription`                          | `credits.py` |
| `GET`   | `/user/subscription/<int:wallet_id>`          | `credits.py` |
| `POST`  | `/stripe/webhooks`                              | `credits.py` |

## GDPR

Available only if `SCHEDULA_GDPR_ENABLED` is enabled.

| Methods | Path                           | Source    |
|---------|--------------------------------|-----------|
| `POST`  | `/gdpr/consent`                | `gdpr.py` |
| `GET`   | `/gdpr/consent/<consent_id>`   | `gdpr.py` |
| `GET`   | `/gdpr/files/cookies-policy`   | `gdpr.py` |
| `GET`   | `/gdpr/files/terms-conditions` | `gdpr.py` |

## Contact

Available only if `CONTACT_ENABLED` is enabled.

| Methods | Path            | Source       |
|---------|-----------------|--------------|
| `POST`  | `/mail/contact` | `contact.py` |

## Locales / i18n

Available only if `SCHEDULA_LOCALE_ENABLED` is enabled.

| Methods | Path                              | Source               |
|---------|-----------------------------------|----------------------|
| `GET`   | `/locales/<lang>`                 | `locale/__init__.py` |
| `POST`  | `/locales/<lang>`                 | `locale/__init__.py` |
| `GET`   | `/locales/<language>/<namespace>` | `locale/__init__.py` |
| `GET`   | `/locales/languages.json`         | `locale/__init__.py` |

## Generic Files

Available only if `FILES_STORAGE_ENABLED` is enabled.

| Methods                   | Path                             | Source     |
|---------------------------|----------------------------------|------------|
| `GET, POST`               | `/file/<category>`               | `files.py` |
| `GET, PUT, PATCH, DELETE` | `/file/<category>/<int:id_item>` | `files.py` |
