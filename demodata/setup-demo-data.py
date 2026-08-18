#!/usr/bin/env python3
# Copyright (c) 2025 Ekkodale GmbH. All rights reserved.
#
# This file is part of the gaeco platform system.
#
# Use of this file is governed by the terms of the license
# in LICENSE.md at the root of this repository.
# Unauthorized copying, modification, distribution, or use of this file,
# via any medium, is strictly prohibited except as expressly permitted
# under that license.

"""
gaeco Demo Data Setup Script
Seeds example data (use cases, access rights, guideline, ontology) into a
locally running gaeco stack via the service APIs.

Usage (from the repository root):
    python demodata/setup-demo-data.py

Data files live in two sub-folders next to this script:
    seed/   -> script-only seed data (pushed via API, not for manual upload)
    IBPDI/  -> standard files a user can also upload manually in the UI
Ports match the defaults in .env.template (block 2, "API servers").

Output is intentionally quiet: only errors are printed while running, plus a
short summary at the end. Run with --dry-run for a verbose step-by-step preview.
"""

import argparse
import hashlib
import json
import os
import ssl
import sys
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

# =============================================================================
# Configuration -- ports = defaults from .env.template (block 2)
# =============================================================================
USECASE_BASE_URL = "http://localhost:5130"
ACCESS_BASE_URL = "http://localhost:5131"
GUIDELINE_BASE_URL = "http://localhost:5008"
ONTOLOGY_BASE_URL = "http://localhost:5023"
INSTANCE_BASE_URL = "http://localhost:5024"
SKIP_CERTIFICATE_CHECK = True

# --- Keycloak (for instance seeding; creating instances requires a token) ---
KEYCLOAK_BASE_URL = "http://localhost:9345"
KEYCLOAK_REALM = "gaeco"
# Public client with direct-access grant + 'groups' as a default scope
KEYCLOAK_CLIENT_ID = "plugin-host-client"
# Seed user from the imported realm (group /Admin)
DEMO_USER = "admin"
DEMO_PASSWORD = "admin"
# Keycloak admin (master realm) -- optional, to resolve the group GUID dynamically
KEYCLOAK_ADMIN_USER = "admin"
KEYCLOAK_ADMIN_PASSWORD = "admin"
# Group that DEMO_USER belongs to; its GUID is matched against AccessRights.
DEMO_GROUP_NAME = "Admin"
# Fallback GUID of group /Admin from keycloak/gaeco-realm.json (used if the admin
# API resolution fails). The realm import normally preserves this ID.
DEMO_GROUP_ID_FALLBACK = "afc11091-e386-4490-9ea9-00eb02fe6b7f"

# Demo data file names.
# Two categories (see DATA_PATH/SEED_PATH/IBPDI_PATH below):
#   seed/  -> script-only seed data (pushed via API, not for manual upload)
#   IBPDI/ -> standard files a user can also upload manually in the UI
DEMO_USECASES_FILE = "demo-usecases.json"
DEMO_ACCESSRIGHTS_FILE = "demo-accessrights.json"
GUIDELINE_FILE = "IBPDI.guideline"
ONTOLOGY_FILE = "IBPDI.ttl"
DEMO_INSTANCES_FILE = "demo-instances.json"

# PropertyRight enum (AccessService): None=0, Write=1, Read=2
RIGHT_WRITE = 1

# Data directory = folder of this script (demodata/)
DATA_PATH = os.path.dirname(os.path.abspath(__file__))
# Script-only seed data (demo-*.json) lives in demodata/seed/ ...
SEED_PATH = os.path.join(DATA_PATH, "seed")
# ... and the uploadable standard files in demodata/IBPDI/
# (one folder per standard -> later e.g. demodata/<other-standard>/).
IBPDI_PATH = os.path.join(DATA_PATH, "IBPDI")


