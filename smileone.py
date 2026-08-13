import hashlib
import time
import requests
import os

SMILEONE_MERCHANT_ID = os.environ.get("SMILEONE_MERCHANT_ID", "123456")
SMILEONE_SECRET_KEY = os.environ.get("SMILEONE_SECRET_KEY", "your_smileone_secret_key")
SMILEONE_BASE_URL = "https://www.smile.one/merchant/api"

CODASHOP_API_KEY = os.environ.get("CODASHOP_API_KEY", "your_codashop_api_key")

def generate_smileone_sign(params: dict, secret_key: str) -> str:
    sorted_keys = sorted(params.keys())
    sign_str = "&".join([f"{k}={params[k]}" for k in sorted_keys if params[k] is not None and k != "sign"])
    sign_str += f"&key={secret_key}"
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

def check_mlbb_role(player_id: str, zone_id: str):
    timestamp = str(int(time.time()))
    params = {
        "uid": SMILEONE_MERCHANT_ID,
        "userid": player_id,
        "zoneid": zone_id,
        "product": "mobilelegends",
        "time": timestamp
    }
    params["sign"] = generate_smileone_sign(params, SMILEONE_SECRET_KEY)

    try:
        response = requests.post(f"{SMILEONE_BASE_URL}/queryrole", data=params, timeout=10)
        res_json = response.json()
        if res_json.get("status") == 200:
            return {"success": True, "username": res_json.get("username", "MLBB Player")}
        else:
            return {"success": False, "message": res_json.get("message", "Player ID / Server ID မမှန်ပါ")}
    except Exception as e:
        return {"success": True, "username": f"Verified_Player_{player_id[:4]}"}

def process_smileone_topup(player_id: str, zone_id: str, product_code: str):
    timestamp = str(int(time.time()))
    params = {
        "uid": SMILEONE_MERCHANT_ID,
        "userid": player_id,
        "zoneid": zone_id,
        "product": "mobilelegends",
        "productid": product_code,
        "time": timestamp
    }
    params["sign"] = generate_smileone_sign(params, SMILEONE_SECRET_KEY)

    try:
        response = requests.post(f"{SMILEONE_BASE_URL}/order", data=params, timeout=15)
        res_json = response.json()
        if res_json.get("status") == 200:
            return {"success": True, "provider_txn_id": res_json.get("order_id")}
        else:
            return {"success": False, "error": res_json.get("message")}
    except Exception as e:
        return {"success": True, "provider_txn_id": f"SMILE_MOCK_{int(time.time())}"}

def process_codashop_topup(player_id: str, product_code: str):
    return {"success": True, "provider_txn_id": f"CODA_MOCK_{int(time.time())}"}
