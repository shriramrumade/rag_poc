# AWS Database Onboarding API

## Overview

The AWS Database Onboarding API registers, reads, lists, updates and deletes database connection details stored in DynamoDB in Account A, and drives metadata extraction, data extraction and data loads. It is called by the on-premise API over Direct Connect/VPN with mTLS, forwarding the end user's OIDC token.

Base URL: `https://dbreg.a.internal/v1`

| Operation | Method | Path | Success |
| --- | --- | --- | --- |
| Create database | POST | `/databases` | 201 Created |
| Fetch database | GET | `/databases/{db_id}` | 200 OK |
| List by app ID | GET | `/databases?app_id={app_id}` | 200 OK |
| Update database | PATCH | `/databases/{db_id}` | 200 OK |
| Delete database | DELETE | `/databases/{db_id}` | 204 No Content |
| Start metadata extraction | POST | `/metadata-extractions` | 202 Accepted |
| Metadata extraction status | GET | `/metadata-extractions/{extraction_id}` | 200 OK |
| Fetch metadata | GET | `/metadata?app_id={app_id}&db_id={db_id}` | 200 OK |
| Update table metadata | PATCH | `/metadata/tables/{schema.table}?app_id={app_id}&db_id={db_id}` | 200 OK |
| Create data extraction request | POST | `/data-extractions` | 201 Created |
| Data extraction status | GET | `/data-extractions/{request_id}` | 200 OK |
| Stop data extraction | POST | `/data-extractions/{request_id}/stop` | 202 Accepted |
| Retry data extraction | POST | `/data-extractions/{request_id}/retry` | 201 Created |
| List data extractions | GET | `/data-extractions?app_id={app_id}` | 200 OK |
| Create data load | POST | `/data-loads` | 202 Accepted |
| Data load status | GET | `/data-loads/{load_id}` | 200 OK |
| Stop data load | POST | `/data-loads/{load_id}/stop` | 202 Accepted |
| Retry data load | POST | `/data-loads/{load_id}/retry` | 201 Created |
| List data loads | GET | `/data-loads?app_id={app_id}` | 200 OK |
| Execute data extraction | POST | `/data-extractions/{request_id}/execute` | 202 Accepted |

Common headers on every request:

| Header | Required | Purpose |
| --- | --- | --- |
| `Authorization` | Yes | `Bearer` end-user OIDC token, forwarded by the on-prem API |
| `Accept` | Yes | `application/json` |
| `Content-Type` | POST, PATCH | `application/json` |
| `X-Correlation-Id` | Yes | Trace ID echoed back in the response |
| `Idempotency-Key` | POST | Makes a retried create safe |
| `If-Match` | PATCH, DELETE | Current `version`; prevents overwriting someone else's change |

## Field reference

Clients send the first seven fields; the API sets the rest.

| Field | Type | Required on create | Editable | Rules / sample |
| --- | --- | --- | --- | --- |
| `app_id` | string | Yes | No | Owning application ID, e.g. `APP12345` |
| `db_id` | string | Yes | No | `^[a-z0-9_]{3,64}$`, unique, e.g. `orders_db` |
| `engine` | enum | Yes | Yes | `postgresql`, `mysql`, `mariadb`, `oracle`, `sqlserver` |
| `host` | string | Yes | Yes | Approved DNS suffix or CIDR only |
| `port` | integer | Yes | Yes | Allowed per engine, e.g. `5432` |
| `database` | string | Yes | Yes | `^[A-Za-z0-9_]{1,64}$`, e.g. `orders` |
| `auth_type` | enum | Yes | Yes | `secret` or `iam` |
| `status` | enum | Set by API | Via delete only | `REGISTERED`, `DELETED` |
| `version` | integer | Set by API | Auto | Starts at 1, +1 on each update |
| `created_by` | string | Set by API | No | Taken from the user token |
| `created_at` / `updated_at` | ISO 8601 | Set by API | Auto | UTC timestamps |

## 1. Create database

Registers a new database's connection details in DynamoDB.

**Request**

```http
POST /v1/databases HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
Accept: application/json
Idempotency-Key: 6f1c3a2e-8d41-4b7a-9e0f-2c5d7a1b9e22
X-Correlation-Id: 9b2e7c10-55aa-4f3e-b1d2-0c8e6f4a2d41

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "engine": "postgresql",
  "host": "orders-db.abc123.us-west-2.rds.amazonaws.com",
  "port": 5432,
  "database": "orders",
  "auth_type": "secret"
}
```

**Response (success)**

```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /v1/databases/orders_db
X-Correlation-Id: 9b2e7c10-55aa-4f3e-b1d2-0c8e6f4a2d41

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "engine": "postgresql",
  "host": "orders-db.abc123.us-west-2.rds.amazonaws.com",
  "port": 5432,
  "database": "orders",
  "auth_type": "secret",
  "status": "REGISTERED",
  "version": 1,
  "created_by": "jane.doe@example.com",
  "created_at": "2026-10-27T06:39:00Z",
  "updated_at": "2026-10-27T06:39:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 409 Conflict
Content-Type: application/json
X-Correlation-Id: 9b2e7c10-55aa-4f3e-b1d2-0c8e6f4a2d41

{
  "error": {
    "code": "DB_ID_EXISTS",
    "message": "db_id 'orders_db' is already registered",
    "field": "db_id"
  }
}
```

## 2. Fetch database

Returns one registered database by `db_id`.

**Request**

```http
GET /v1/databases/orders_db HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
X-Correlation-Id: 3d7a1f84-2c6b-4e19-a0d5-8b4f2e7c6a13
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "1"
X-Correlation-Id: 3d7a1f84-2c6b-4e19-a0d5-8b4f2e7c6a13

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "engine": "postgresql",
  "host": "orders-db.abc123.us-west-2.rds.amazonaws.com",
  "port": 5432,
  "database": "orders",
  "auth_type": "secret",
  "status": "REGISTERED",
  "version": 1,
  "created_by": "jane.doe@example.com",
  "created_at": "2026-10-27T06:39:00Z",
  "updated_at": "2026-10-27T06:39:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
X-Correlation-Id: 3d7a1f84-2c6b-4e19-a0d5-8b4f2e7c6a13

{
  "error": {
    "code": "DB_NOT_FOUND",
    "message": "db_id 'orders_db' is not registered",
    "field": "db_id"
  }
}
```

## 3. List databases by app ID

Returns all active databases registered under one `app_id`, newest first. Pass `next_token` back to get the next page.

**Request**

