import sqlite3
import json
import os
import hashlib
from datetime import datetime

DB_PATH = os.environ.get("DATABASE_PATH", "/tmp/topup_store.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password: str, salt: str = "MYANPLAY_SECRET_SALT_2026") -> str:
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT NOT NULL,
            wallet_balance REAL NOT NULL DEFAULT 0.0,
            role TEXT NOT NULL DEFAULT 'USER',
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS deposits (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_id TEXT NOT NULL,
            screenshot_path TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT,
            game_type TEXT NOT NULL,
            player_id TEXT NOT NULL,
            zone_id TEXT,
            player_name TEXT,
            package_id TEXT NOT NULL,
            package_name TEXT NOT NULL,
            price_mmk REAL NOT NULL,
            payment_method TEXT NOT NULL,
            transaction_id TEXT,
            screenshot_path TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            provider_txn_id TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS packages (
            id TEXT PRIMARY KEY,
            game_type TEXT NOT NULL,
            name TEXT NOT NULL,
            diamonds_uc INTEGER NOT NULL,
            price_mmk REAL NOT NULL,
            product_code TEXT NOT NULL
        )
    ''')

    cursor.execute('SELECT COUNT(*) FROM packages')
    if cursor.fetchone()[0] == 0:
        default_packages = [
            ('ml_weekly', 'MLBB', 'Weekly Diamond Pass', 1, 6600, 'weekly_pass'),
            ('ml_86', 'MLBB', '86 Diamonds', 86, 5600, '86_dia'),
            ('ml_172', 'MLBB', '172 Diamonds', 172, 10800, '172_dia'),
            ('ml_257', 'MLBB', '257 Diamonds', 257, 16800, '257_dia'),
            ('ml_706', 'MLBB', '706 Diamonds', 706, 42000, '706_dia'),
            ('pubg_60', 'PUBG', '60 UC', 60, 4300, 'pubg_60_uc'),
            ('pubg_325', 'PUBG', '325 UC', 325, 22000, 'pubg_325_uc'),
            ('pubg_660', 'PUBG', '660 UC', 660, 43500, 'pubg_660_uc'),
        ]
        cursor.executemany('''
            INSERT INTO packages (id, game_type, name, diamonds_uc, price_mmk, product_code)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', default_packages)

    cursor.execute('SELECT COUNT(*) FROM users WHERE phone = "09449490500"')
    if cursor.fetchone()[0] == 0:
        admin_pass = hash_password("admin12345")
        cursor.execute('''
            INSERT INTO users (id, phone, password_hash, name, wallet_balance, role, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ('ADMIN-001', '09449490500', admin_pass, 'MyanPlay Admin', 1000000.0, 'ADMIN', datetime.now().isoformat()))

    conn.commit()
    conn.close()

def register_user(user_id: str, phone: str, password: str, name: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE phone = ?', (phone,))
    if cursor.fetchone():
        conn.close()
        return None
    
    pass_hash = hash_password(password)
    created_at = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO users (id, phone, password_hash, name, wallet_balance, role, created_at)
        VALUES (?, ?, ?, ?, 0.0, 'USER', ?)
    ''', (user_id, phone, pass_hash, name, created_at))
    conn.commit()
    conn.close()
    return {"id": user_id, "phone": phone, "name": name, "wallet_balance": 0.0, "role": "USER"}

def authenticate_user(phone: str, password: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    pass_hash = hash_password(password)
    cursor.execute('SELECT * FROM users WHERE phone = ? AND password_hash = ?', (phone, pass_hash))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, phone, name, wallet_balance, role, created_at FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_deposit_request(deposit_id: str, user_id: str, amount: float, payment_method: str, transaction_id: str, screenshot_path: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO deposits (id, user_id, amount, payment_method, transaction_id, screenshot_path, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?)
    ''', (deposit_id, user_id, amount, payment_method, transaction_id, screenshot_path, created_at))
    conn.commit()
    conn.close()

def approve_deposit(deposit_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM deposits WHERE id = ? AND status = "PENDING"', (deposit_id,))
    deposit = cursor.fetchone()
    if not deposit:
        conn.close()
        return False
    
    cursor.execute('UPDATE users SET wallet_balance = wallet_balance + ? WHERE id = ?', (deposit['amount'], deposit['user_id']))
    cursor.execute('UPDATE deposits SET status = "APPROVED" WHERE id = ?', (deposit_id,))
    conn.commit()
    conn.close()
    return True

def get_pending_deposits():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT d.*, u.name as user_name, u.phone as user_phone 
        FROM deposits d 
        JOIN users u ON d.user_id = u.id 
        WHERE d.status = 'PENDING'
        ORDER BY d.created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def create_order(order_data: dict):
    conn = get_db_connection()
    cursor = conn.cursor()
    created_at = datetime.now().isoformat()
    
    if order_data['payment_method'] == 'WALLET' and order_data.get('user_id'):
        cursor.execute('SELECT wallet_balance FROM users WHERE id = ?', (order_data['user_id'],))
        user_row = cursor.fetchone()
        if not user_row or user_row['wallet_balance'] < order_data['price_mmk']:
            conn.close()
            raise ValueError("အကောင့်ထဲတွင် လက်ကျန်ငွေ မလုံလောက်ပါ")
        
        cursor.execute('UPDATE users SET wallet_balance = wallet_balance - ? WHERE id = ?', (order_data['price_mmk'], order_data['user_id']))

    cursor.execute('''
        INSERT INTO orders (order_id, user_id, game_type, player_id, zone_id, player_name, package_id, package_name, price_mmk, payment_method, transaction_id, screenshot_path, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        order_data['order_id'], order_data.get('user_id'), order_data['game_type'],
        order_data['player_id'], order_data.get('zone_id', ''), order_data.get('player_name', ''),
        order_data['package_id'], order_data['package_name'], order_data['price_mmk'],
        order_data['payment_method'], order_data.get('transaction_id', ''),
        order_data.get('screenshot_path', ''), 'PENDING', created_at
    ))
    conn.commit()
    conn.close()
    return order_data

def get_order_by_id(order_id: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE order_id = ? OR transaction_id = ?', (order_id, order_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_all_packages(game_type: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if game_type:
        cursor.execute('SELECT * FROM packages WHERE game_type = ?', (game_type,))
    else:
        cursor.execute('SELECT * FROM packages')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_order_status(order_id: str, status: str, provider_txn_id: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE orders SET status = ?, provider_txn_id = ? WHERE order_id = ?', (status, provider_txn_id, order_id))
    conn.commit()
    conn.close()
