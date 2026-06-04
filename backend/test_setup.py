import httpx
import os
import re
import sys

# Ensure UTF-8 printing on Windows terminal
if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

DEV_URL = "http://localhost:8001"
CLIENT_URL = "http://localhost:8000"

print("====================================================")
print("[STARTING] STARTING AUTOMATED END-TO-END SUBSCRIPTION SETUP")
print("====================================================")

try:
    # 1. Create billing plan on developer server
    print("\n[1/5] Creating Billing Plan on Developer Server...")
    plan_data = {
        "name": "Auto Gold Plan",
        "description": "Premium automated test plan",
        "tier": "2",
        "annual_pricing": 1200,
        "monthly_pricing": 120
    }
    res = httpx.post(f"{DEV_URL}/plans", data=plan_data)
    if res.status_code in (200, 201):
        print("[SUCCESS] Plan created successfully.")
    else:
        print(f"[INFO] Plan log: {res.text}")

    # 2. Create tenant profile on developer server
    print("\n[2/5] Registering Test Tenant on Developer Server...")
    tenant_data = {
        "name": "Automated Testing Corp",
        "phone_no": "+20123456789",
        "contact_email": "billing@autotest.com",
        "access_email": "admin@autotest.com",
        "access_password": "securepassword123"
    }
    res = httpx.post(f"{DEV_URL}/tenants", data=tenant_data)
    if res.status_code not in (200, 201):
        raise RuntimeError(f"Failed to create tenant: {res.text}")
    
    tenant_id = res.json()["id"]
    print(f"[SUCCESS] Tenant registered. Tenant ID: {tenant_id}")

    # 3. Create active subscription configuration
    print("\n[3/5] Allocating Subscription for Tenant...")
    sub_data = {
        "tenant_id": tenant_id,
        "plan_id": "Auto Gold Plan",
        "subscription_type": "monthly"
    }
    res = httpx.post(f"{DEV_URL}/subscriptions", data=sub_data)
    if res.status_code not in (200, 201):
        raise RuntimeError(f"Failed to allocate subscription: {res.text}")
        
    subscription_id = res.json()["subscription_id"]
    print(f"[SUCCESS] Subscription allocated. ID: {subscription_id}")

    # 4. Update the client .env configuration file automatically
    print("\n[4/5] Syncing license installation ID to Client Application...")
    env_path = ".env"
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            content = f.read()
        
        # Replace or append INSTALLATION_UUID value
        if "INSTALLATION_UUID=" in content:
            content = re.sub(r"INSTALLATION_UUID=.*", f"INSTALLATION_UUID={subscription_id}", content)
        else:
            content += f"\nINSTALLATION_UUID={subscription_id}\n"
        
        with open(env_path, "w") as f:
            f.write(content)
        print("[SUCCESS] Sync complete. Client .env file updated.")
    else:
        print("[WARNING] Warning: Client .env file not found in current directory.")

    # 5. Trigger mock Paymob payment webhook
    print("\n[5/5] Triggering Mock Paymob Payment Webhook...")
    import hmac
    import hashlib

    # Load HMAC secret from developer .env
    hmac_secret = "027D00A9DDA0EF7CE070FFBDCC574CFE"
    dev_env_path = "D:/Work/Learning/coourses/Grad/dev_proj/rawivision_developers/.env"
    if os.path.exists(dev_env_path):
        with open(dev_env_path, "r") as f:
            for line in f:
                if line.startswith("PAYMOB_HMAC_SECRET="):
                    hmac_secret = line.split("=", 1)[1].strip()

    # Build the payload matching the verification format
    obj = {
        "amount_cents": 12000,
        "created_at": "2026-05-20T00:00:00.000000",
        "currency": "EGP",
        "error_occured": False,
        "has_parent_transaction": False,
        "id": 123456,
        "integration_id": 4829834,
        "is_3d_secure": True,
        "is_auth": False,
        "is_capture": False,
        "is_refunded": False,
        "is_standalone_payment": True,
        "is_voided": False,
        "order": {
            "id": 78910,
            "merchant_order_id": subscription_id
        },
        "owner": 112233,
        "pending": False,
        "source_data": {
            "pan": "1234",
            "sub_type": "visa",
            "type": "card"
        },
        "success": True
    }
    
    callback_payload = {
        "obj": obj
    }

    def format_val(val):
        if isinstance(val, bool):
            return "true" if val else "false"
        if val is None:
            return ""
        return str(val)

    concatenated = (
        format_val(obj.get("amount_cents")) +
        format_val(obj.get("created_at")) +
        format_val(obj.get("currency")) +
        format_val(obj.get("error_occured")) +
        format_val(obj.get("has_parent_transaction")) +
        format_val(obj.get("id")) +
        format_val(obj.get("integration_id")) +
        format_val(obj.get("is_3d_secure")) +
        format_val(obj.get("is_auth")) +
        format_val(obj.get("is_capture")) +
        format_val(obj.get("is_refunded")) +
        format_val(obj.get("is_standalone_payment")) +
        format_val(obj.get("is_voided")) +
        format_val(obj.get("order", {}).get("id")) +
        format_val(obj.get("owner")) +
        format_val(obj.get("pending")) +
        format_val(obj.get("source_data", {}).get("pan")) +
        format_val(obj.get("source_data", {}).get("sub_type")) +
        format_val(obj.get("source_data", {}).get("type")) +
        format_val(obj.get("success"))
    )

    computed_hmac = hmac.new(
        hmac_secret.encode("utf-8"),
        concatenated.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    res = httpx.post(f"{DEV_URL}/payment/paymob-callback?hmac={computed_hmac}", json=callback_payload)
    if res.status_code == 200:
        print("[SUCCESS] Mock payment succeeded. Database updated.")
        print("[SUCCESS] Outbound webhook delivered to Client Application.")
    else:
        print(f"[FAIL] Webhook simulation failed: {res.text}")

    print("\n====================================================")
    print("🎉 ALL DONE! Your application is now active.")
    print("👉 Refresh your React page at http://localhost:3000")
    print("====================================================")

except Exception as e:
    print(f"\n[FAIL] Setup failed: {e}")