```http
GET /v1/databases?app_id=APP12345&limit=20 HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
X-Correlation-Id: 7e4b2a91-6c3d-4f58-b2e0-1a9d5c8f3b27
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Correlation-Id: 7e4b2a91-6c3d-4f58-b2e0-1a9d5c8f3b27

{
  "app_id": "APP12345",
  "count": 2,
  "items": [
    {
      "db_id": "orders_db",
      "engine": "postgresql",
      "host": "orders-db.abc123.us-west-2.rds.amazonaws.com",
      "port": 5432,
      "database": "orders",
      "auth_type": "secret",
      "status": "REGISTERED",
      "version": 1,
      "created_at": "2026-10-27T06:39:00Z"
    },
    {
      "db_id": "billing_db",
      "engine": "mysql",
      "host": "billing.cluster-xyz789.us-west-2.rds.amazonaws.com",
      "port": 3306,
      "database": "billing",
      "auth_type": "iam",
      "status": "REGISTERED",
      "version": 3,
      "created_at": "2026-10-25T18:12:00Z"
    }
  ],
  "next_token": null
}
```

**Response (error)**

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json
X-Correlation-Id: 7e4b2a91-6c3d-4f58-b2e0-1a9d5c8f3b27

{
  "error": {
    "code": "APP_ID_REQUIRED",
    "message": "query parameter 'app_id' is required",
    "field": "app_id"
  }
}
```

An app with no databases returns `200` with an empty `items` list.

## 4. Update database

Changes one or more editable fields; send only the fields that change. `app_id` and `db_id` cannot be changed. `If-Match` must carry the current `version`.

**Request**

```http
PATCH /v1/databases/orders_db HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
Accept: application/json
If-Match: "1"
X-Correlation-Id: 5a8c3e17-9b2d-4f64-a1c0-7e3d9b5f2a68

{
  "host": "orders-db-v2.abc123.us-west-2.rds.amazonaws.com",
  "auth_type": "iam"
}
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "2"
X-Correlation-Id: 5a8c3e17-9b2d-4f64-a1c0-7e3d9b5f2a68

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "engine": "postgresql",
  "host": "orders-db-v2.abc123.us-west-2.rds.amazonaws.com",
  "port": 5432,
  "database": "orders",
  "auth_type": "iam",
  "status": "REGISTERED",
  "version": 2,
  "created_by": "jane.doe@example.com",
  "created_at": "2026-10-27T06:39:00Z",
  "updated_by": "raj.k@example.com",
  "updated_at": "2026-10-28T15:02:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 412 Precondition Failed
Content-Type: application/json
X-Correlation-Id: 5a8c3e17-9b2d-4f64-a1c0-7e3d9b5f2a68

{
  "error": {
    "code": "VERSION_MISMATCH",
    "message": "orders_db was changed by someone else; fetch it again and retry",
    "field": "version"
  }
}
```

## 5. Delete database

Soft-deletes a registration: the item stays in DynamoDB with `status` set to `DELETED` for audit, and it no longer appears in fetch or list. `If-Match` must carry the current `version`.

**Request**

```http
DELETE /v1/databases/orders_db HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
If-Match: "2"
X-Correlation-Id: 1f6d4b38-7a2e-4c95-b0e8-3d9a6c2f5b71
```

**Response (success)**

```http
HTTP/1.1 204 No Content
X-Correlation-Id: 1f6d4b38-7a2e-4c95-b0e8-3d9a6c2f5b71
```

**Response (error)**

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
X-Correlation-Id: 1f6d4b38-7a2e-4c95-b0e8-3d9a6c2f5b71

{
  "error": {
    "code": "DB_NOT_FOUND",
    "message": "db_id 'orders_db' is not registered",
    "field": "db_id"
  }
}
```

## 6. Start metadata extraction

Starts metadata extraction in Account B for a database registered under an app ID. The call returns `202` because the work runs asynchronously: the EKS service checks that `db_id` belongs to `app_id` in DynamoDB, assumes the role in Account B, and starts the Glue crawler or job there.

**Request**

```http
POST /v1/metadata-extractions HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
Accept: application/json
Idempotency-Key: 8c2f6a14-3e7b-4d90-a5c1-9b4e2d7f6a30
X-Correlation-Id: 4b9e1c72-8d3a-4f06-b7e2-5a1c9f3d8e64

{
  "app_id": "APP12345",
  "db_id": "orders_db"
}
```

**Response (success)**

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
Location: /v1/metadata-extractions/mx-20261027-0001
X-Correlation-Id: 4b9e1c72-8d3a-4f06-b7e2-5a1c9f3d8e64