# =============================================================================
# Low-level HTTP helpers
# =============================================================================
def setup_ssl_context():
    """SSL context without certificate verification, for local development."""
    if SKIP_CERTIFICATE_CHECK:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        return ssl_context
    return None


def _encode_body(data, content_type):
    """Encode a request body to bytes: dict/list -> JSON, str -> UTF-8 bytes."""
    if not data:
        return data
    if isinstance(data, (dict, list)) and content_type == "application/json":
        return json.dumps(data).encode("utf-8")
    if isinstance(data, str):
        return data.encode("utf-8")
    return data


def make_api_call(url, method="POST", data=None, content_type="application/json", description="", timeout=10, extra_headers=None):
    """Performs an API call against the given endpoint. Prints only on failure."""
    try:
        ssl_context = setup_ssl_context()
        data = _encode_body(data, content_type)

        headers = {'Content-Type': content_type}
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        with urllib.request.urlopen(req, context=ssl_context, timeout=timeout) as response:
            result = response.read().decode('utf-8')
            return True, result

    except HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode('utf-8')
        except Exception:
            pass
        print(f"FAIL {description}: HTTP {e.code} - {e.reason}")
        if error_body:
            print(f"     Response: {error_body}")
        return False, str(e)
    except URLError as e:
        print(f"FAIL {description}: {e.reason}")
        if "refused" in str(e.reason).lower():
            print("     Hint: the service may not be running. Is the stack started?")
        return False, str(e)
    except Exception as e:
        print(f"FAIL {description}: {str(e)}")
        return False, str(e)


def make_fire_and_forget_call(url, method="POST", data=None, content_type="application/json", description="", extra_headers=None):
    """Fire-and-forget call with a very short timeout (upload keeps running in the background).

    Prints only on failure; a timeout is treated as success (request was sent).
    """
    try:
        ssl_context = setup_ssl_context()
        data = _encode_body(data, content_type)

        headers = {'Content-Type': content_type}
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url, data=data, headers=headers, method=method)

        # Very short timeout -- just long enough to fire off the request
        with urllib.request.urlopen(req, context=ssl_context, timeout=1) as response:
            return True, ""

    except Exception as e:
        # For fire-and-forget, a timeout means the request was sent
        if "timed out" in str(e).lower() or "timeout" in str(e).lower():
            return True, ""

        print(f"FAIL {description}: {str(e)}")
        if "refused" in str(e).lower():
            print("     Hint: the service may not be running. Is the stack started?")
        return False, str(e)


def create_multipart_data(file_content, filename, content_type, additional_fields=None):
    """Builds multipart/form-data for a file upload."""
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"

    body_parts = []

    # File part
    body_parts.append(f"--{boundary}")
    body_parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"')
    body_parts.append(f"Content-Type: {content_type}")
    body_parts.append("")
    body_parts.append(file_content)

    # Additional fields
    if additional_fields:
        for name, value in additional_fields.items():
            body_parts.append(f"--{boundary}")
            body_parts.append(f'Content-Disposition: form-data; name="{name}"')
            body_parts.append("")
            body_parts.append(value)

    body_parts.append(f"--{boundary}--")

    body = "\r\n".join(body_parts)

    return body, f"multipart/form-data; boundary={boundary}"


