<div align="center">
  <img src="https://raw.githubusercontent.com/gaeco-ekkodale/.github/main/assets/gaeco_logo_horizontal_color.png" width="200" alt="gaeco logo">

  <em>Runs the complete gaeco platform locally with a single command — public container images only, no source build.</em>

  [![License](https://img.shields.io/badge/license-fair--code-blue.svg)](LICENSE.md)
  [![Version](https://img.shields.io/github/v/release/gaeco-ekkodale/gaeco)](../../releases)

  [gaeco-ekkodale Organization](https://github.com/gaeco-ekkodale) · [All Repos](https://github.com/orgs/gaeco-ekkodale/repositories)
</div>

---

gaeco (Graphs for Architecture, Engineering, Construction, Operations) is an event-driven microservice platform for BIM data management. It translates external building-industry standards (IFC, IBPDI, Brick Schema, ASHRAE 223 and others) into a shared, versioned classification and relationship model (Guideline + Ontology) and exposes consistent, graph-based building data (Instance) across use cases and departments — without forcing every consumer onto one rigid schema. Built for organizations managing building/portfolio data across disconnected departmental systems (construction, facilities management, leasing, accounting) that need automatic, reliable data propagation instead of manual, error-prone hand-offs.

> This project is licensed under the [Source Available](LICENSE.md). Source code is viewable and usable; commercial use is restricted.

---

Each service lives in a repository of its own — see [Source code](#source-code). This repo contains
no source code, only what is needed to run the platform.

> **Just started it and wondering what to do?** The [user guide](docs/user-guide/README.md) takes an
> empty platform through its setup and on to creating data — data model, UseCase, permissions down to
> the single property, then the graph and table views.
>
> **More than just starting it?** How the services fit together and **where you change what**
> is described in [`docs/orientation.md`](docs/orientation.md).

---

## Prerequisites

- **Docker** + **Docker Compose v2** (Docker Desktop on Windows/Mac is sufficient)
- ~8 GB of free RAM for the full stack
- Free ports (defaults, changeable in `.env`): see the table below

---

## Quick start

### Windows (recommended): a single double-click

Run `start-gaeco.bat`. The script asks interactively:

1. **Clean start?** – stop the stack and delete all volumes/data (for a fresh state).
2. **With demo data?** – automatically loads sample data after startup (see [Demo data](#demo-data)).

After that it pulls the images, starts the stack (**images only, no build**), waits
until everything is healthy, and opens http://localhost:5000. On the very first run it creates
`.env` from the template – then enter the `IMAGE_REGISTRY` there and start again.

### Manual (all platforms)

```bash
# 1. Create configuration
cp .env.example .env

# 2. In .env, enter the registry organization (line IMAGE_REGISTRY)
#    e.g.  IMAGE_REGISTRY=ghcr.io/<org>

# 3. Start the stack
docker compose up -d

# 4. Follow the logs (optional)
docker compose logs -f pluginhost-client
```

The first start takes a while (images are pulled, databases initialized,
Keycloak realm imported). After that:

**→ Open the platform: [http://localhost:5000](http://localhost:5000)** (Plugin Host)

Log in as **`admin`** / **`admin`**. The realm is imported ready to use, so there is no identity
setup to do first; adding further accounts is described in
[the user guide](docs/user-guide/01-first-start.md#adding-a-user).

---

## Accessing the services

| Service | URL | Credentials (default) |
|---|---|---|
| **Plugin Host (main entry point)** | http://localhost:5000 | Keycloak login |
| Keycloak Admin | http://localhost:9345/admin | `admin` / `admin` |
| Kafka UI | http://localhost:8080 | `gaeco` / `gaeco` |
| MinIO Console | http://localhost:9001 | `minioadmin` / `minioadmin` |
| Aspire Monitoring | http://localhost:18888 | Token from `ASPIRE_TOKEN` |

The API servers of the individual services are located at `localhost:50xx` (see `.env`, block 2).

---

## Extensions

gaeco is **modular**. What you see after logging in is not one application but a shell with modules
loaded into it — and that list is open. A module can come from us, from you, or from a third party:
anything that brings a microfrontend and declares itself can take its place beside the ones shipped
here, whether it extends an existing capability or adds a new one.

The App Orchestrator is the piece that makes that work: it discovers the client containers and
registers them with the shell, so adding a module is a deployment step rather than a rebuild of the
platform. An app store on top of it — for finding and installing modules without touching Compose
files — is planned and not available yet.

---

## Source code

gaeco is not one codebase. Every service is developed, versioned and released on its own, and
this repo only composes the resulting images — which is why a version bump here is a single
`*_TAG` in [`.env`](.env.example) rather than a coordinated release.

The repositories below are the source. Where the *images* come from is a separate setting —
`IMAGE_REGISTRY` in `.env` — and need not be the same organisation.

| Service | What it does | Repository |
| --- | --- | --- |
| Plugin Host | The shell all modules are loaded into; owns login and navigation | [PluginHost](https://github.com/gaeco-ekkodale/PluginHost) |
| App Orchestrator | Discovers the client containers and registers them with the shell | [AppOrchestrator](https://github.com/gaeco-ekkodale/AppOrchestrator) |
| Homepage | Start page and setup checklist | [Homepage](https://github.com/gaeco-ekkodale/Homepage) |
| Platform Config | Upload and manage guideline and ontology | [PlatformConfig](https://github.com/gaeco-ekkodale/PlatformConfig) |
| Guideline Service | Stores the classifications and their properties | [GuidelineService](https://github.com/gaeco-ekkodale/GuidelineService) |
| Ontology Service | Stores the permitted relationships | [OntologyService](https://github.com/gaeco-ekkodale/OntologyService) |
| UseCase Service | The working contexts | [UseCaseService](https://github.com/gaeco-ekkodale/UseCaseService) |
| Access Service | Permissions per property, per user group, per UseCase | [AccessService](https://github.com/gaeco-ekkodale/AccessService) |
| Instance Service | The data itself: instances and their relationships | [InstanceService](https://github.com/gaeco-ekkodale/InstanceService) |

**Tooling.** The guideline and ontology files that the platform runs on are produced by the
Guideline Editor, not written by hand:

| Tool | Repository |
| --- | --- |
| Guideline Editor | [Guideline.Editor](https://github.com/gaeco-ekkodale/Guideline.Editor) |
| Guideline Model | [Guideline.Model](https://github.com/gaeco-ekkodale/Guideline.Model) |

Each repository carries its own documentation under `_docu/`: `_docu/user/` for using the module,
`_docu/developer/` for working on it.

---

## Demo data

The [`demodata/`](demodata/) folder contains example use cases and access rights
as well as a loading script. For usage, see [`demodata/setup-demo-data.md`](demodata/setup-demo-data.md):

```bash
python demodata/setup-demo-data.py
```

> **Requires [Git LFS](https://git-lfs.com/).** The `.guideline` files are stored
> via LFS, so a clone without it yields ~130 byte pointer files and the loading
> script fails. Install it, then `git lfs pull` to fetch the actual data.

---

## Stopping & cleaning up

```bash
docker compose down            # stop the stack, keep all data
docker compose down -v         # stop the stack and remove its named volumes
rm -rf volumes                 # ... and this is what actually deletes the data
```

`down -v` on its own is **not** a reset. The databases, MinIO and Keycloak are bind-mounted from
`volumes/` (path from `VOLUME_BASE_PATH` in `.env`) — a folder on your disk, not a Docker volume — so
the stack comes back up with everything still in it. Deleting that folder is the step that empties
the platform, and `start-gaeco.bat` does both when you answer **Y** to *Clean start?*.

---

## Structure of this repo

```
gaeco/
├── start-gaeco.bat             # Windows: interactive start (clean start + demo data)
├── docker-compose.yml          # includes all service composes via include:
├── .env.example               # all configuration values (copy -> .env)
├── docker-compose-files/       # one compose per service
│   ├── general-services.yml    #   Kafka, MinIO, Kafka-UI, Aspire
│   ├── keycloak.yml            #   Identity Provider + realm import
│   ├── <service>.yml           #   one per backend service (+ Microfrontend client)
│   └── pluginhost.yml          #   Module Federation host (starts last)
├── keycloak/gaeco-realm.json   # preconfigured realm (clients, roles, admin user)
├── demodata/                   # sample data + loading script
└── docs/                       # orientation: structure & "where do I do what"
```

---

## If the modules do not appear after login

The clients (Access, UseCase, Instance, …) carry `app.mfe.*` labels, and the **App Orchestrator**
reads those and registers the microfrontends with the Plugin Host — which is why it is started by
default. An empty shell after a successful login is almost always that registration, so its log is
the place to look:

```bash
docker compose logs -f apporchestrator-server
```

Passwords/secrets in `.env.example` are **local development values** — replace them before any
non-local use.