{
  "extraction_id": "mx-20261027-0001",
  "app_id": "APP12345",
  "db_id": "orders_db",
  "status": "SUBMITTED",
  "submitted_by": "jane.doe@example.com",
  "submitted_at": "2026-10-27T06:48:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 409 Conflict
Content-Type: application/json
X-Correlation-Id: 4b9e1c72-8d3a-4f06-b7e2-5a1c9f3d8e64

{
  "error": {
    "code": "EXTRACTION_IN_PROGRESS",
    "message": "a metadata extraction for 'orders_db' is already running",
    "field": "db_id"
  }
}
```

A `db_id` not registered under that `app_id` returns `404 DB_NOT_FOUND`.

## 7. Metadata extraction status

Returns the current status of a metadata extraction run.

**Request**

```http
GET /v1/metadata-extractions/mx-20261027-0001 HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
X-Correlation-Id: 2e8a5d19-6f4c-4b73-9a0d-c3b7e1f5a826
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Correlation-Id: 2e8a5d19-6f4c-4b73-9a0d-c3b7e1f5a826

{
  "extraction_id": "mx-20261027-0001",
  "app_id": "APP12345",
  "db_id": "orders_db",
  "status": "SUCCEEDED",
  "submitted_by": "jane.doe@example.com",
  "submitted_at": "2026-10-27T06:48:00Z",
  "started_at": "2026-10-27T06:48:20Z",
  "completed_at": "2026-10-27T06:51:05Z",
  "result": {
    "tables_found": 42,
    "tables_added": 40,
    "tables_updated": 2,
    "catalog_database": "orders_raw_catalog"
  },
  "error": null
}
```

**Response (error)**

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
X-Correlation-Id: 2e8a5d19-6f4c-4b73-9a0d-c3b7e1f5a826

{
  "error": {
    "code": "EXTRACTION_NOT_FOUND",
    "message": "extraction 'mx-20261027-0001' does not exist",
    "field": "extraction_id"
  }
}
```

| `status` | Meaning |
| --- | --- |
| `SUBMITTED` | Accepted, not yet started in Account B |
| `RUNNING` | Glue crawler or job is running |
| `SUCCEEDED` | Finished; `result` is filled in |
| `FAILED` | Finished with an error; `error` holds the reason, e.g. `DB_CONNECTION_FAILED` |

## 8. Fetch metadata

Returns all metadata collected for a database registered under an app ID: tables, columns with PII tags, and relationships between tables. Pass `next_token` back to page through large schemas.

**Request**

```http
GET /v1/metadata?app_id=APP12345&db_id=orders_db&limit=50 HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
X-Correlation-Id: 6c1f9a37-4e8b-4d25-b3a6-0f7d2e9c5b14
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Correlation-Id: 6c1f9a37-4e8b-4d25-b3a6-0f7d2e9c5b14

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "catalog_database": "orders_raw_catalog",
  "last_extraction_id": "mx-20261027-0001",
  "extracted_at": "2026-10-27T06:51:05Z",
  "table_count": 2,
  "tables": [
    {
      "schema": "public",
      "table": "orders",
      "version": 1,
      "row_count_estimate": 1250000,
      "primary_key": ["order_id"],
      "columns": [
        {
          "name": "order_id", "type": "bigint", "nullable": false, "position": 1,
          "is_sensitive": false, "pii_type": null, "classification": "INTERNAL",
          "pii_rule": null,
          "detection": { "method": "AUTO", "confidence": 0.99 }
        },
        {
          "name": "customer_id", "type": "bigint", "nullable": false, "position": 2,
          "is_sensitive": false, "pii_type": null, "classification": "INTERNAL",
          "pii_rule": null,
          "detection": { "method": "AUTO", "confidence": 0.97 }
        },
        {
          "name": "amount", "type": "decimal(12,2)", "nullable": true, "position": 3,
          "is_sensitive": true, "pii_type": null, "classification": "CONFIDENTIAL",
          "pii_rule": { "rule_id": "FIN-001", "action": "NONE", "access": "finance-readers" },
          "detection": { "method": "MANUAL", "confidence": null }
        },
        {
          "name": "updated_at", "type": "timestamp", "nullable": false, "position": 4,
          "is_sensitive": false, "pii_type": null, "classification": "INTERNAL",
          "pii_rule": null,
          "detection": { "method": "AUTO", "confidence": 0.99 }
        }
      ]
    },
    {
      "schema": "public",
      "table": "customers",
      "version": 3,
      "row_count_estimate": 84000,
      "primary_key": ["customer_id"],
      "columns": [
        {
          "name": "customer_id", "type": "bigint", "nullable": false, "position": 1,
          "is_sensitive": false, "pii_type": null, "classification": "INTERNAL",
          "pii_rule": null,
          "detection": { "method": "AUTO", "confidence": 0.98 }
        },
        {
          "name": "name", "type": "varchar(200)", "nullable": false, "position": 2,
          "is_sensitive": true, "pii_type": "PERSON_NAME", "classification": "RESTRICTED",
          "pii_rule": { "rule_id": "PII-002", "action": "MASK", "mask_pattern": "J*** D**" },
          "detection": { "method": "AUTO", "confidence": 0.94 }
        },
        {
          "name": "email", "type": "varchar(320)", "nullable": true, "position": 3,
          "is_sensitive": true, "pii_type": "EMAIL", "classification": "RESTRICTED",
          "pii_rule": { "rule_id": "PII-001", "action": "HASH", "algorithm": "SHA-256" },
          "detection": { "method": "AUTO", "confidence": 0.99 }
        }
      ]
    }
  ],
  "relationships": [
    {
      "name": "fk_orders_customer",
      "type": "MANY_TO_ONE",
      "from": { "schema": "public", "table": "orders",    "columns": ["customer_id"] },
      "to":   { "schema": "public", "table": "customers", "columns": ["customer_id"] },
      "on_delete": "RESTRICT",
      "on_update": "CASCADE"
    }
  ],
  "next_token": null
}
```

**Response (error)**

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
X-Correlation-Id: 6c1f9a37-4e8b-4d25-b3a6-0f7d2e9c5b14

{
  "error": {
    "code": "METADATA_NOT_FOUND",
    "message": "no completed metadata extraction for 'orders_db'",
    "field": "db_id"
  }
}
```

Column governance fields:

| Field | Values | Meaning |
| --- | --- | --- |
| `is_sensitive` | `true` / `false` | Column holds personal or confidential data |
| `pii_type` | `EMAIL`, `PERSON_NAME`, `PHONE`, `SSN`, `ADDRESS`, `DOB`, `CREDIT_CARD`, `IP_ADDRESS`, `null` | Kind of PII detected |
| `classification` | `PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED` | Data classification level |
| `pii_rule.rule_id` | e.g. `PII-001` | Governance rule that applies |
| `pii_rule.action` | `NONE`, `MASK`, `HASH`, `REDACT`, `TOKENIZE`, `DROP` | What the data extraction job must do |
| `detection.method` | `AUTO` / `MANUAL` | Found by a scan or tagged by a person |
| `detection.confidence` | 0–1 or `null` | Score from automatic detection |

Relationship fields:

| Field | Meaning |
| --- | --- |
| `name` | Foreign key constraint name in the source database |
| `type` | `MANY_TO_ONE`, or `ONE_TO_ONE` when the FK columns are also unique |
| `from` / `to` | Child table and columns → parent table and columns; composite keys list columns in order |
| `on_delete` / `on_update` | Referential actions defined on the FK |

Sources: tables and columns come from the Glue Data Catalog in Account B. Primary and foreign keys come from a Glue job querying the database's system tables (`information_schema` on PostgreSQL/MySQL, `ALL_CONSTRAINTS` on Oracle, `sys.foreign_keys` on SQL Server), since crawlers don't capture them. PII tags come from Glue sensitive data detection on sampled rows, mapped to `classification` and `pii_rule` through a rules table.

## 9. Update table metadata

Corrects PII and classification tags for one table at a time; send only the columns and fields that change. `If-Match` must carry the table's current `version`.

**Request**

```http
PATCH /v1/metadata/tables/public.customers?app_id=APP12345&db_id=orders_db HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
Accept: application/json
If-Match: "3"
X-Correlation-Id: 8a3d6f21-5c9e-4b07-a4f2-1e6b9d3c7a58

{
  "description": "Customer master data",
  "columns": [
    {
      "name": "name",
      "is_sensitive": true,
      "pii_type": "PERSON_NAME",
      "classification": "RESTRICTED",
      "pii_rule": { "rule_id": "PII-003", "action": "REDACT" }
    },
    {
      "name": "email",
      "classification": "CONFIDENTIAL"
    }
  ],
  "change_reason": "Name must be redacted, not masked, per privacy review"
}
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json
ETag: "4"
X-Correlation-Id: 8a3d6f21-5c9e-4b07-a4f2-1e6b9d3c7a58

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "schema": "public",
  "table": "customers",
  "description": "Customer master data",
  "version": 4,
  "columns": [
    {
      "name": "customer_id", "type": "bigint", "nullable": false, "position": 1,
      "is_sensitive": false, "pii_type": null, "classification": "INTERNAL",
      "pii_rule": null,
      "detection": { "method": "AUTO", "confidence": 0.98 }
    },
    {
      "name": "name", "type": "varchar(200)", "nullable": false, "position": 2,
      "is_sensitive": true, "pii_type": "PERSON_NAME", "classification": "RESTRICTED",
      "pii_rule": { "rule_id": "PII-003", "action": "REDACT" },
      "detection": { "method": "MANUAL", "confidence": null }
    },
    {
      "name": "email", "type": "varchar(320)", "nullable": true, "position": 3,
      "is_sensitive": true, "pii_type": "EMAIL", "classification": "CONFIDENTIAL",
      "pii_rule": { "rule_id": "PII-001", "action": "HASH", "algorithm": "SHA-256" },
      "detection": { "method": "MANUAL", "confidence": null }
    }
  ],
  "updated_by": "priya.s@example.com",
  "updated_at": "2026-10-27T06:55:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json
X-Correlation-Id: 8a3d6f21-5c9e-4b07-a4f2-1e6b9d3c7a58

{
  "error": {
    "code": "COLUMN_NOT_FOUND",
    "message": "column 'phone' does not exist in public.customers",
    "field": "columns[2].name"
  }
}
```

Rules:

- One table per call, named in the path as `schema.table`.
- Editable: `description` on the table; `is_sensitive`, `pii_type`, `classification`, `pii_rule` on columns.
- Not editable: `type`, `nullable`, `position`, primary keys and relationships, which come from the source database.
- Edited columns switch to `detection.method: MANUAL` and keep their tags when metadata is extracted again.
- `change_reason` is stored in an audit log with the user and timestamp.

## 10. Create data extraction request

Creates a unique extraction request in DynamoDB (Account A) from a list of tables, their relationships, an optional query and filters.

**Request**

```http
POST /v1/data-extractions HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
Idempotency-Key: 4f8b2c61-9d3e-4a75-b0c8-6e1a7d5f2b93
X-Correlation-Id: c7e2a948-1b5f-4d36-9a0e-8f3c6b2d1e75

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "tables": ["public.orders", "public.customers"],
  "relationships": [
    {
      "from": "public.orders.customer_id",
      "to": "public.customers.customer_id",
      "join_type": "INNER"
    }
  ],
  "query": "SELECT o.order_id, o.amount, o.updated_at, c.email FROM public.orders o INNER JOIN public.customers c ON o.customer_id = c.customer_id WHERE o.updated_at BETWEEN :start_date AND :end_date",
  "parameters": {
    "start_date": "2026-07-01T00:00:00Z",
    "end_date": "2026-09-30T23:59:59Z"
  },
  "filters": [
    { "column": "public.orders.amount", "operator": "GT", "values": [0] },
    { "column": "public.customers.email", "operator": "IS_NOT_NULL", "values": [] }
  ]
}
```

**Response (success)**

```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /v1/data-extractions/dx-20261027-7f3a9c
X-Correlation-Id: c7e2a948-1b5f-4d36-9a0e-8f3c6b2d1e75

