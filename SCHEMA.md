# Database Schema

This document describes the current database structure used by the application.
It is based on the SQLAlchemy models in `app/models`.

## Overview

- ORM: SQLAlchemy declarative models using `app.db.Base`
- Migrations: Alembic revisions in `alembic/versions`
- Current model tables: `users`, `connectors`

## Tables

### `users`

Stores application user accounts, authentication credentials, profile names,
account status, and authorization role.

Model: `app.models.user.User`

| Column | Type | Nullable | Default | Constraints / Notes |
| --- | --- | --- | --- | --- |
| `id` | `String(36)` | No | Generated UUID string | Primary key |
| `email` | `String(255)` | No | None | Unique, indexed |
| `password_hash` | `String(255)` | No | None | Stores hashed password only |
| `first_name` | `String(255)` | No | None | User profile first name |
| `last_name` | `String(255)` | No | None | User profile last name |
| `status` | `String(50)` | No | `pending` | Application status value |
| `role` | `String(50)` | No | `user` | Application authorization role |
| `created_at` | `DateTime(timezone=True)` | No | Current UTC datetime | Set by ORM on insert |
| `updated_at` | `DateTime(timezone=True)` | No | Current UTC datetime | Set by ORM on insert and update |

#### Indexes

| Name | Columns | Unique | Notes |
| --- | --- | --- | --- |
| `ix_users_email` | `email` | Yes | Created by the model's `unique=True` and `index=True` mapping |

#### Primary Key

- `users.id`

#### Relationships

- `users.id` is referenced by `connectors.user_id`.

#### Application-Level Values

The database stores `status` and `role` as strings. The current model and
operations layer define the following application-level meanings:

| Field | Values / Semantics |
| --- | --- |
| `status` | Defaults to `pending`; user helpers recognize `active`, `inactive`, and `deleted`; `soft_delete()` sets `deleted`. |
| `role` | Defaults to `user`; allowed roles are `user` and `admin`. |

These values are enforced by application code, not by database enum or check
constraints in the current model.

### `connectors`

Stores model connector configuration for a user.

Model: `app.models.connector.Connector`

| Column | Type | Nullable | Default | Constraints / Notes |
| --- | --- | --- | --- | --- |
| `id` | `String(36)` | No | Generated UUID string | Primary key |
| `user_id` | `String(36)` | No | None | Foreign key to `users.id`, indexed |
| `code` | `String(100)` | No | None | User-scoped connector identifier |
| `name` | `String(255)` | No | None | Connector display name |
| `connection_type` | `String(50)` | No | None | Application-level values: `local`, `openai` |
| `local_file_path` | `String(1024)` | Yes | None | Local GGUF file path |
| `embedding_local_file_path` | `String(1024)` | Yes | None | Local embedding model file path |
| `embedding_name` | `String(255)` | Yes | None | Embedding model name |
| `api_key` | `String(255)` | Yes | None | API key for remote connector types |
| `data` | `JSONB` | No | `{}` | Metadata about the connector |
| `created_at` | `DateTime(timezone=True)` | No | Current UTC datetime | Set by ORM on insert; migration has database default |
| `updated_at` | `DateTime(timezone=True)` | No | Current UTC datetime | Set by ORM on insert and update; migration has insert default |

#### Indexes

| Name | Columns | Unique | Notes |
| --- | --- | --- | --- |
| `ix_connectors_user_id` | `user_id` | No | Supports user-scoped connector lookups |
| `uq_connectors_user_id_code` | `user_id`, `code` | Yes | Enforces unique connector codes per user |

#### Primary Key

- `connectors.id`

#### Relationships

- `connectors.user_id` references `users.id`.

#### Application-Level Values

The database stores `connection_type` as a string. The current model defines
the following application-level values: `local` and `openai`.

Connector inference is application behavior and does not add database columns.
Local connector inference requires `local_file_path` to point to a `.gguf`
model. OpenAI connector inference uses the connector `api_key`; the API never
includes `api_key` in connector response payloads.

## Migration Notes

The Alembic history currently creates this schema in six revisions:

| Revision | Change |
| --- | --- |
| `0001_init` | Creates `users` with identity, email, password, name, status, and timestamp columns; creates the unique email index. |
| `0002_add_role_to_users` | Adds the non-null `role` column with a database server default of `user`. |
| `0003_create_connectors` | Creates `connectors` with a user foreign key, connector settings, timestamps, and JSONB metadata. |
| `0004_add_code_to_connectors` | Adds user-scoped connector codes and a unique constraint on `user_id` plus `code`. |
| `0005_rename_openai_type` | Renames the OpenAI connector value from `open-ai` to `openai`. |
| `0006_add_connector_embeddings` | Adds optional embedding model path and name fields to `connectors`. |

## Current Schema Boundaries

- There are no join tables or many-to-many relationships.
- Passwords are represented only by `password_hash`; raw passwords are not stored.
