# gaeco-ext — Orientation & Maintenance

This documentation supplements the [README](../README.md). The README answers **"How do I
start the whole thing?"**. This document answers **"What is this, how does it fit
together, and where do I do what?"** — intended for everyone who maintains this repo
or wants to understand it.

---

## 1. What this repo is (and what it isn't)

`gaeco-ext` is the **welcome / customer repo** for gaeco. Goal:

> Start the entire gaeco platform locally with **a single command** — without
> building source code, using exclusively **prebuilt public
> container images**.

| This repo (`gaeco-ext`)                            | A service repository (e.g. `AccessService`)          |
|----------------------------------------------------|------------------------------------------------------|
| Operations only: Compose files, `.env`, demo data  | Source code and documentation of exactly one service |
| Pulls finished images from a registry              | Is where that service's image comes from             |
| Audience: customers, demos, quick local stack      | Audience: development on that service                |
| Nothing to build                                   | A local toolchain is needed to build it              |

The published service repositories contain the source and its documentation. The internal release
tooling is **not** part of them — images are consumed here by tag, and how they came to be is not
this repo's concern.

**gaeco is not one codebase.** Every service is its own repository, developed, versioned and
released independently; this repo only composes the resulting images. That is the reason a
version bump here is a single `*_TAG` in `.env` rather than a coordinated release — and the
reason there is no single checkout that contains "all of gaeco".