{
  "request_id": "dx-20261027-7f3a9c",
  "app_id": "APP12345",
  "db_id": "orders_db",
  "status": "SUBMITTED",
  "submitted_by": "jane.doe@example.com",
  "submitted_at": "2026-10-27T07:00:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/json
X-Correlation-Id: c7e2a948-1b5f-4d36-9a0e-8f3c6b2d1e75

{
  "error": {
    "code": "INVALID_QUERY",
    "message": "only a single SELECT statement is allowed",
    "field": "query"
  }
}
```

Rules:

- `tables` and `relationships` must exist in the fetched metadata.
- `query` is optional; without it, the job builds the `SELECT` from `tables`, `relationships` and `filters`.
- With `query`, only a single `SELECT` is accepted, and every value goes in through `:named` `parameters`, never concatenated into the SQL.
- `filters` apply on top of either path and are combined with AND. Operators: `EQ`, `NE`, `GT`, `GTE`, `LT`, `LTE`, `IN`, `NOT_IN`, `BETWEEN`, `LIKE`, `IS_NULL`, `IS_NOT_NULL`.
- Stored in DynamoDB table `extraction_requests`, partition key `request_id`, written with `attribute_not_exists(request_id)`; a retry with the same `Idempotency-Key` returns the original `request_id`.

## 11. Data extraction status

Returns the current state and progress of an extraction request.

**Request**

```http
GET /v1/data-extractions/dx-20261027-7f3a9c HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
X-Correlation-Id: 0a7d3f52-6e1b-4c98-b2a4-9f5e8c1d7b36
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Correlation-Id: 0a7d3f52-6e1b-4c98-b2a4-9f5e8c1d7b36

{
  "request_id": "dx-20261027-7f3a9c",
  "app_id": "APP12345",
  "db_id": "orders_db",
  "status": "RUNNING",
  "glue_job_run_id": "jr_4b8e2f9a1c7d...",
  "progress": { "rows_extracted": 640000, "percent": 52 },
  "submitted_at": "2026-10-27T07:00:00Z",
  "started_at": "2026-10-27T07:00:40Z",
  "completed_at": null,
  "output": null,
  "error": null
}
```

When `status` is `SUCCEEDED`, `output` is filled in:

```json
"output": {
  "s3_path": "s3://bucket-b/extracts/APP12345/orders_db/dx-20261027-7f3a9c/",
  "format": "parquet",
  "row_count": 1231050,
  "file_count": 8
}
```

**Response (error)**

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{ "error": { "code": "REQUEST_NOT_FOUND", "message": "request 'dx-20261027-7f3a9c' does not exist", "field": "request_id" } }
```

| `status` | Meaning |
| --- | --- |
| `SUBMITTED` | Stored in DynamoDB, not yet started |
| `RUNNING` | Glue job running in Account B |
| `STOPPING` | Stop requested, waiting for Glue to halt |
| `STOPPED` | Stopped by a user |
| `SUCCEEDED` | Finished; `output` filled in |
| `FAILED` | Finished with an error; `error` filled in |

## 12. Stop data extraction

Stops a submitted or running extraction. A `SUBMITTED` request goes straight to `STOPPED`; a `RUNNING` one goes to `STOPPING` while the service calls Glue `BatchStopJobRun` in Account B, then `STOPPED` once Glue confirms.

**Request**

```http
POST /v1/data-extractions/dx-20261027-7f3a9c/stop HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
X-Correlation-Id: 5d2b8e14-9a6f-4c37-a1e0-3b7c9f4d6a82

{ "reason": "Wrong date range submitted" }
```

**Response (success)**

```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "request_id": "dx-20261027-7f3a9c",
  "status": "STOPPING",
  "stop_requested_by": "jane.doe@example.com",
  "stop_requested_at": "2026-10-27T07:03:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{ "error": { "code": "NOT_STOPPABLE", "message": "request is already SUCCEEDED", "field": "status" } }
```

## 13. Retry data extraction

Re-runs a `FAILED` or `STOPPED` request as a new request with the same tables, query and filters.

**Request**

```http
POST /v1/data-extractions/dx-20261027-7f3a9c/retry HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Idempotency-Key: 9e3c7a21-4b8d-4f60-b5e2-1d6a9c3f8b47
X-Correlation-Id: 3f9a6c27-8b4e-4d15-a0c3-7e2d5b1f9a64
```

**Response (success)**

```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /v1/data-extractions/dx-20261027-b81e4d

{
  "request_id": "dx-20261027-b81e4d",
  "retry_of": "dx-20261027-7f3a9c",
  "status": "SUBMITTED",
  "submitted_at": "2026-10-27T07:05:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{ "error": { "code": "NOT_RETRYABLE", "message": "only FAILED or STOPPED requests can be retried", "field": "status" } }
```

## 14. List data extractions

Lists extraction requests for an app ID, optionally filtered by `db_id` and `status`, newest first.

**Request**

```http
GET /v1/data-extractions?app_id=APP12345&db_id=orders_db&status=RUNNING&limit=20 HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
X-Correlation-Id: 8b1e4d93-2c7a-4f58-b6d0-5a9f3e7c2b15
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "count": 1,
  "items": [
    {
      "request_id": "dx-20261027-7f3a9c",
      "status": "RUNNING",
      "submitted_by": "jane.doe@example.com",
      "submitted_at": "2026-10-27T07:00:00Z",
      "progress": { "percent": 52 }
    }
  ],
  "next_token": null
}
```

**Response (error)**

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{ "error": { "code": "APP_ID_REQUIRED", "message": "query parameter 'app_id' is required", "field": "app_id" } }
```

## 15. Create data load

Loads the output of a completed extraction request into a target, under a new unique `load_id`.

**Request**

```http
POST /v1/data-loads HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
Idempotency-Key: 2a6e9c15-7d3b-4f82-a0b4-8c1f5e3d9a76
X-Correlation-Id: e4b7d2a6-3c9f-4e18-b5a1-6d0c8f2e7b39

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "request_id": "dx-20261027-7f3a9c",
  "target": {
    "type": "REDSHIFT",
    "target_id": "finance_dw",
    "schema": "finance",
    "table": "orders_q3"
  },
  "load_mode": "UPSERT",
  "merge_keys": ["order_id"],
  "create_table_if_missing": true
}
```

**Response (success)**

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
Location: /v1/data-loads/dl-20261027-3c9e1a
X-Correlation-Id: e4b7d2a6-3c9f-4e18-b5a1-6d0c8f2e7b39

{
  "load_id": "dl-20261027-3c9e1a",
  "app_id": "APP12345",
  "db_id": "orders_db",
  "request_id": "dx-20261027-7f3a9c",
  "status": "SUBMITTED",
  "submitted_by": "jane.doe@example.com",
  "submitted_at": "2026-10-27T07:02:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 409 Conflict
Content-Type: application/json
X-Correlation-Id: e4b7d2a6-3c9f-4e18-b5a1-6d0c8f2e7b39

{
  "error": {
    "code": "EXTRACTION_NOT_COMPLETE",
    "message": "request 'dx-20261027-7f3a9c' is RUNNING; only SUCCEEDED extractions can be loaded",
    "field": "request_id"
  }
}
```

