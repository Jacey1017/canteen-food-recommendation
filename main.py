"""校园食堂点评后端：FastAPI + SQLite（标准库 sqlite3）。"""
import json, os, sqlite3, time
from contextlib import closing
from datetime import datetime, timedelta, timezone

import httpx, jwt
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

DB = os.getenv("DB_PATH", "canteen.db")
SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me-in-production-0000")
WX_APPID, WX_SECRET = os.getenv("WX_APPID"), os.getenv("WX_SECRET")
HALF_LIFE_DAYS = 14   # 评价时间衰减半衰期
PRIOR_N = 5           # 贝叶斯先验权重（相当于 5 条虚拟评价）
MIN_AVOID_N = 3       # 进入避雷榜所需最少评价数

SCHEMA = """
CREATE TABLE IF NOT EXISTS canteen(id INTEGER PRIMARY KEY, name TEXT UNIQUE, location TEXT);
CREATE TABLE IF NOT EXISTS stall(id INTEGER PRIMARY KEY, canteen_id INT, name TEXT, open_hours TEXT);
CREATE TABLE IF NOT EXISTS dish(
  id INTEGER PRIMARY KEY, stall_id INT, name TEXT, price REAL, tags TEXT DEFAULT '[]',
  status TEXT DEFAULT 'active',            -- active / pending(众包待审) / offline
  first_seen_at TEXT DEFAULT (datetime('now')), created_by INT);
CREATE TABLE IF NOT EXISTS user(id INTEGER PRIMARY KEY, openid TEXT UNIQUE, created_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS review(
  id INTEGER PRIMARY KEY, user_id INT, dish_id INT, day TEXT,
  liked INT, tags TEXT DEFAULT '[]', text TEXT DEFAULT '', meal TEXT, hour INT,
  created_at TEXT DEFAULT (datetime('now')), UNIQUE(user_id, dish_id, day));
"""

app = FastAPI(title="Campus Canteen")


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def q(sql, args=()):
    with closing(db()) as con:
        return [dict(r) for r in con.execute(sql, args)]


def run(sql, args=()):
    with closing(db()) as con, con:
        return con.execute(sql, args).lastrowid


def init_db():
    with closing(db()) as con, con:
        con.executescript(SCHEMA)


init_db()


# ---------- 认证 ----------
class Login(BaseModel):
    code: str


@app.post("/auth/login")
def login(body: Login):
    """小程序 wx.login() 得到 code，换 openid。未配置 WX_APPID 时为开发模式。"""
    if WX_APPID:
        r = httpx.get("https://api.weixin.qq.com/sns/jscode2session", timeout=5, params={
            "appid": WX_APPID, "secret": WX_SECRET, "js_code": body.code, "grant_type": "authorization_code"}).json()
        if "openid" not in r:
            raise HTTPException(400, f"wechat login failed: {r.get('errmsg')}")
        openid = r["openid"]
    else:
        openid = "dev_" + body.code
    run("INSERT OR IGNORE INTO user(openid) VALUES(?)", (openid,))
    uid = q("SELECT id FROM user WHERE openid=?", (openid,))[0]["id"]
    return {"token": jwt.encode({"uid": uid, "exp": time.time() + 30 * 86400}, SECRET, "HS256")}


def current_user(authorization: str = Header(None)) -> int:
    try:
        return jwt.decode((authorization or "").removeprefix("Bearer "), SECRET, ["HS256"])["uid"]
    except Exception:
        raise HTTPException(401, "invalid token")


# ---------- 评分 ----------
def scores(dish_ids=None):
    """返回 {dish_id: {score, n, dislike_rate, tags}}。
    score = 带时间衰减的贝叶斯平均好评率，范围 0~1。"""
    where = f"WHERE dish_id IN ({','.join('?' * len(dish_ids))})" if dish_ids else ""
    rows = q(f"SELECT dish_id, liked, tags, created_at FROM review {where}", dish_ids or [])
    now = utcnow()
    agg, tw, tl = {}, 0.0, 0.0
    for r in rows:
        age = (now - datetime.fromisoformat(r["created_at"])).total_seconds() / 86400
        w = 0.5 ** (age / HALF_LIFE_DAYS)
        a = agg.setdefault(r["dish_id"], {"w": 0.0, "l": 0.0, "n": 0, "dis": 0, "tags": {}})
        a["w"] += w; a["l"] += w * r["liked"]; a["n"] += 1; a["dis"] += 1 - r["liked"]
        if not r["liked"]:
            for t in json.loads(r["tags"]):
                a["tags"][t] = a["tags"].get(t, 0) + 1
        tw += w; tl += w * r["liked"]
    m = tl / tw if tw else 0.7  # 全局平均好评率作为先验
    return {d: {"score": round((PRIOR_N * m + a["l"]) / (PRIOR_N + a["w"]), 3), "n": a["n"],
                "dislike_rate": round(a["dis"] / a["n"], 3),
                "bad_tags": sorted(a["tags"], key=a["tags"].get, reverse=True)[:3]}
            for d, a in agg.items()}


