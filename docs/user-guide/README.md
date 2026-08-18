# gaeco — user guide

From a freshly started platform to actual data, in five steps. Each one depends on the previous, so
the order is not a suggestion.

| | | |
| --- | --- | --- |
| 1 | [First start](01-first-start.md) | Signing in, the setup checklist, and adding a user |
| 2 | [Define the data model](02-data-model.md) | Guideline and ontology: what may exist, what may be connected |
| 3 | [Create a UseCase](03-usecase.md) | The working context data and permissions hang off |
| 4 | [Assign permissions](04-permissions.md) | Read, write or hidden — per property, per user group |
| 5 | [Create data](05-creating-data.md) | Instances and relationships, in the graph and in the table |

## The short version

```
open http://localhost:5000          # sign in as admin / admin
Platform Config  → upload demodata/IBPDI/IBPDI.guideline and IBPDI.ttl
UseCases         → create one, named after a task
Access Rights    → pick the UseCase + a user group, grant Write on the
                   classifications you intend to use, then Save changes
Instances        → pick the UseCase, + to create, click the canvas
```

Or skip all of it and load the [demo data](../../demodata/setup-demo-data.md), then come back to
understand what it did.

## The idea in four sentences

The **guideline** defines what kinds of object exist and what properties they carry. The **ontology**
defines which of them may be connected to which. A **UseCase** is a working context, and every view
and permission is bound to one — so the same building can be relevant in different ways to different
tasks without being stored twice. **Access rights** are then granted per property, for a user group,
within a UseCase.

Everything else follows from that: a classification you cannot select, or a property you cannot edit,
is almost always a permission rather than a fault.

## If something looks broken

| Symptom | Usually means |
| --- | --- |
| Access Rights shows nothing, selectors disabled | The guideline has not finished propagating yet — wait and reload |
| A classification is not offered when creating data | No **write** access for your group in this UseCase |
| A field is missing from a form | That property is set to `None`, which hides rather than disables |
| Two instances refuse to connect | The ontology does not permit that relationship, in that direction |
| A signed-in user sees nothing at all | Their account is in no user group — see [adding a user](01-first-start.md#adding-a-user) |
| The start page shows 404 at `/` | The home module is mounted on `/homepage` |

## Beyond this guide

- [Repository README](../../README.md) — starting, stopping and configuring the stack
- [Orientation](../orientation.md) — how the services fit together, and where to change what
- [Demo data](../../demodata/setup-demo-data.md) — loading a complete example portfolio

---

The screenshots in [`screenshots/`](screenshots) are not edited by hand. They are produced by a
script that drives a real platform from a clean start with no demo data — the same steps this guide
describes, in the same order — so the whole set can be regenerated whenever the UI changes rather
than drifting out of date one image at a time.