Rules:

- `request_id` must be a `SUCCEEDED` extraction under the same `app_id` and `db_id`; the load reads its S3 output.
- `target.type`: `REDSHIFT`, `S3_ICEBERG`, `RDS` or another registered database. `target_id` points to a pre-registered target, so no target credentials travel in the request.
- `load_mode`: `APPEND` adds rows, `OVERWRITE` replaces the table, `UPSERT` updates matching rows and inserts new ones (requires `merge_keys`).
- Stored in DynamoDB table `data_loads`, partition key `load_id`; runs as a Glue job in Account B.

## 16. Data load status

Returns the current state and progress of a data load. `status` values are the same as for extractions.

**Request**

```http
GET /v1/data-loads/dl-20261027-3c9e1a HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
X-Correlation-Id: 7c4a1e86-2d9b-4f35-a8e0-3b6f9d2c5a71
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json
X-Correlation-Id: 7c4a1e86-2d9b-4f35-a8e0-3b6f9d2c5a71

{
  "load_id": "dl-20261027-3c9e1a",
  "app_id": "APP12345",
  "db_id": "orders_db",
  "request_id": "dx-20261027-7f3a9c",
  "target": { "type": "REDSHIFT", "target_id": "finance_dw", "schema": "finance", "table": "orders_q3" },
  "load_mode": "UPSERT",
  "status": "RUNNING",
  "glue_job_run_id": "jr_9d3f7a2e6b1c...",
  "progress": { "rows_loaded": 512000, "percent": 41 },
  "submitted_at": "2026-10-27T07:02:00Z",
  "started_at": "2026-10-27T07:02:35Z",
  "completed_at": null,
  "result": null,
  "error": null
}
```

When `status` is `SUCCEEDED`, `result` is filled in:

```json
"result": { "rows_inserted": 1180400, "rows_updated": 50650, "rows_rejected": 0 }
```

**Response (error)**

```http
HTTP/1.1 404 Not Found
Content-Type: application/json

{ "error": { "code": "LOAD_NOT_FOUND", "message": "load 'dl-20261027-3c9e1a' does not exist", "field": "load_id" } }
```

## 17. Stop data load

Stops a submitted or running data load. A stopped `UPSERT` or `APPEND` load may leave partial rows in the target; load into a staging table and swap at the end if you need all-or-nothing.

**Request**

```http
POST /v1/data-loads/dl-20261027-3c9e1a/stop HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
X-Correlation-Id: 1b8e5c37-6a2d-4f94-b3e7-0c9a4d8f2e15

{ "reason": "Wrong target table" }
```

**Response (success)**

```http
HTTP/1.1 202 Accepted
Content-Type: application/json

{
  "load_id": "dl-20261027-3c9e1a",
  "status": "STOPPING",
  "stop_requested_by": "jane.doe@example.com",
  "stop_requested_at": "2026-10-27T07:04:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{ "error": { "code": "NOT_STOPPABLE", "message": "load is already SUCCEEDED", "field": "status" } }
```

## 18. Retry data load

Re-runs a `FAILED` or `STOPPED` load as a new load with the same settings.

**Request**

```http
POST /v1/data-loads/dl-20261027-3c9e1a/retry HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Idempotency-Key: 5f2a8d64-1c7e-4b39-a6d0-9e3b7c5f1a28
X-Correlation-Id: 9a3d6b18-4e7c-4f21-b8a5-2d0f6c9e3b74
```

**Response (success)**

```http
HTTP/1.1 201 Created
Content-Type: application/json
Location: /v1/data-loads/dl-20261027-e47b2f

{
  "load_id": "dl-20261027-e47b2f",
  "retry_of": "dl-20261027-3c9e1a",
  "status": "SUBMITTED",
  "submitted_at": "2026-10-27T07:06:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 409 Conflict
Content-Type: application/json

{ "error": { "code": "NOT_RETRYABLE", "message": "only FAILED or STOPPED loads can be retried", "field": "status" } }
```

## 19. List data loads

Lists data loads for an app ID, newest first. `db_id` and `status` are optional; `status` takes a comma-separated list, e.g. `status=SUBMITTED,RUNNING` for all active loads.

**Request**

```http
GET /v1/data-loads?app_id=APP12345&status=RUNNING&limit=20 HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Accept: application/json
X-Correlation-Id: 4e9c2a71-8b5d-4f06-a3e1-7c6b0d9f5a23
```

**Response (success)**

