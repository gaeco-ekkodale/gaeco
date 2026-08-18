# Security Policy

## Reporting a vulnerability

Please report security vulnerabilities in the gaeco platform through one of
these two channels:

1. **GitHub private vulnerability reporting** (preferred) - open the Security
   tab of the affected repository and choose "Report a vulnerability". The report
   stays private between you and us, and proof-of-concept material can be
   attached safely.
2. **Email** to **security@ekkodale.com**, if you prefer email or the repository
   in question is not on GitHub.

Do **not** open a public issue, a public pull request or a work item for a
suspected vulnerability - including a pull request that merely fixes it. A commit
message or a diff is a disclosure: it tells everyone what the weakness is,
usually before anyone has a fixed release to upgrade to.

Please include, as far as you can determine it:

- the affected component, version and deployment (self-hosted or managed)
- the steps needed to reproduce the issue
- what an attacker can achieve with it
- any logs, requests or proof-of-concept code that help us confirm the finding

If you need to share information confidentially and neither channel is suitable,
say so in a first message without technical detail and we will arrange one.

### Report template

Copy this into your email and fill in what you can. Nothing here is mandatory.
A partial report is better than none, and we will ask if something is missing.

```text
Summary:
  One or two sentences: what is broken and what it allows.

Affected component:
  Repository / service / UI area, and the version or commit if known.

Deployment:
  Self-hosted, managed by ekkodale, or a local development instance.

Impact:
  What an attacker gains. Whose data or which function is at risk, and
  what access or privileges they need to start.

Steps to reproduce:
  1.
  2.
  3.
  Expected result:
  Actual result:

Proof of concept:
  Request, payload, script or screenshot. Please redact any real personal
  data before sending it.

Environment:
  Browser / OS / client version, and anything unusual about the setup.

Discovered on:
  Date, and whether the issue is already known publicly.

Disclosure:
  How you would like to be credited, or that you prefer to stay anonymous.
  Tell us here if you are working to a publication deadline.

Contact:
  How to reach you for follow-up questions.
```


## What happens next

| Step | Timeframe |
| --- | --- |
| We acknowledge your report | within 3 business days |
| We confirm the finding and assess its severity | within 10 business days |
| We have a fix or a documented mitigation | 14 days as a target, 3 days for a critical finding |
| We agree a disclosure date with you | after the assessment |

These are targets, not a contract, and a hard problem can miss them. What we
commit to is telling you when a target slips and why, rather than going quiet.

If we cannot agree a disclosure date, we will publish an advisory no later than
120 days after your report. That backstop exists so a report can never be
buried by silence.

### Actively exploited vulnerabilities

If a vulnerability is being exploited in the wild, the timeline above does not
apply. We prioritise a mitigation customers can apply immediately - a
configuration change, a network restriction, a disabled feature - and publish it
before the permanent fix is ready. Please say so explicitly in your report if you
have evidence of exploitation; it changes both our response and our notification
duties (see below).

## Coordinated disclosure

We ask you to give us the opportunity to release a fix before you publish. We do
not set a fixed embargo period unilaterally - we agree it with you, and we will
credit you in the GitHub security advisory and the release notes unless you
prefer to stay anonymous.

We will not pursue legal action against anyone who reports a vulnerability in
good faith, stays within the scope of their own test data, and does not access,
modify or delete data belonging to others.

**There is no paid bug bounty programme.** We have no budget for payouts and we
would rather say so plainly than leave it open. What you get is credit, a real
response from an engineer, and a say in the disclosure timing.

## Sending us a fix

If you have a patch, please attach it to the private report rather than opening a
pull request. We will work it into a fix on a private branch and release it, with
credit to you.

The licence terms for contributions apply to a security fix like to any other
contribution - see the Community contribution sections of `LICENSE.md`.

## Scope

This policy covers the repositories and components of the gaeco platform
published by ekkodale GmbH: the platform services, their clients, the plugin
host, the container images and the Docker Compose files.

Out of scope:

- **Third-party dependencies.** Report those to the upstream project. Do tell us
  if a gaeco release ships an affected version - deciding how fast we need to
  move on that is our job, not yours.
- **Third-party services** we merely integrate with.
- Findings that require physical access to a customer's infrastructure.
- Social engineering of ekkodale staff or of a customer's staff.
- Self-XSS, and issues that require the victim to paste attacker-supplied code
  into their own browser console.