Anyone who wants to work **on the source code** of a service belongs in that service's own
repository. The [README](../README.md#source-code) links all of them.

Each service repository carries its own documentation in `_docu/`: `_docu/user/` describes using
the module, `_docu/developer/` describes working on it. This repo documents only the running of
the platform — the [user guide](user-guide/README.md) for using it, this document for maintaining
the deployment.

---

## 2. The fastest start (short version)

**Windows:** double-click `start-gaeco.bat` → prompts for clean start + demo data,
starts (images only), opens the browser.

**Manual:**
```bash
cp .env.example .env          # 1. Create configuration
#    in .env: set IMAGE_REGISTRY=ghcr.io/<org>
docker compose up -d           # 2. Start the stack
```

→ Open the platform: **http://localhost:5000** (Plugin Host)

The full guide including credentials is in the [README](../README.md).
Load demo data: [`demodata/setup-demo-data.md`](../demodata/setup-demo-data.md).

---

## 3. How the stack fits together

```
                          Browser  →  http://localhost:5000
                                          │
                                   ┌───────────────┐
                                   │  Plugin Host   │  Shell app (Module Federation)
                                   │  (starts last)
                                   └───────┬───────┘
                                           │  registers Microfrontends via
                                   ┌───────────────┐
                                   │ App Orchestr. │  reads app.mfe.* labels of the clients
                                   └───────────────┘
        ┌───────────┬───────────┬───────────┼───────────┬───────────────┐
     Ontology    Guideline   UseCase     Access      Instance     PlatformConfig
     -server     -server     -server     -server     -server      -client
        │           │           │           │           │
     (each backend service has its own DB + optionally an MFE client)
        └───────────┴───────────┴───── Kafka ──────────┴──── MinIO ──── Keycloak
                                   (Infrastructure: general-services.yml + keycloak.yml)
```

**Startup order** (controlled via `depends_on`): infrastructure (Kafka, MinIO,
Aspire, Keycloak) → backend services → App Orchestrator → Plugin Host.

**Network:** All containers are on the shared network `gaeco-local` and reach
each other by service name (e.g. `gaeco-broker`, `keycloak-server`, `access-postgres`).
Each service additionally has its own internal network for its database.

---

## 4. Overview of the services

| Service            | Compose file                           | Purpose                                             | UI port | API port |
|--------------------|----------------------------------------|-----------------------------------------------------|---------|----------|
| **Plugin Host**    | `pluginhost.yml`                       | Shell / main entry point, embeds all MFEs           | 5000    | 5240     |
| **App Orchestrator** | `apporchestrator.yml`                | Detects clients (`app.mfe.*` labels), registers MFEs | 3000  | 6241     |
| **Ontology**       | `ontology-service.yml`                 | Semantic relationships (RDF/OWL/Turtle)             | –       | 5023     |
| **Guideline**      | `guideline-service.yml`                | Classification / taxonomy (IBPDI)                   | –       | 5008     |
| **UseCase**        | `usecase-service.yml`                  | Use cases                                           | 3131    | 5130     |
| **Access**         | `access-service.yml`                   | Role- / permission-based visibility (RBAC)          | 3132    | 5131     |
| **Instance**       | `instance-service.yml`                 | Domain-object instances + relationships (graph/ArcadeDB) | 5026 | 5024   |
| **PlatformConfig** | `platformconfig-service.yml`           | Platform configuration (client only)                | 3133    | –        |
| Infrastructure     | `general-services.yml`                 | Kafka, Kafka UI, MinIO, Aspire monitoring           | see below |        |
| Keycloak           | `keycloak.yml`                         | Identity provider (+ realm import)                  | 9345    |          |

**Infrastructure UIs:** Keycloak Admin `:9345/admin` · Kafka UI `:8080` ·
MinIO console `:9001` · Aspire monitoring `:18888`.

> All ports are defaults and can be freely changed in `.env` (block 2).

That table is what ships here, not what the platform can consist of. A module is discovered from the
`app.mfe.*` labels on its client container, so adding one — ours, yours, or a third party's — is a
new `<service>.yml` and an `include:` line, not a change to the shell. See
[Extensions](../README.md#extensions).

---

## 5. Structure of the repo

```
gaeco-ext/
├── start-gaeco.bat             # Windows: interactive start (clean start + demo data, images only)
├── docker-compose.yml          # Entry point: includes all service composes via include:
├── .env.example                # ALL configuration values  (copy → .env)
├── .env                        # your local configuration (do not commit!)
├── docker-compose-files/       # one compose per service
│   ├── general-services.yml    #   Kafka, MinIO, Kafka UI, Aspire
│   ├── keycloak.yml            #   Identity provider + realm import
│   ├── <service>.yml           #   per backend service (+ MFE client)
│   └── pluginhost.yml          #   Module Federation host (starts last)
├── keycloak/gaeco-realm.json   # preconfigured realm (clients, roles, admin user)
├── demodata/                   # sample data + load script
│   ├── setup-demo-data.py      #   loads the data via the service APIs
│   ├── setup-demo-data.md      #   guide for it
│   ├── demo-instances.json     #   instance chain Portfolio → 3 buildings → 3 addresses
│   └── *.json / *.ttl          #   use cases, access rights, guideline, ontology
├── docs/                       # this documentation
└── volumes/                    # all persistent data (created at startup)
```

The structure of a service compose file is always the same (example `access-service.yml`):
a **`<service>-postgres`** (DB, its own internal network), a **`<service>-server`**
(backend image, attached to `gaeco-network`) and — if present — a
**`<service>-client`** (Microfrontend, carrying the `app.mfe.*` labels).

---

## 6. Where do I do what?  (Task → location)

| I want to …                                       | … then here                                                                 |
|---------------------------------------------------|-----------------------------------------------------------------------------|
| **Start (Windows, interactive)**                  | `start-gaeco.bat` — prompts for clean start + demo data                     |
| **Bump image version(s)**                         | `.env` → block 1 (`*_TAG`, e.g. `ACCESS_SERVER_TAG=1.4.0`)                   |
| **Set registry / org**                            | `.env` → `IMAGE_REGISTRY`                                                    |
| **Change a port** (collision)                     | `.env` → block 2                                                            |
| **Change passwords / secrets**                    | `.env` → block 3                                                            |
| **Adjust Kafka topics / MinIO buckets**           | `.env` → block 5                                                            |
| **Add a user**                                    | Keycloak admin console — [user guide](user-guide/01-first-start.md#adding-a-user) |
| **Leave out a service entirely**                  | `docker-compose.yml` → comment out the relevant `include:` line            |
| **Change env var / image of a service**           | the respective file in `docker-compose-files/<service>.yml`                |
| **Add a module / service**                        | create a new `<service>.yml` + add it under `include:` in `docker-compose.yml` + add ports/secrets in `.env.example` |
| **Load demo data**                                | `python demodata/setup-demo-data.py` (see `demodata/setup-demo-data.md`)    |
| **Change demo data**                              | edit JSON/TTL in `demodata/`                                               |
| **Where does persistent data go?**                | `volumes/` (path = `.env` → `VOLUME_BASE_PATH`)                            |
| **See logs of a service**                         | `docker compose logs -f <service>`                                          |
| **Reset everything (delete data)**                | `start-gaeco.bat` → *Clean start? Y* — or `docker compose down -v` **plus** deleting `volumes/` |

> **Rule of thumb:** Values you change in day-to-day work (versions, ports, secrets)
> **always live in `.env`** — never in the Compose files. The Compose files
> describe the *structure* of a service, `.env` provides the *values*.

---

## 7. Typical tasks

**Update the version of a service**
```bash
# 1. set the tag in .env, e.g.  ACCESS_SERVER_TAG=1.4.0
docker compose pull access-server     # pull the new image
docker compose up -d access-server    # recreate the container
```

**Set up the stack cleanly from scratch**
```bash
docker compose down -v                # stop, remove the named volumes
rm -rf volumes                        # the actual data lives here — this is the reset
docker compose up -d                  # start fresh
python demodata/setup-demo-data.py    # reload demo data
```

The second line is not optional. `VOLUME_BASE_PATH` bind-mounts every database, MinIO and Keycloak
out to `volumes/` on the host, so `down -v` prints a page of "Volume Removed" and changes nothing
about the data. `start-gaeco.bat` does both when asked for a clean start.

**Check what's running**
```bash
docker compose ps
docker compose logs -f pluginhost-client
```

---

## 8. Identity and module registration

Two things are worth knowing about, because they explain most of what can look broken after a
first start. Neither needs configuring.

**Identity is preconfigured.** `keycloak/gaeco-realm.json` is imported on startup and contains the
clients, roles and the `admin` user, so there is no identity setup step. The only routine task is
adding an account — and the group it joins matters, because access rights are granted to groups:
see [Adding a user](user-guide/01-first-start.md#adding-a-user). A clean start deletes Keycloak's
database along with `volumes/` and re-imports the realm, so it also removes any user created since.

**Modules register themselves.** The clients carry `app.mfe.*` labels (see e.g.
`access-service.yml`); the **App Orchestrator** reads them and registers the microfrontends with the
Plugin Host. A shell with no modules in it after a successful login is nearly always that step, so
`docker compose logs -f apporchestrator-server` is where to look. The same mechanism is what makes
the platform extensible — a new module is a container with those labels, nothing more.

> The passwords/secrets in `.env.example` are **local development values** — replace
> them before any non-local use.
