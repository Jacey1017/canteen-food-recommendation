"""导入示例数据：python seed.py   （正式数据请按同样结构录入/CSV 导入）"""
import json
import main

DATA = {
    "一食堂": {"位置": "东区", "窗口": {
        "麻辣烫": [("麻辣烫（自选）", 15), ("藤椒鸡腿饭", 14)],
        "面食窗口": [("牛肉面", 13), ("西红柿鸡蛋面", 9)]}},
    "二食堂": {"位置": "西区", "窗口": {
        "盖浇饭": [("宫保鸡丁饭", 12), ("鱼香肉丝饭", 11)],
        "轻食": [("鸡胸肉沙拉", 18)]}},
}

for cname, c in DATA.items():
    main.run("INSERT OR IGNORE INTO canteen(name,location) VALUES(?,?)", (cname, c["位置"]))
    cid = main.q("SELECT id FROM canteen WHERE name=?", (cname,))[0]["id"]
    for sname, items in c["窗口"].items():
        if main.q("SELECT 1 FROM stall WHERE canteen_id=? AND name=?", (cid, sname)):
            continue  # 已导入过，保持幂等
        sid = main.run("INSERT INTO stall(canteen_id,name,open_hours) VALUES(?,?,?)", (cid, sname, "07:00-20:30"))
        for name, price in items:
            main.run("INSERT INTO dish(stall_id,name,price,tags) VALUES(?,?,?,?)",
                     (sid, name, price, json.dumps([], ensure_ascii=False)))
print("seeded")