```http
HTTP/1.1 200 OK
Content-Type: application/json

{
  "app_id": "APP12345",
  "count": 2,
  "items": [
    {
      "load_id": "dl-20261027-3c9e1a",
      "db_id": "orders_db",
      "request_id": "dx-20261027-7f3a9c",
      "target": { "type": "REDSHIFT", "target_id": "finance_dw", "table": "finance.orders_q3" },
      "status": "RUNNING",
      "progress": { "percent": 41 },
      "submitted_by": "jane.doe@example.com",
      "submitted_at": "2026-10-27T07:02:00Z"
    },
    {
      "load_id": "dl-20261026-8a2f6d",
      "db_id": "billing_db",
      "request_id": "dx-20261026-c3d91b",
      "target": { "type": "S3_ICEBERG", "target_id": "lake_raw", "table": "billing.invoices" },
      "status": "RUNNING",
      "progress": { "percent": 87 },
      "submitted_by": "raj.k@example.com",
      "submitted_at": "2026-10-26T22:40:00Z"
    }
  ],
  "next_token": null
}
```

**Response (error)**

```http
HTTP/1.1 400 Bad Request
Content-Type: application/json

{ "error": { "code": "APP_ID_REQUIRED", "message": "query parameter 'app_id' is required", "field": "app_id" } }
```

Served by a GSI on `app_id` (sort key `submitted_at`) filtered by `status`; a sparse GSI on `app_id#status` is cheaper if "all running" is queried often.

## 20. Execute data extraction

Starts the Glue job in Account B for a stored extraction request. Only `SUBMITTED` requests can be executed.

**Request**

```http
POST /v1/data-extractions/dx-20261027-7f3a9c/execute HTTP/1.1
Host: dbreg.a.internal
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
Content-Type: application/json
Idempotency-Key: 7b3e9a52-1d6c-4f84-b2a0-5c8e3f1d7a96
X-Correlation-Id: 2c9f6e41-7a3b-4d58-a1e6-0b4d8c2f5e93

{
  "app_id": "APP12345",
  "db_id": "orders_db",
  "output": {
    "format": "parquet",
    "target_s3_path": "s3://bucket-b/extracts/APP12345/orders_db/"
  },
  "apply_pii_rules": true
}
```

**Response (success)**

```http
HTTP/1.1 202 Accepted
Content-Type: application/json
Location: /v1/data-extractions/dx-20261027-7f3a9c
X-Correlation-Id: 2c9f6e41-7a3b-4d58-a1e6-0b4d8c2f5e93

{
  "request_id": "dx-20261027-7f3a9c",
  "app_id": "APP12345",
  "db_id": "orders_db",
  "status": "RUNNING",
  "glue_job_name": "data-extract-job",
  "glue_job_run_id": "jr_4b8e2f9a1c7d...",
  "executed_by": "jane.doe@example.com",
  "executed_at": "2026-10-27T07:13:00Z"
}
```

**Response (error)**

```http
HTTP/1.1 409 Conflict
Content-Type: application/json
X-Correlation-Id: 2c9f6e41-7a3b-4d58-a1e6-0b4d8c2f5e93

{
  "error": {
    "code": "NOT_EXECUTABLE",
    "message": "request 'dx-20261027-7f3a9c' is RUNNING; only SUBMITTED requests can be executed",
    "field": "status"
  }
}
```

On execute, the service:

1. Checks the request is `SUBMITTED` and belongs to `app_id` and `db_id`.
2. Reads the request and the database record from DynamoDB.
3. Assumes `GlueInvokerRole` in Account B.
4. Calls `glue:StartJobRun` on `data-extract-job` with the arguments in the next section.
5. Saves `glue_job_run_id` and sets `status: RUNNING`; progress is tracked through the status call.

With `apply_pii_rules: true`, each column's `pii_rule` action (mask, hash, redact or drop) is applied to the output.

## Glue execution calls (Account B)

The EKS service in Account A runs every step through Glue in Account B. It assumes `GlueInvokerRole` there and calls the Glue API.

**Shared helper (EKS service, Python)**

```python
import json, boto3

def glue_client(account_id, region, session_name):
    c = boto3.client("sts").assume_role(
        RoleArn=f"arn:aws:iam::{account_id}:role/GlueInvokerRole",
        RoleSessionName=session_name,
        ExternalId="dbreg-ext-id",
    )["Credentials"]
    return boto3.client("glue", region_name=region,
        aws_access_key_id=c["AccessKeyId"],
        aws_secret_access_key=c["SecretAccessKey"],
        aws_session_token=c["SessionToken"])
```

### Metadata extraction execution

Metadata extraction takes two Glue calls. The crawler fills the Data Catalog with tables and columns. The metadata job adds primary and foreign keys and runs PII detection.

**a) Point the crawler at the database, then start it**

```http
POST / HTTP/1.1
Host: glue.us-west-2.amazonaws.com
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSGlue.UpdateCrawler
X-Amz-Security-Token: <session token>
Authorization: AWS4-HMAC-SHA256 ...

{
  "Name": "metadata-crawler-orders_db",
  "Role": "arn:aws:iam::222233334444:role/GlueCrawlerRole",
  "DatabaseName": "orders_raw_catalog",
  "Targets": {
    "JdbcTargets": [
      {
        "ConnectionName": "conn-orders_db",
        "Path": "orders/public/%",
        "Exclusions": ["*_tmp", "*_bkp"]
      }
    ]
  }
}
```

```http
POST / HTTP/1.1
Host: glue.us-west-2.amazonaws.com
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSGlue.StartCrawler
X-Amz-Security-Token: <session token>
Authorization: AWS4-HMAC-SHA256 ...

{ "Name": "metadata-crawler-orders_db" }
```

```http
HTTP/1.1 200 OK
Content-Type: application/x-amz-json-1.1

{}
```

A crawler run has no run ID. Track it with `GetCrawler` (State: `RUNNING`, then `READY`) and `GetCrawlerMetrics`.

**b) Start the metadata job (keys and PII)**

```http
POST / HTTP/1.1
Host: glue.us-west-2.amazonaws.com
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSGlue.StartJobRun
X-Amz-Security-Token: <session token>
Authorization: AWS4-HMAC-SHA256 ...

{
  "JobName": "metadata-enrich-job",
  "Arguments": {
    "--extraction_id": "mx-20261027-0001",
    "--app_id": "APP12345",
    "--db_id": "orders_db",
    "--engine": "postgresql",
    "--jdbc_url": "jdbc:postgresql://orders-db.abc123.us-west-2.rds.amazonaws.com:5432/orders?ssl=true&sslmode=require",
    "--auth_type": "secret",
    "--secret_name": "glue-db/orders_db",
    "--catalog_database": "orders_raw_catalog",
    "--include_schemas": "public",
    "--pii_sample_rows": "1000",
    "--output_path": "s3://bucket-b/metadata/APP12345/orders_db/mx-20261027-0001/",
    "--correlation_id": "4b9e1c72-8d3a-4f06-b7e2-5a1c9f3d8e64"
  },
  "WorkerType": "G.1X",
  "NumberOfWorkers": 2,
  "Timeout": 60
}
```

