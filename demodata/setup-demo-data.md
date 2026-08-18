# Loading Demo Data

A small script that loads sample data into a **locally running** gaeco stack —
for trying things out and testing.

## Prerequisite

The stack is running (see [README](../README.md)) and the four backend services are
reachable:

| Service           | Port | Env variable (`.env`)   |
|-------------------|------|-------------------------|
| UseCase Service   | 5130 | `USECASE_SERVER_PORT`   |
| Access Service    | 5131 | `ACCESS_SERVER_PORT`    |
| Guideline Service | 5008 | `GUIDELINE_SERVER_PORT` |
| Ontology Service  | 5023 | `ONTOLOGY_SERVER_PORT`  |
| Instance Service  | 5024 | `INSTANCE_SERVER_PORT`  |
| Keycloak          | 9345 | `KEYCLOAK_PORT`         |

> If you changed the ports in `.env`, adjust them at the top of the script
> (`setup-demo-data.py`, "Configuration" block) accordingly.

Also required: **Python 3.6+** (standard library only, no packages needed).

Also required: **[Git LFS](https://git-lfs.com/)**. The `.guideline` files in this
folder are stored via LFS. Without it, `git clone` leaves behind ~130 byte pointer
files instead of the real data and the upload step fails. Check with:

```bash
git lfs install          # once per machine
git lfs pull             # fetch the actual .guideline files
```

If **pushing** an updated `.guideline` fails with `LFS: Client error ... HTTP 413`,
Azure DevOps rejected the upload over HTTP/2 (its LFS request limit is 128 MB;
`ifc4_3.guideline` is ~311 MB). Force HTTP/1.1 once per clone:

```bash
git config http.version HTTP/1.1
git config lfs.concurrenttransfers 1
```

These are local settings — `.gitattributes` cannot carry them, so every clone
needs them again.

## Quick Start

From the **repo root directory**:

```bash
python demodata/setup-demo-data.py
```

Options:

```bash
# Only show what would happen (no API calls)
python demodata/setup-demo-data.py --dry-run

# Skip the reachability check of the services
python demodata/setup-demo-data.py --skip-service-check

# Do not create the instance chain (Portfolio/Building/Address)
python demodata/setup-demo-data.py --skip-instances
```

## What the Script Does

It reads the JSON/TTL files in this folder and loads them via the service APIs
**in this order** (the order matters):

1. **Use Cases** → UseCase Service (`/api/UseCases`). Returns one Use-Case ID each.
2. **Access rights** → Access Service (`/api/AccessRights`). They are bound to the ID of the
   **first** Use Case. Without a valid Use-Case ID this step aborts —
   access rights cannot exist without a Use Case.
3. **Guideline** → Guideline Service (`PUT /Guideline`, fire-and-forget)
4. **Ontology** → Ontology Service (`POST /Ontology/turtle`, fire-and-forget)
5. **Instance chain** → Instance Service (`POST /{useCaseId}/Instances` + `/relations`).
   Creates **1 Portfolio → 3 Buildings → 1 Address each**, including relations
   (`portfolioHasBuilding`, `addressHasBuilding`). See [Instance Seeding](#instance-seeding).

## Instance Seeding

Unlike the other steps, creating instances requires **authentication**
and only works if **Keycloak** and the **Access Service** are running as well.
The script handles this automatically:

1. Obtains a token for the seed user **`dummy` / `dummy`** via a **password grant**
   (client `plugin-host-client`, group `/Admin`) from Keycloak.
2. Resolves the **Group GUID** of the group `/Admin` (Keycloak Admin API, otherwise a fallback).
3. Creates **write access rights** for Portfolio/Building/Address (bound to the
   Use-Case ID + Group GUID). This is mandatory: otherwise the Instance Service rejects
   creation with *Unauthorized*, and the classification endpoint returns an empty list
   without write rights (which is why nothing is "discovered", but rather the
   `classificationId` URIs from `demo-instances.json` are used).
4. Creates the instances and links them.

If instance seeding fails (e.g. Keycloak not reachable, wrong user/password),
the rest of the demo setup remains valid. Skip it with `--skip-instances`.
User/password/ports are configurable at the top of the script.

## Folder Structure

The data is separated by purpose:

- **`seed/`** — pure **script seed data**. Loaded by the load script via API
  and not intended for manual upload.
- **`IBPDI/`** — **standard files** that a user can also upload **manually in the UI**
  (Guideline + Ontology). One folder per standard — for additional standards later,
  simply create an extra folder (e.g. `demodata/<standard>/`).

The script additionally uploads the IBPDI files automatically, so the demo
stays self-contained.

| File                         | Content                                                    |
|------------------------------|------------------------------------------------------------|
| `seed/demo-usecases.json`    | 3 sample Use-Cases                                         |
| `seed/demo-accessrights.json`| Sample access rights                                       |
| `seed/demo-instances.json`   | Instance chain Portfolio → 3 Buildings → 3 Addresses       |
| `IBPDI/IBPDI.json`           | IBPDI Guideline (export from the **Guideline Editor**)     |
| `IBPDI/IBPDI.ttl`            | IBPDI Ontology / relations (Turtle, from the Editor)       |
| `setup-demo-data.py`         | Load script                                                |

### Origin of `IBPDI/IBPDI.json` and `IBPDI/IBPDI.ttl`

Both come from the **Guideline Editor** (`Guideline.Editor`, IBPDI export):

- `IBPDI/IBPDI.json` = `Testdata/IBPDI/IBPDI.json`
- `IBPDI/IBPDI.ttl`  = `Testdata/IBPDI/IBPDI_Real_Estate_CDM_..._relations.ttl`

They use the current IBPDI schema `https://ibpdi.org/ontology/2.0/`. To
update them, re-export in the Editor and replace the two files here
(keep the file names `IBPDI.json` / `IBPDI.ttl`).

> **Note:** `demo-accessrights.json` uses the current schema
> `ibpdi.org/ontology/2.0/` (class `Building`, properties `Name` / `BuildingCode`)
> and is bound to the group `/Admin` — matching the new Guideline and the
> seed user `dummy`.

## Troubleshooting

**"Service is not available" / Connection refused**
- Is the stack running? `docker compose ps`
- Are the ports correct (`.env` vs. script configuration)?
- Have the services fully started up yet? The first start takes a while.

**"File not found"**
- The script expects the data files in the **same folder** as itself
  (`demodata/`). It's best to call it from the repo root directory.