DISH_SQL = """SELECT d.id, d.name, d.price, d.tags, d.first_seen_at, s.name AS stall, c.name AS canteen
              FROM dish d JOIN stall s ON s.id=d.stall_id JOIN canteen c ON c.id=s.canteen_id
              WHERE d.status='active' """


def enrich(dishes):
    sc = scores([d["id"] for d in dishes]) if dishes else {}
    for d in dishes:
        d["tags"] = json.loads(d["tags"])
        d.update(sc.get(d["id"], {"score": None, "n": 0, "dislike_rate": None, "bad_tags": []}))
    return dishes


# ---------- 浏览 ----------
@app.get("/canteens")
def canteens():
    return q("SELECT * FROM canteen")


@app.get("/stalls")
def stalls(canteen_id: int):
    return q("SELECT * FROM stall WHERE canteen_id=?", (canteen_id,))


@app.get("/dishes")
def dishes(stall_id: int | None = None, keyword: str | None = None,
           max_price: float | None = None, limit: int = 50):
    sql, args = DISH_SQL, []
    if stall_id: sql += "AND d.stall_id=? "; args.append(stall_id)
    if keyword: sql += "AND d.name LIKE ? "; args.append(f"%{keyword}%")
    if max_price: sql += "AND d.price<=? "; args.append(max_price)
    return enrich(q(sql + "LIMIT ?", args + [limit]))


@app.get("/dishes/new")
def new_dishes(days: int = 7):
    since = (utcnow() - timedelta(days=days)).isoformat(sep=" ", timespec="seconds")
    return enrich(q(DISH_SQL + "AND d.first_seen_at>=? ORDER BY d.first_seen_at DESC", (since,)))


class NewDish(BaseModel):
    stall_id: int
    name: str = Field(min_length=1, max_length=30)
    price: float = Field(gt=0, lt=200)


@app.post("/dishes")
def add_dish(body: NewDish, uid: int = Depends(current_user)):
    """众包加菜：先进入 pending，管理员审核后改为 active。"""
    did = run("INSERT INTO dish(stall_id,name,price,status,created_by) VALUES(?,?,?,'pending',?)",
              (body.stall_id, body.name, body.price, uid))
    return {"id": did, "status": "pending"}


# ---------- 评价 ----------
class ReviewIn(BaseModel):
    dish_id: int
    liked: bool
    tags: list[str] = Field(default_factory=list, max_length=5)
    text: str = Field("", max_length=200)
    meal: str | None = Field(None, pattern="^(breakfast|lunch|dinner|snack)$")


@app.post("/reviews")
def review(body: ReviewIn, uid: int = Depends(current_user)):
    """一键评价。每人每菜每天一条，重复提交则覆盖。"""
    if not q("SELECT 1 FROM dish WHERE id=? AND status='active'", (body.dish_id,)):
        raise HTTPException(404, "dish not found")
    now = utcnow() + timedelta(hours=8)  # 北京时间，用于时段分析
    run("""INSERT INTO review(user_id,dish_id,day,liked,tags,text,meal,hour,created_at)
           VALUES(?,?,?,?,?,?,?,?,datetime('now'))
           ON CONFLICT(user_id,dish_id,day) DO UPDATE SET liked=excluded.liked,
           tags=excluded.tags, text=excluded.text, meal=excluded.meal, hour=excluded.hour""",
        (uid, body.dish_id, now.strftime("%Y-%m-%d"), int(body.liked),
         json.dumps(body.tags, ensure_ascii=False), body.text, body.meal, now.hour))
    return {"ok": True}


@app.get("/dishes/{dish_id}")
def dish_detail(dish_id: int):
    d = q(DISH_SQL + "AND d.id=?", (dish_id,))
    if not d:
        raise HTTPException(404)
    d = enrich(d)[0]
    d["recent_reviews"] = q("""SELECT id, liked, tags, text, meal, created_at FROM review
                               WHERE dish_id=? AND text!='' ORDER BY id DESC LIMIT 10""", (dish_id,))
    return d


# ---------- 榜单 ----------
@app.get("/rank/top")
def top(limit: int = 20, min_n: int = 2):
    ds = [d for d in enrich(q(DISH_SQL)) if d["n"] >= min_n]
    return sorted(ds, key=lambda d: -d["score"])[:limit]


@app.get("/rank/avoid")
def avoid(limit: int = 20):
    """避雷榜：评价数足够且综合分最低。bad_tags 即差评高频标签。"""
    ds = [d for d in enrich(q(DISH_SQL)) if d["n"] >= MIN_AVOID_N and d["dislike_rate"] >= 0.4]
    return sorted(ds, key=lambda d: d["score"])[:limit]


@app.get("/stalls/{stall_id}/timeslots")
def timeslots(stall_id: int):
    """窗口分时段好评率，用于发现"晚餐最后半小时变差"这类踩雷窗口。"""
    return q("""SELECT r.hour, COUNT(*) AS n, ROUND(AVG(r.liked), 3) AS like_rate
                FROM review r JOIN dish d ON d.id=r.dish_id
                WHERE d.stall_id=? AND r.hour IS NOT NULL GROUP BY r.hour ORDER BY r.hour""", (stall_id,))