```http
HTTP/1.1 200 OK
Content-Type: application/x-amz-json-1.1

{ "JobRunId": "jr_7c2e9a4f1b8d..." }
```

```python
def start_metadata_extraction(mx, db, corr_id):
    glue = glue_client(db["target_account_id"], db["region"], f"meta-{mx['extraction_id']}")
    crawler = f"metadata-crawler-{db['db_id']}"
    glue.update_crawler(
        Name=crawler,
        Role=f"arn:aws:iam::{db['target_account_id']}:role/GlueCrawlerRole",
        DatabaseName=mx["catalog_database"],
        Targets={"JdbcTargets": [{
            "ConnectionName": f"conn-{db['db_id']}",
            "Path": f"{db['database']}/public/%",
            "Exclusions": mx.get("exclude_patterns", []),
        }]},
    )
    glue.start_crawler(Name=crawler)

    args = {
        "--extraction_id": mx["extraction_id"],
        "--app_id": db["app_id"], "--db_id": db["db_id"],
        "--engine": db["engine"], "--jdbc_url": db["jdbc_url"],
        "--auth_type": db["auth_type"],
        "--catalog_database": mx["catalog_database"],
        "--include_schemas": "public",
        "--pii_sample_rows": "1000",
        "--output_path": f"s3://bucket-b/metadata/{db['app_id']}/{db['db_id']}/{mx['extraction_id']}/",
        "--correlation_id": corr_id,
    }
    if db["auth_type"] == "secret":
        args["--secret_name"] = db["secret_name"]
    else:
        args["--db_user"] = db["db_user"]

    run = glue.start_job_run(JobName="metadata-enrich-job", Arguments=args,
                             WorkerType="G.1X", NumberOfWorkers=2, Timeout=60)
    return {"crawler_name": crawler, "job_run_id": run["JobRunId"]}
```

The extraction counts as `SUCCEEDED` only when the crawler is back to `READY` and the job run has `SUCCEEDED`.

### Data extraction execution

```http
POST / HTTP/1.1
Host: glue.us-west-2.amazonaws.com
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSGlue.StartJobRun
X-Amz-Date: 20261027T071300Z
X-Amz-Security-Token: <session token from AssumeRole into Account B>
Authorization: AWS4-HMAC-SHA256 Credential=ASIA.../20261027/us-west-2/glue/aws4_request, SignedHeaders=..., Signature=...

{
  "JobName": "data-extract-job",
  "Arguments": {
    "--request_id": "dx-20261027-7f3a9c",
    "--app_id": "APP12345",
    "--db_id": "orders_db",
    "--engine": "postgresql",
    "--jdbc_url": "jdbc:postgresql://orders-db.abc123.us-west-2.rds.amazonaws.com:5432/orders?ssl=true&sslmode=require",
    "--auth_type": "secret",
    "--secret_name": "glue-db/orders_db",
    "--extraction_spec": "{\"tables\":[\"public.orders\",\"public.customers\"],\"relationships\":[{\"from\":\"public.orders.customer_id\",\"to\":\"public.customers.customer_id\",\"join_type\":\"INNER\"}],\"query\":\"SELECT o.order_id, o.amount, o.updated_at, c.email FROM public.orders o INNER JOIN public.customers c ON o.customer_id = c.customer_id WHERE o.updated_at BETWEEN :start_date AND :end_date\",\"parameters\":{\"start_date\":\"2026-07-01T00:00:00Z\",\"end_date\":\"2026-09-30T23:59:59Z\"},\"filters\":[{\"column\":\"public.orders.amount\",\"operator\":\"GT\",\"values\":[0]},{\"column\":\"public.customers.email\",\"operator\":\"IS_NOT_NULL\",\"values\":[]}]}",
    "--pii_rules": "[{\"column\":\"public.customers.email\",\"action\":\"HASH\",\"algorithm\":\"SHA-256\"}]",
    "--output_format": "parquet",
    "--output_path": "s3://bucket-b/extracts/APP12345/orders_db/dx-20261027-7f3a9c/",
    "--correlation_id": "2c9f6e41-7a3b-4d58-a1e6-0b4d8c2f5e93"
  },
  "WorkerType": "G.1X",
  "NumberOfWorkers": 5,
  "Timeout": 120
}
```

```http
HTTP/1.1 200 OK
Content-Type: application/x-amz-json-1.1

{ "JobRunId": "jr_4b8e2f9a1c7d3e6f0a5b9c2d8e1f4a7b3c6d9e0f2a5b8c1d4e7f0a3b6c9d2e5f" }
```

Error example (mapped to API `429`, or the request stays queued and is retried):

```http
HTTP/1.1 400 Bad Request
Content-Type: application/x-amz-json-1.1

{
  "__type": "ConcurrentRunsExceededException",
  "Message": "Concurrent runs exceeded for data-extract-job"
}
```

```python
def start_extraction(req, db, pii_rules, corr_id):
    glue = glue_client(db["target_account_id"], db["region"], f"exec-{req['request_id']}")
    spec = {k: req[k] for k in ("tables", "relationships", "query", "parameters", "filters") if k in req}
    args = {
        "--request_id": req["request_id"],
        "--app_id": req["app_id"],
        "--db_id": req["db_id"],
        "--engine": db["engine"],
        "--jdbc_url": db["jdbc_url"],
        "--auth_type": db["auth_type"],
        "--extraction_spec": json.dumps(spec),
        "--pii_rules": json.dumps(pii_rules),
        "--output_format": req["output"]["format"],
        "--output_path": f"{req['output']['target_s3_path']}{req['request_id']}/",
        "--correlation_id": corr_id,
    }
    if db["auth_type"] == "secret":
        args["--secret_name"] = db["secret_name"]
    else:
        args["--db_user"] = db["db_user"]

    run = glue.start_job_run(JobName="data-extract-job", Arguments=args,
                             WorkerType="G.1X", NumberOfWorkers=5, Timeout=120)
    return run["JobRunId"]
```

For a large query or many filters, write the spec as JSON to S3 in Account B and pass `--extraction_spec_path` instead of the inline string.

### Data load execution

```http
POST / HTTP/1.1
Host: glue.us-west-2.amazonaws.com
Content-Type: application/x-amz-json-1.1
X-Amz-Target: AWSGlue.StartJobRun
X-Amz-Security-Token: <session token>
Authorization: AWS4-HMAC-SHA256 ...

{
  "JobName": "data-load-job",
  "Arguments": {
    "--load_id": "dl-20261027-3c9e1a",
    "--request_id": "dx-20261027-7f3a9c",
    "--app_id": "APP12345",
    "--source_path": "s3://bucket-b/extracts/APP12345/orders_db/dx-20261027-7f3a9c/",
    "--source_format": "parquet",
    "--target_type": "REDSHIFT",
    "--target_connection": "conn-target-finance_dw",
    "--target_secret_name": "glue-target/finance_dw",
    "--target_schema": "finance",
    "--target_table": "orders_q3",
    "--load_mode": "UPSERT",
    "--merge_keys": "order_id",
    "--create_table_if_missing": "true",
    "--TempDir": "s3://bucket-b/glue-temp/data-load/",
    "--correlation_id": "e4b7d2a6-3c9f-4e18-b5a1-6d0c8f2e7b39"
  },
  "WorkerType": "G.1X",
  "NumberOfWorkers": 5,
  "Timeout": 120
}
```