- Resource exhaustion and denial of service against an instance you do not
  operate yourself.
- Missing hardening that the checklist below already asks the operator to apply,
  and development defaults in `appsettings.Development.json` files.
- Reports produced by automated scanners without a demonstrated impact.

## Supported versions

Security fixes are provided for the current release of the gaeco platform.
Customers under an Enterprise or Managed agreement receive fixes according to
that agreement.

Once the platform reaches a stable major version, the intent is to support the
latest stable release plus the preceding minor release for six months after it is
superseded. Until then, "current release" means the tip of the default branch and
the most recent published container images.

## Hardening a self-hosted deployment

The Source Available terms allow you to run gaeco on your own systems, and a
misconfigured deployment is the most likely way an instance gets compromised.
This list is the short version of the operational requirements; the Enterprise
model additionally refers to the implementation and operating requirements in
Anlage 1 of `LICENSE.md`.

- **Keycloak.** Change every default credential in the realm, restrict client
  redirect URIs to hosts you control, and keep the realm's token lifetimes short.
  gaeco delegates all authentication to Keycloak, so its configuration is your
  authentication posture.
- **TLS everywhere.** Traefik terminates TLS with a Let's Encrypt certificate and
  routes only what has to be reachable; keep everything else on the internal
  Compose network. The services ship with `RequireHttpsMetadata` disabled so that
  a local Keycloak works without certificates; enable it for anything that is not
  a development machine.
- **`AllowedHosts`.** The shipped value is `*`. Set it to the host names the
  deployment actually serves.
- **PostgreSQL.** Use generated credentials per service and never add a `ports:`
  mapping to a database container - `expose:` keeps it on the internal network,
  `ports:` puts it on the host. Back it up: restoring is the only answer to
  ransomware that always works.
- **MinIO.** Rotate the root access key, give each service its own key, and keep
  buckets private. Object storage left public is the classic way documents leak.
- **Kafka.** Keep brokers on the internal network with authentication enabled. An
  unauthenticated broker is a read and write channel into every service. The same
  goes for the Kafka UI container: it reads every topic and belongs nowhere near a
  public hostname.
- **Secrets.** The stacks read them from environment variables. Keep the `.env`
  file that supplies them out of git and readable only by the user running the
  stack, and keep secrets out of `appsettings.json` and out of container images.
- **OpenTelemetry.** The collector endpoint carries request data. Do not expose
  it publicly.
- **Container images.** Rebuild and redeploy on our releases; an unpatched base
  image is a vulnerability you inherited rather than wrote.
- **Backups.** Test a restore. An untested backup is a hope, not a control.

## What the platform provides

So you know what to expect before you test:

- Authentication and identity are delegated to **Keycloak** (OpenID Connect).
  Services validate bearer tokens against the realm, checking the issuer and the
  signing key.
- Authorisation is group-based. The access service owns access rights and keeps
  its group data in sync with Keycloak.
- Services run as separate containers, one Docker Compose stack per service,
  composed together by the app orchestrator. A Traefik reverse proxy terminates
  TLS and is the only component that publishes a port.
- Requests are traced through OpenTelemetry, which is what makes an incident
  reconstructable after the fact.

## Regulatory notification

Independently of the disclosure timeline above, ekkodale has reporting duties
that a report may trigger:

- **Cyber Resilience Act** (Regulation (EU) 2024/2847): from 11 September 2026,
  manufacturers must notify actively exploited vulnerabilities and severe
  security incidents to ENISA and the competent national CSIRT - for ekkodale,
  CERT-Bund at the BSI. This is why we ask you to flag evidence of exploitation
  explicitly: it starts a clock that is not ours to reset.
- **GDPR Article 33**: where a vulnerability has led to a personal data breach on
  an instance operated by ekkodale, we notify the competent supervisory authority
  within 72 hours of becoming aware of it, and the affected controllers we act
  for without undue delay.

Reporting to an authority never replaces talking to you. We will tell you if a
report of yours has triggered a notification.

## Contact

Security reports: GitHub private vulnerability reporting, or
**security@ekkodale.com**.

For anything that is not a security issue, please use the normal issue tracker of
the repository in question.

---

ekkodale GmbH, Friedrichstr. 10, 65185 Wiesbaden
