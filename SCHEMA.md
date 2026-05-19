# Database Schema

This document describes the current database structure used by the application.
It is based on the SQLAlchemy models in `app/models`.

## Overview

- ORM: SQLAlchemy declarative models using `app.db.Base`
- Migrations: Alembic revisions in `alembic/versions`
- Current model tables: `users`

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

- No foreign keys or ORM relationships are currently defined on `users`.

#### Application-Level Values

The database stores `status` and `role` as strings. The current model and
operations layer define the following application-level meanings:

| Field | Values / Semantics |
| --- | --- |
| `status` | Defaults to `pending`; user helpers recognize `active`, `inactive`, and `deleted`; `soft_delete()` sets `deleted`. |
| `role` | Defaults to `user`; allowed roles are `user` and `admin`. |

These values are enforced by application code, not by database enum or check
constraints in the current model.

## Migration Notes

The Alembic history currently creates this schema in two revisions:

| Revision | Change |
| --- | --- |
| `0001_init` | Creates `users` with identity, email, password, name, status, and timestamp columns; creates the unique email index. |
| `0002_add_role_to_users` | Adds the non-null `role` column with a database server default of `user`. |

## Current Schema Boundaries

- There are no other SQLAlchemy models in `app/models`.
- There are no join tables, foreign keys, or many-to-many relationships.
- Passwords are represented only by `password_hash`; raw passwords are not stored.
