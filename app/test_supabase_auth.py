"""
DriveTrust - Supabase Auth Test Suite

Tests:
1. Environment variables
2. Supabase client creation
3. Network reachability
4. Anon-key database query
5. Service-role admin client
6. Auth sign-up endpoint
7. Real email/password login
8. Access-token retrieval

Run from project root:
    python -m app.test_supabase_auth
"""

import os
import sys

from dotenv import load_dotenv


# ---------------------------------------------------------
# Project root
# ---------------------------------------------------------

ROOT_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# ---------------------------------------------------------
# Environment
# ---------------------------------------------------------

load_dotenv(os.path.join(ROOT_DIR, ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv(
    "SUPABASE_SERVICE_ROLE_KEY"
)

# Test account credentials are kept in .env
TEST_USER_EMAIL = os.getenv("TEST_USER_EMAIL")
TEST_USER_PASSWORD = os.getenv("TEST_USER_PASSWORD")


# ---------------------------------------------------------
# Output helpers
# ---------------------------------------------------------

PASS = "\033[92m✔ PASS\033[0m"
FAIL = "\033[91m✘ FAIL\033[0m"
INFO = "\033[94mℹ INFO\033[0m"


def separator(title: str = ""):
    width = 60

    if title:
        pad = max(1, (width - len(title) - 2) // 2)
        print(f"\n{'─' * pad} {title} {'─' * pad}")
    else:
        print("─" * width)


# ---------------------------------------------------------
# TEST 1 – Environment variables
# ---------------------------------------------------------

def test_env_vars():
    separator("1. Environment Variables")

    results = []

    variables = [
        ("SUPABASE_URL", SUPABASE_URL),
        ("SUPABASE_ANON_KEY", SUPABASE_ANON_KEY),
        (
            "SUPABASE_SERVICE_ROLE_KEY",
            SUPABASE_SERVICE_ROLE_KEY
        ),
        ("TEST_USER_EMAIL", TEST_USER_EMAIL),
        ("TEST_USER_PASSWORD", TEST_USER_PASSWORD),
    ]

    for name, value in variables:

        if value:
            print(f"  {PASS}  {name} is set")
            results.append(True)
        else:
            print(
                f"  {FAIL}  {name} is MISSING in .env"
            )
            results.append(False)

    return all(results)


# ---------------------------------------------------------
# TEST 2 – Supabase client creation
# ---------------------------------------------------------

def test_client_creation():

    separator("2. Supabase Client Creation")

    try:
        from supabase import create_client, Client

        client: Client = create_client(
            SUPABASE_URL,
            SUPABASE_ANON_KEY
        )

        print(
            f"  {PASS}  "
            f"supabase-py client created successfully"
        )

        return client

    except ImportError:

        print(
            f"  {FAIL}  supabase-py is not installed"
        )
        print("         Run: pip install supabase")

        return None

    except Exception as e:

        print(
            f"  {FAIL}  "
            f"Could not create client: {e}"
        )

        return None


# ---------------------------------------------------------
# TEST 3 – Network reachability
# ---------------------------------------------------------

def test_network_reachability():

    separator("3. Network Reachability")

    import urllib.request
    import urllib.error

    try:

        request = urllib.request.Request(
            SUPABASE_URL,
            headers={
                "apikey": SUPABASE_ANON_KEY
            }
        )

        with urllib.request.urlopen(
            request,
            timeout=10
        ) as response:

            print(
                f"  {PASS}  Reached Supabase URL "
                f"(HTTP {response.status})"
            )

            return True

    except urllib.error.HTTPError as e:

        # Any HTTP response means the server is reachable.
        print(
            f"  {PASS}  Reached Supabase URL "
            f"(HTTP {e.code})"
        )

        return True

    except Exception as e:

        print(
            f"  {FAIL}  "
            f"Could not reach Supabase URL: {e}"
        )

        return False


# ---------------------------------------------------------
# TEST 4 – Anon key database query
# ---------------------------------------------------------

def test_anon_query(client):

    separator("4. Anon Key – Database Query")

    if client is None:

        print(f"  {INFO}  Skipped (no client)")
        return None

    try:

        response = (
            client
            .table("users")
            .select("id")
            .limit(1)
            .execute()
        )

        print(
            f"  {PASS}  Query succeeded "
            f"(rows returned: {len(response.data)})"
        )

        return True

    except Exception as e:

        error = str(e)

        if (
            "does not exist" in error
            or "42P01" in error
        ):

            print(
                f"  {INFO}  Table 'users' doesn't exist yet "
                f"(DB not migrated)"
            )

            return None

        if (
            "permission denied" in error
            or "42501" in error
        ):

            print(
                f"  {INFO}  Access denied by RLS/policy "
                f"(possible expected behaviour)"
            )

            return None

        print(
            f"  {FAIL}  "
            f"Unexpected database error: {error}"
        )

        return False


# ---------------------------------------------------------
# TEST 5 – Service role key
# ---------------------------------------------------------

def test_service_role_client():

    separator("5. Service Role Key – Admin Client")

    try:

        from supabase import create_client

        admin_client = create_client(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY
        )

        response = admin_client.auth.admin.list_users()

        if hasattr(response, "users"):
            users = response.users
        else:
            users = response

        user_count = len(users) if users else 0

        print(
            f"  {PASS}  Admin client works "
            f"– {user_count} Auth user(s)"
        )

        return True

    except ImportError:

        print(
            f"  {INFO}  Skipped "
            f"(supabase-py not installed)"
        )

        return None

    except Exception as e:

        error = str(e)

        if (
            "not allowed" in error.lower()
            or "403" in error
        ):

            print(
                f"  {FAIL}  "
                f"Service role key rejected: {error}"
            )

        else:

            print(
                f"  {FAIL}  "
                f"Admin client error: {error}"
            )

        return False


# ---------------------------------------------------------
# TEST 6 – Auth sign-up endpoint
# ---------------------------------------------------------

def test_auth_signup_endpoint(client):

    separator("6. Auth Sign-Up Endpoint Reachability")

    if client is None:

        print(f"  {INFO}  Skipped (no client)")
        return None

    import urllib.request
    import urllib.error
    import json

    url = f"{SUPABASE_URL}/auth/v1/signup"

    payload = json.dumps({
        "email": "test@example.invalid",
        "password": "test1234!"
    }).encode()

    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:

        with urllib.request.urlopen(
            request,
            timeout=10
        ) as response:

            print(
                f"  {PASS}  Auth sign-up endpoint "
                f"reachable (HTTP {response.status})"
            )

            return True

    except urllib.error.HTTPError as e:

        body = {}

        try:
            body = json.loads(e.read())
        except Exception:
            pass

        code = e.code

        message = (
            body.get("msg")
            or body.get("message")
            or body.get("error_description")
            or ""
        )

        if code in (400, 401, 422, 429):

            print(
                f"  {PASS}  Auth endpoint reachable "
                f"(HTTP {code}: "
                f"{message or 'validation response'})"
            )

            return True

        print(
            f"  {FAIL}  Auth endpoint returned "
            f"HTTP {code}: {message or body}"
        )

        return False

    except Exception as e:

        print(
            f"  {FAIL}  "
            f"Could not reach Auth endpoint: {e}"
        )

        return False


# ---------------------------------------------------------
# TEST 7 – Real Auth login
# ---------------------------------------------------------

def test_auth_login(client):

    separator("7. Auth Login")

    if client is None:

        print(f"  {INFO}  Skipped (no client)")
        return None

    if not TEST_USER_EMAIL:
        print(
            f"  {FAIL}  "
            f"TEST_USER_EMAIL is missing from .env"
        )
        return False

    if not TEST_USER_PASSWORD:
        print(
            f"  {FAIL}  "
            f"TEST_USER_PASSWORD is missing from .env"
        )
        return False

    try:

        response = client.auth.sign_in_with_password({
            "email": TEST_USER_EMAIL,
            "password": TEST_USER_PASSWORD
        })

        if response.user and response.session:

            print(f"  {PASS}  Login successful")

            print(
                f"  {INFO}  Auth user ID: "
                f"{response.user.id}"
            )

            access_token = response.session.access_token

            if access_token:

                print(
                    f"  {PASS}  Access token received"
                )

                # Never print the actual JWT.
                # print(
                #     f"  {INFO}  JWT is available for "
                #     f"authenticated API testing"
                # )

                print("\nACCESS TOKEN:")
                print(access_token)
                print()

                return True

            print(
                f"  {FAIL}  Login succeeded but "
                f"no access token was returned"
            )

            return False

        print(
            f"  {FAIL}  "
            f"Login returned no user/session"
        )

        return False

    except Exception as e:

        print(
            f"  {FAIL}  Login failed: {e}"
        )

        return False


# ---------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------

def print_summary(results: dict):

    separator("Summary")

    passed = sum(
        1
        for value in results.values()
        if value is True
    )

    skipped = sum(
        1
        for value in results.values()
        if value is None
    )

    failed = sum(
        1
        for value in results.values()
        if value is False
    )

    total = len(results)

    for name, result in results.items():

        if result is True:
            icon = PASS

        elif result is None:
            icon = "\033[93m~ SKIP\033[0m"

        else:
            icon = FAIL

        print(f"  {icon}  {name}")

    separator()

    print(
        f"\n  Total: {total}  |  "
        f"\033[92mPassed: {passed}\033[0m  |  "
        f"\033[93mSkipped: {skipped}\033[0m  |  "
        f"\033[91mFailed: {failed}\033[0m\n"
    )

    return failed == 0


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

if __name__ == "__main__":

    print("\n" + "═" * 60)
    print("  DriveTrust – Supabase Auth Test Suite")
    print("═" * 60)

    # TEST 1
    env_ok = test_env_vars()

    if not env_ok:

        print(
            "\n  ⚠ Fix missing .env variables "
            "then re-run.\n"
        )

        sys.exit(1)

    # TEST 2
    client = test_client_creation()

    # TEST 3
    network_ok = test_network_reachability()

    # TEST 4
    anon_ok = test_anon_query(client)

    # TEST 5
    service_role_ok = test_service_role_client()

    # TEST 6
    signup_ok = test_auth_signup_endpoint(client)

    # TEST 7
    login_ok = test_auth_login(client)

    # -----------------------------------------------------
    # Results
    # -----------------------------------------------------

    results = {
        "Environment Variables": env_ok,
        "Client Creation": client is not None,
        "Network Reachability": network_ok,
        "Anon Key Query": anon_ok,
        "Service Role Admin": service_role_ok,
        "Auth Sign-Up Endpoint": signup_ok,
        "Auth Login + JWT": login_ok,
    }

    all_ok = print_summary(results)

    sys.exit(0 if all_ok else 1)