# =============================================================================
# Authentication (Keycloak)
# =============================================================================
def get_access_token():
    """Fetches a user token (DEMO_USER) via password grant, for the instance API.

    The token carries the 'groups' claim (a default scope of plugin-host-client)
    that the InstanceService needs to resolve access rights.
    """
    token_url = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    form = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": KEYCLOAK_CLIENT_ID,
        "username": DEMO_USER,
        "password": DEMO_PASSWORD,
        "scope": "openid",
    }).encode("utf-8")
    try:
        ssl_context = setup_ssl_context()
        req = urllib.request.Request(
            token_url, data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, context=ssl_context, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("access_token")
    except Exception as e:
        print(f"FAIL Token request failed ({DEMO_USER}@{KEYCLOAK_CLIENT_ID}): {e}")
        return None


def resolve_demo_group_id():
    """Resolves the GUID of group DEMO_GROUP_NAME via the Keycloak admin API.

    Falls back to DEMO_GROUP_ID_FALLBACK if resolution fails. This GUID must be
    stored in AccessRight.userGroupId so that CanCreate matches.
    """
    try:
        ssl_context = setup_ssl_context()
        # 1. Admin token from the master realm (admin-cli, public)
        admin_url = f"{KEYCLOAK_BASE_URL}/realms/master/protocol/openid-connect/token"
        form = urllib.parse.urlencode({
            "grant_type": "password",
            "client_id": "admin-cli",
            "username": KEYCLOAK_ADMIN_USER,
            "password": KEYCLOAK_ADMIN_PASSWORD,
        }).encode("utf-8")
        req = urllib.request.Request(
            admin_url, data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, context=ssl_context, timeout=10) as resp:
            admin_token = json.loads(resp.read().decode("utf-8")).get("access_token")

        # 2. Load the realm's groups and search by name
        groups_url = f"{KEYCLOAK_BASE_URL}/admin/realms/{KEYCLOAK_REALM}/groups?search={urllib.parse.quote(DEMO_GROUP_NAME)}"
        req = urllib.request.Request(
            groups_url, headers={"Authorization": f"Bearer {admin_token}"}, method="GET")
        with urllib.request.urlopen(req, context=ssl_context, timeout=10) as resp:
            groups = json.loads(resp.read().decode("utf-8"))

        def find(gs):
            for g in gs:
                if g.get("name", "").lower() == DEMO_GROUP_NAME.lower():
                    return g.get("id")
                sub = find(g.get("subGroups", []) or [])
                if sub:
                    return sub
            return None

        gid = find(groups)
        if gid:
            return gid
    except Exception as e:
        print(f"WARN Group GUID resolution via admin API failed, using fallback: {e}")

    return DEMO_GROUP_ID_FALLBACK


# =============================================================================
# Service availability
# =============================================================================
def check_service_availability(auth=None):
    """Checks whether all required services are reachable. Prints only failures."""
    services = [
        ("UseCase Service", f"{USECASE_BASE_URL}/api/usecases"),
        ("Access Service", f"{ACCESS_BASE_URL}/api/AccessRights"),
        ("Guideline Service", f"{GUIDELINE_BASE_URL}/health"),
        ("Ontology Service", f"{ONTOLOGY_BASE_URL}/health")
    ]

    all_available = True

    for service_name, url in services:
        try:
            ssl_context = setup_ssl_context()
            headers = dict(auth) if auth else {}
            req = urllib.request.Request(url, headers=headers, method="GET")

            with urllib.request.urlopen(req, context=ssl_context, timeout=5) as response:
                pass
        except Exception as e:
            print(f"FAIL {service_name} is not available: {str(e)}")
            all_available = False

    return all_available


# =============================================================================
# Seeding steps (in the order main() runs them)
# =============================================================================
def upload_guideline(auth=None, dry_run=False):
    """Uploads the guideline from the IBPDI file."""
    guideline_file = os.path.join(IBPDI_PATH, GUIDELINE_FILE)

    if not os.path.exists(guideline_file):
        print(f"FAIL Guideline file not found: {guideline_file}")
        return False

    try:
        with open(guideline_file, 'r', encoding='utf-8') as f:
            file_content = f.read()

        if dry_run:
            print(f"[DRY RUN] Would upload {GUIDELINE_FILE}")
            return True

        body, content_type = create_multipart_data(
            file_content,
            GUIDELINE_FILE,
            "application/json"
        )

        # Wait for the response -- do NOT fire-and-forget here. IBPDI.json is
        # ~1.5 MB and would be truncated under the 1 s fire-and-forget timeout
        # while the server reads/validates/stores it (TCP backpressure), so the
        # guideline never lands. A synchronous call transmits the full body and
        # confirms the 201 response.
        success, _ = make_api_call(
            f"{GUIDELINE_BASE_URL}/guideline",
            method="POST",
            data=body,
            content_type=content_type,
            description="Guideline upload",
            timeout=60,
            extra_headers=auth
        )

        return success

    except Exception as e:
        print(f"FAIL Guideline upload failed: {str(e)}")
        return False


def upload_ontology(auth=None, dry_run=False):
    """Uploads the ontology from the IBPDI file."""
    ontology_file = os.path.join(IBPDI_PATH, ONTOLOGY_FILE)

    if not os.path.exists(ontology_file):
        print(f"FAIL Ontology file not found: {ontology_file}")
        return False

    try:
        with open(ontology_file, 'r', encoding='utf-8') as f:
            file_content = f.read()

        if dry_run:
            print(f"[DRY RUN] Would upload {ONTOLOGY_FILE}")
            return True

        body, content_type = create_multipart_data(
            file_content,
            ONTOLOGY_FILE,
            "text/turtle"
        )

        url_with_params = f"{ONTOLOGY_BASE_URL}/ontology"

        success, _ = make_fire_and_forget_call(
            url_with_params,
            method="POST",
            data=body,
            content_type=content_type,
            description="Ontology upload",
            extra_headers=auth
        )

        return success

    except Exception as e:
        print(f"FAIL Ontology upload failed: {str(e)}")
        return False


def seed_use_cases(auth=None, dry_run=False):
    """Seeds use cases from the demo data file. Returns (success, created_ids)."""
    use_cases_file = os.path.join(SEED_PATH, DEMO_USECASES_FILE)

    if not os.path.exists(use_cases_file):
        print(f"FAIL Use cases file not found: {use_cases_file}")
        return False, []

    try:
        with open(use_cases_file, 'r', encoding='utf-8') as f:
            use_cases = json.load(f)

        success = True
        created_use_case_ids = []

        for i, use_case in enumerate(use_cases):
            # POST /api/usecases expects a JSON body { name, description }.
            body = {
                "name": use_case["name"],
                "description": use_case["description"],
            }

            if dry_run:
                print(f"[DRY RUN] Would create Use Case: {use_case['name']}")
                created_use_case_ids.append(f"mock-id-{i+1}")
            else:
                result, response_body = make_api_call(
                    f"{USECASE_BASE_URL}/api/usecases",
                    method="POST",
                    data=body,
                    content_type="application/json",
                    description=f"Use Case: {use_case['name']}",
                    extra_headers=auth
                )

                if result and response_body:
                    try:
                        response_data = json.loads(response_body)
                        if 'useCase' in response_data and 'id' in response_data['useCase']:
                            created_use_case_ids.append(response_data['useCase']['id'])
                        elif 'id' in response_data:
                            created_use_case_ids.append(response_data['id'])
                        else:
                            print(f"WARN Response for Use Case '{use_case['name']}' had no ID field")
                    except json.JSONDecodeError as e:
                        print(f"WARN Failed to parse response for Use Case '{use_case['name']}': {e}")
                else:
                    success = False

        return success, created_use_case_ids

    except Exception as e:
        print(f"FAIL Failed to load use cases from file: {str(e)}")
        return False, []


def seed_access_rights(use_case_ids=None, auth=None, dry_run=False):
    """Seeds access rights from the demo data file."""
    access_rights_file = os.path.join(SEED_PATH, DEMO_ACCESSRIGHTS_FILE)

    if not os.path.exists(access_rights_file):
        print(f"FAIL Access rights file not found: {access_rights_file}")
        return False

    # Access rights MUST be bound to a valid use-case ID. Without a previously
    # created use case there is no ID -> abort here instead of creating invalid
    # rights (with an empty usecaseId).
    if not use_case_ids or len(use_case_ids) == 0:
        print("FAIL No valid use-case ID available -- run the use-case step first.")
        return False

    try:
        with open(access_rights_file, 'r', encoding='utf-8') as f:
            access_rights = json.load(f)

        # Each right carries a 0-based "useCaseIndex" (which of the created use
        # cases it belongs to). Use it to set the real useCaseId and remove the
        # helper field -- it is not part of the API schema. This way EVERY use
        # case gets its own access rights (otherwise the other use cases "see"
        # nothing).
        prepared = []
        for access_right in access_rights:
            idx = access_right.pop("useCaseIndex", 0)
            if idx < 0 or idx >= len(use_case_ids):
                print(f"WARN AccessRight '{access_right.get('name')}' references "
                      f"use-case index {idx}, which does not exist -- skipped.")
                continue
            access_right["useCaseId"] = use_case_ids[idx]
            prepared.append(access_right)

        if not prepared:
            print("FAIL No assignable access rights -- nothing created.")
            return False

        if dry_run:
            per_uc = len({ar["useCaseId"] for ar in prepared})
            print(f"[DRY RUN] Would create {len(prepared)} access rights across {per_uc} use cases")
            return True

        success, _ = make_api_call(
            f"{ACCESS_BASE_URL}/api/AccessRights",
            method="POST",
            data=prepared,
            description=f"Demo access rights (batch of {len(prepared)})",
            extra_headers=auth
        )

        return success

    except Exception as e:
        print(f"FAIL Failed to load access rights from file: {str(e)}")
        return False


def _pseudo_guid(seed):
    """Builds a deterministic GUID from a seed string (version-agnostic).

    Deterministic so that a re-run reuses the same AccessRight IDs (more
    idempotent). No randomness needed.
    """
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def seed_instances(use_case_ids=None, auth=None, dry_run=False):
    """Creates a demo chain in the InstanceService:
    1 portfolio -> buildings -> 1 address each -> floor(s) each -> space(s) each.

    Flow (order is mandatory):
      1. Fetch a user token (creating instances needs a JWT with the groups claim).
      2. Resolve the GUID of group /Admin.
      3. Create write access rights for EVERY class involved
         (otherwise CanCreate in the InstanceService throws UnauthorizedAccessException;
          the classifications endpoint is write-filtered -> no discovery possible,
          so the classificationId URIs from demo-instances.json are used instead).
      4. Create instances (portfolio, buildings, addresses, floors, spaces).
      5. Create relations (portfolioHasBuilding, addressHasBuilding,
         buildingHasFloor, floorHasSpace).
    """
    if not use_case_ids or len(use_case_ids) == 0:
        print("FAIL No valid use-case ID available -- instance seeding skipped.")
        return False
    use_case_id = use_case_ids[0]

    instances_file = os.path.join(SEED_PATH, DEMO_INSTANCES_FILE)
    if not os.path.exists(instances_file):
        print(f"FAIL Instance file not found: {instances_file}")
        return False
    with open(instances_file, "r", encoding="utf-8") as f:
        spec = json.load(f)

    classes = spec["classes"]          # class key -> guideline class name
    predicates = spec["predicates"]    # predicateUri per relation
    # classificationId = identifier URI of the guideline class (from IBPDI/IBPDI.json).
    # Derived from 'classes' so that new classes only need to be added there.
    ONTOLOGY_BASE = "https://ibpdi.org/ontology/2.0"
    class_uri = {key: f"{ONTOLOGY_BASE}/{name}" for key, name in classes.items()}

    buildings = spec.get("buildings", [])
    n_b = len(buildings)
    n_addr = sum(1 for b in buildings if b.get("address"))
    n_floors = sum(len(b.get("floors", [])) for b in buildings)
    n_spaces = sum(len(fl.get("spaces", [])) for b in buildings for fl in b.get("floors", []))

    if dry_run:
        print(f"[DRY RUN] Would fetch a token for '{DEMO_USER}' and resolve the group GUID")
        print(f"[DRY RUN] Would create {len(class_uri)} write access rights ({'/'.join(classes.values())}) for use case {use_case_id}")
        print(f"[DRY RUN] Would create 1 portfolio, {n_b} buildings, {n_addr} addresses, {n_floors} floors and {n_spaces} spaces")
        print(f"[DRY RUN] Would create {n_b} portfolioHasBuilding, {n_addr} addressHasBuilding, "
              f"{n_floors} buildingHasFloor + {n_spaces} floorHasSpace relations")
        return True

    # 1. Token (fetched centrally in main() and passed through here)
    if not auth:
        print("WARN No token -- instance seeding skipped.")
        print("     Is Keycloak running? Does the seed user 'dummy'/'dummy' exist?")
        return False

    # 2. Group GUID
    group_id = resolve_demo_group_id()

    # 3. Create write access rights for EVERY class involved
    access_rights = []
    for key, uri in class_uri.items():
        access_rights.append({
            "id": _pseudo_guid(f"{use_case_id}:{uri}"),
            "name": f"demo-write-{classes[key]}",
            "guidelineClassificationId": uri,
            "userGroupId": group_id,
            "useCaseId": use_case_id,
            "guidlineClassificationPropertyId": uri + "#demo",
            "right": RIGHT_WRITE,
        })
    ok, _ = make_api_call(
        f"{ACCESS_BASE_URL}/api/AccessRights",
        method="POST", data=access_rights, extra_headers=auth,
        description=f"Write access rights for {'/'.join(classes.values())}")
    if not ok:
        print("FAIL Could not create access rights -- instance seeding aborted.")
        return False

    # 4. Create instances
    def create_instance(name, class_key):
        body = {"name": name, "classificationId": class_uri[class_key], "properties": {}}
        ok, resp = make_api_call(
            f"{INSTANCE_BASE_URL}/{use_case_id}/instances",
            method="POST", data=body, timeout=30, extra_headers=auth,
            description=f"Instance '{name}' ({classes[class_key]})")
        if not ok or not resp:
            return None
        try:
            return json.loads(resp).get("id")
        except Exception:
            print(f"WARN Could not read id from response: {resp[:200]}")
            return None

    portfolio_id = create_instance(spec["portfolio"]["name"], "portfolio")
    if not portfolio_id:
        print("FAIL Could not create portfolio -- aborting.")
        return False

    relations = []
    for b in buildings:
        building_id = create_instance(b["name"], "building")
        if not building_id:
            print(f"WARN Building '{b['name']}' skipped.")
            continue
        # Portfolio --portfolioHasBuilding--> Building
        relations.append({
            "subjectId": portfolio_id,
            "objectId": building_id,
            "predicateUri": predicates["portfolioHasBuilding"],
        })
        addr = b.get("address")
        if addr:
            address_id = create_instance(addr["name"], "address")
            if address_id:
                # Address --addressHasBuilding--> Building (domain Address, range Building)
                relations.append({
                    "subjectId": address_id,
                    "objectId": building_id,
                    "predicateUri": predicates["addressHasBuilding"],
                })
        # Floors and, per floor, spaces
        for fl in b.get("floors", []):
            floor_id = create_instance(fl["name"], "floor")
            if not floor_id:
                print(f"WARN Floor '{fl['name']}' skipped.")
                continue
            # Building --buildingHasFloor--> Floor (domain Building, range Floor)
            relations.append({
                "subjectId": building_id,
                "objectId": floor_id,
                "predicateUri": predicates["buildingHasFloor"],
            })
            for sp in fl.get("spaces", []):
                space_id = create_instance(sp["name"], "space")
                if space_id:
                    # Floor --floorHasSpace--> Space (domain Floor, range Space)
                    relations.append({
                        "subjectId": floor_id,
                        "objectId": space_id,
                        "predicateUri": predicates["floorHasSpace"],
                    })

    # 5. Create relations (bulk)
    if relations:
        ok, _ = make_api_call(
            f"{INSTANCE_BASE_URL}/{use_case_id}/instances/relations",
            method="POST", data=relations, timeout=30, extra_headers=auth,
            description=f"{len(relations)} relations (portfolioHasBuilding / addressHasBuilding)")
        if not ok:
            print("WARN Could not create (all) relations.")
            return False

    return True


# =============================================================================
# Entry point
# =============================================================================
def _count_json_array(path):
    """Returns the number of items in a JSON array file, or None on error."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return len(json.load(f))
    except Exception:
        return None


def main():
    """Entry point of the demo data setup."""
    parser = argparse.ArgumentParser(description="gaeco Demo Data Setup Script")
    parser.add_argument("--dry-run", action="store_true",
                      help="Show what would be done, without calling any APIs")
    parser.add_argument("--skip-service-check", action="store_true",
                      help="Skip the service availability check")
    parser.add_argument("--skip-instances", action="store_true",
                      help="Skip instance seeding (portfolio/buildings/addresses)")

    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN - no real API calls will be made\n")

    # Authentication is required for ALL service calls: fetch a user token once,
    # centrally, and pass it through to every seeding step. In a dry run no real
    # calls are made -> no token needed.
    auth = None
    if not args.dry_run:
        token = get_access_token()
        if not token:
            print("FAIL No access token received - aborting.")
            print(f"     Is Keycloak ({KEYCLOAK_BASE_URL}) running? Does the seed")
            print(f"     user '{DEMO_USER}'/'{DEMO_PASSWORD}' exist in realm '{KEYCLOAK_REALM}'?")
            sys.exit(1)
        auth = {"Authorization": f"Bearer {token}"}

    if not args.skip_service_check and not args.dry_run:
        if not check_service_availability(auth=auth):
            print("FAIL One or more services are not reachable.")
            print("     Start the stack first: docker compose up -d")
            sys.exit(1)

    # The order is intentional: guideline + ontology define the schema/classes
    # that use cases, access rights and instances build on.
    required_ok = True

    guideline_ok = upload_guideline(auth=auth, dry_run=args.dry_run)
    ontology_ok = upload_ontology(auth=auth, dry_run=args.dry_run)

    use_case_ok, use_case_ids = seed_use_cases(auth=auth, dry_run=args.dry_run)
    if not use_case_ok:
        required_ok = False

    # Access rights need the created use-case IDs.
    if not seed_access_rights(use_case_ids=use_case_ids, auth=auth, dry_run=args.dry_run):
        required_ok = False

    # Instances (best effort) -- need use-case IDs, guideline classes and access
    # rights. If this fails, the rest of the demo setup stays valid.
    if args.skip_instances:
        instances_ok = None  # not attempted
    else:
        instances_ok = seed_instances(use_case_ids=use_case_ids, auth=auth, dry_run=args.dry_run)

    # --- Summary --------------------------------------------------------------
    uc_count = len(use_case_ids)
    ar_count = _count_json_array(os.path.join(SEED_PATH, DEMO_ACCESSRIGHTS_FILE))

    def status(ok):
        return "ok" if ok else "FAILED"

    print()
    print("Summary")
    print("-------")
    print(f"Use Cases:     {uc_count} ({status(use_case_ok)})")
    print(f"Access Rights: {ar_count if ar_count is not None else '?'} ({'ok' if required_ok else 'FAILED'})")
    print(f"Guideline:     {'uploaded' if guideline_ok else 'FAILED'}")
    print(f"Ontology:      {'sent' if ontology_ok else 'FAILED'}")
    if instances_ok is None:
        print("Instances:     skipped (--skip-instances)")
    else:
        print(f"Instances:     {status(instances_ok)}")

    if not required_ok:
        print("\nFAIL Some required steps failed (see errors above).")
        sys.exit(1)


if __name__ == "__main__":
    main()