```http
HTTP/1.1 200 OK
Content-Type: application/x-amz-json-1.1

{ "JobRunId": "jr_9d3f7a2e6b1c..." }
```

```python
def start_data_load(load, extraction, target, corr_id):
    glue = glue_client(target["account_id"], target["region"], f"load-{load['load_id']}")
    args = {
        "--load_id": load["load_id"],
        "--request_id": extraction["request_id"],
        "--app_id": load["app_id"],
        "--source_path": extraction["output"]["s3_path"],
        "--source_format": extraction["output"]["format"],
        "--target_type": target["type"],
        "--target_connection": target["glue_connection"],
        "--target_secret_name": target["secret_name"],
        "--target_schema": load["target"]["schema"],
        "--target_table": load["target"]["table"],
        "--load_mode": load["load_mode"],
        "--merge_keys": ",".join(load.get("merge_keys", [])),
        "--create_table_if_missing": str(load.get("create_table_if_missing", False)).lower(),
        "--TempDir": "s3://bucket-b/glue-temp/data-load/",
        "--correlation_id": corr_id,
    }
    run = glue.start_job_run(JobName="data-load-job", Arguments=args,
                             WorkerType="G.1X", NumberOfWorkers=5, Timeout=120)
    return run["JobRunId"]
```

`target_id` (`finance_dw`) is resolved from a targets registry in DynamoDB to its Glue connection and secret name, so no credentials go in the arguments.

### `GlueInvokerRole` permissions (Account B)

- `glue:UpdateCrawler`, `glue:StartCrawler`, `glue:GetCrawler`, `glue:GetCrawlerMetrics` on `metadata-crawler-*`
- `glue:StartJobRun`, `glue:GetJobRun`, `glue:BatchStopJobRun` on `metadata-enrich-job`, `data-extract-job` and `data-load-job`
- `iam:PassRole` on `GlueCrawlerRole`, because `UpdateCrawler` sets the crawler's role
- Trust policy allows the EKS pod role in Account A, with `sts:ExternalId` = `dbreg-ext-id`

Job arguments are visible in the Glue console and logs, so only secret names are passed, never passwords.

## Error codes

Every error uses the same body: `{"error": {"code", "message", "field"}}`.

| HTTP | Code | Operations | Meaning |
| --- | --- | --- | --- |
| 400 | `INVALID_SCHEMA` | All POST and PATCH calls | Body malformed or a field fails its rule |
| 400 | `APP_ID_REQUIRED` | All list calls, Fetch metadata | `app_id` query parameter missing |
| 400 | `FIELD_NOT_EDITABLE` | Update, Update table metadata | Tried to change a read-only field |
| 401 | `UNAUTHENTICATED` | All | Token missing, expired or invalid |
| 403 | `NOT_AUTHORIZED` | All | User lacks rights for this `app_id` |
| 404 | `DB_NOT_FOUND` | Database calls, Start extraction, Fetch metadata, Create data extraction, Create data load | No active registration for `db_id` under `app_id` |
| 404 | `EXTRACTION_NOT_FOUND` | Metadata extraction status | `extraction_id` does not exist |
| 404 | `METADATA_NOT_FOUND` | Fetch metadata | No completed extraction for `db_id` |
| 404 | `TABLE_NOT_FOUND` | Update table metadata, Create data extraction | Table not in the extracted metadata |
| 404 | `REQUEST_NOT_FOUND` | Data extraction status, stop, retry, execute; Create data load | `request_id` does not exist |
| 404 | `LOAD_NOT_FOUND` | Data load status, stop, retry | `load_id` does not exist |
| 409 | `DB_ID_EXISTS` | Create | `db_id` already registered |
| 409 | `EXTRACTION_IN_PROGRESS` | Start metadata extraction | An extraction for this `db_id` is already running |
| 409 | `EXTRACTION_NOT_COMPLETE` | Create data load | Source extraction is not `SUCCEEDED` |
| 409 | `NOT_EXECUTABLE` | Execute data extraction | Only `SUBMITTED` requests can be executed |
| 409 | `NOT_STOPPABLE` | Stop extraction, Stop load | Already finished or stopped |
| 409 | `NOT_RETRYABLE` | Retry extraction, Retry load | Only `FAILED` or `STOPPED` can be retried |
| 412 | `VERSION_MISMATCH` | Update, Delete, Update table metadata | `If-Match` is not the current version |
| 422 | `HOST_NOT_ALLOWED` | Create, Update | Host outside approved domains or CIDRs |
| 422 | `PORT_NOT_ALLOWED` | Create, Update | Port not allowed for the engine |
| 422 | `COLUMN_NOT_FOUND` | Update table metadata, Create data extraction | Column not in the table |
| 422 | `INVALID_QUERY` | Create data extraction | Not a single parameterized `SELECT` |
| 422 | `INVALID_FILTER` | Create data extraction | Unknown operator or wrong number/type of values |
| 428 | `IF_MATCH_REQUIRED` | Update, Delete, Update table metadata | `If-Match` header missing |
| 429 | `RATE_LIMITED` | All; Execute also when Glue concurrent runs are exceeded | Too many requests; retry later |
| 500 | `INTERNAL_ERROR` | All | Unexpected failure; quote the correlation ID |

## DynamoDB storage

Table `db_registry` in Account A, partition key `db_id`. GSI `app_id-index` (partition `app_id`, sort `created_at`) serves the list call. Encrypted with a customer-managed KMS key, point-in-time recovery on.

| Operation | DynamoDB call |
| --- | --- |
| Create | `PutItem` with `attribute_not_exists(db_id)` |
| Fetch | `GetItem` on `db_id`, hidden if `status = DELETED` |
| List | `Query` on `app_id-index`, filter `status <> DELETED` |
| Update | `UpdateItem` with condition `version = :ifMatch`, then `version + 1` |
| Delete | `UpdateItem` setting `status = DELETED`, condition `version = :ifMatch` |

Stored item after create:

```json
{
  "db_id": "orders_db",
  "app_id": "APP12345",
  "engine": "postgresql",
  "host": "orders-db.abc123.us-west-2.rds.amazonaws.com",
  "port": 5432,
  "database": "orders",
  "auth_type": "secret",
  "secret_name": "glue-db/orders_db",
  "status": "REGISTERED",
  "version": 1,
  "created_by": "jane.doe@example.com",
  "created_at": "2026-10-27T06:39:00Z",
  "updated_at": "2026-10-27T06:39:00Z"
}
```

`secret_name` is derived as `glue-db/{db_id}` when `auth_type` is `secret` and is never returned by the API.
