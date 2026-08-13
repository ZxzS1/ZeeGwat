from fastapi import FastAPI, HTTPException, Request, File, UploadFile, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uuid
import os
import shutil

from database import (
    init_db, register_user, authenticate_user, get_user_by_id,
    create_deposit_request, approve_deposit, get_pending_deposits,
    create_order, get_order_by_id, get_all_packages, update_order_status
)
from smileone import check_mlbb_role, process_smileone_topup, process_codashop_topup

app = FastAPI(title="MyanPlay Game Topup & Wallet API", version="2.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
init_db()

@app.get("/", response_class=HTMLResponse)
def read_root():
    paths = [
        os.path.join(BASE_DIR, "static", "index.html"),
        os.path.join(BASE_DIR, "index.html")
    ]
    for p in paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return f.read()
    return "<h1>MyanPlay TopUp API Server is Live!</h1>"

@app.post("/api/register")
def register(req: dict):
    user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
    user = register_user(user_id, req['phone'], req['password'], req['name'])
    if not user:
        raise HTTPException(status_code=400, detail="ဤဖုန်းနံပါတ်ဖြင့် အကောင့်ဖွင့်ပြီးသား ဖြစ်ပါသည်")
    return {"success": True, "message": "အကောင့် အောင်မြင်စွာ ဖွင့်ပြီးပါပြီ!", "user": user}

@app.post("/api/login")
def login(req: dict):
    user = authenticate_user(req['phone'], req['password'])
    if not user:
        raise HTTPException(status_code=401, detail="ဖုန်းနံပါတ် သို့မဟုတ် စကားဝှက် မမှန်ပါ")
    del user["password_hash"]
    return {"success": True, "message": "Login အောင်မြင်ပါသည်!", "user": user}

@app.get("/api/users/{user_id}")
def get_user_profile(user_id: str):
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User ရှာမတွေ့ပါ")
    return {"user": user}

@app.post("/api/deposits")
async def create_deposit(
    user_id: str = Form(...),
    amount: float = Form(...),
    payment_method: str = Form(...),
    transaction_id: str = Form(...),
    screenshot: UploadFile = File(...)
):
    file_ext = screenshot.filename.split(".")[-1] if "." in screenshot.filename else "jpg"
    filename = f"deposit_{uuid.uuid4().hex[:8]}.{file_ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(screenshot.file, buffer)

    deposit_id = f"DEP-{uuid.uuid4().hex[:8].upper()}"
    screenshot_url = f"/uploads/{filename}"
    create_deposit_request(deposit_id, user_id, amount, payment_method, transaction_id, screenshot_url)
    return {"success": True, "message": "ငွေဖြည့်သွင်းမှု တောင်းဆိုချက် ရရှိပါသည်။ Admin မှ Screenshot စစ်ဆေးပြီးပါက အကောင့်ထဲသို့ ငွေထည့်သွင်းပေးပါမည်။", "deposit_id": deposit_id}

@app.get("/api/admin/deposits")
def list_pending_deposits():
    return {"deposits": get_pending_deposits()}

@app.post("/api/admin/deposits/{deposit_id}/approve")
def approve_user_deposit(deposit_id: str):
    success = approve_deposit(deposit_id)
    if not success:
        raise HTTPException(status_code=400, detail="Deposit ရှာမတွေ့ပါ")
    return {"success": True, "message": "ငွေဖြည့်သွင်းမှုကို အတည်ပြုပြီး အကောင့်ထဲသို့ ငွေထည့်သွင်းပေးလိုက်ပါပြီ!"}

@app.get("/api/packages")
def list_packages(game_type: str = None):
    return {"packages": get_all_packages(game_type)}

@app.post("/api/check-player")
def check_player(req: dict):
    if req.get("game_type") == "MLBB":
        if not req.get("zone_id"):
            raise HTTPException(status_code=400, detail="Server ID (Zone ID) လိုအပ်ပါသည်")
        return check_mlbb_role(req["player_id"], req["zone_id"])
    elif req.get("game_type") == "PUBG":
        return {"success": True, "username": f"PUBG_Player_{req['player_id']}"}
    return {"success": False, "message": "Unsupported Game Type"}

@app.post("/api/orders")
async def submit_order(
    game_type: str = Form(...),
    player_id: str = Form(...),
    zone_id: str = Form(None),
    player_name: str = Form(None),
    package_id: str = Form(...),
    package_name: str = Form(...),
    price_mmk: float = Form(...),
    payment_method: str = Form(...),
    transaction_id: str = Form(None),
    user_id: str = Form(None),
    screenshot: UploadFile = File(None)
):
    screenshot_url = ""
    if screenshot:
        file_ext = screenshot.filename.split(".")[-1] if "." in screenshot.filename else "jpg"
        filename = f"order_{uuid.uuid4().hex[:8]}.{file_ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(screenshot.file, buffer)
        screenshot_url = f"/uploads/{filename}"

    order_id = f"MP-{uuid.uuid4().hex[:8].upper()}"
    
    order_data = {
        "order_id": order_id,
        "user_id": user_id,
        "game_type": game_type,
        "player_id": player_id,
        "zone_id": zone_id,
        "player_name": player_name,
        "package_id": package_id,
        "package_name": package_name,
        "price_mmk": price_mmk,
        "payment_method": payment_method,
        "transaction_id": transaction_id or "",
        "screenshot_path": screenshot_url
    }
    
    try:
        saved_order = create_order(order_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if game_type == "MLBB":
        topup_res = process_smileone_topup(player_id, zone_id, package_id)
    else:
        topup_res = process_codashop_topup(player_id, package_id)
        
    if topup_res.get("success"):
        update_order_status(order_id, "COMPLETED", topup_res.get("provider_txn_id"))
        saved_order["status"] = "COMPLETED"
        saved_order["provider_txn_id"] = topup_res.get("provider_txn_id")
    
    return {"success": True, "message": "အော်ဒါ အောင်မြင်စွာ တင်ပြီးပါပြီ!", "order": saved_order}

@app.get("/api/orders/{order_id}")
def check_order_status(order_id: str):
    order = get_order_by_id(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="အော်ဒါ ရှာမတွေ့ပါ")
    return {"order": order}

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
