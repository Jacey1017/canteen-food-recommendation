"""冒烟测试：pytest -q"""
import os, tempfile
os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")

from fastapi.testclient import TestClient
import main, seed  # noqa  (seed 会写入示例数据)

c = TestClient(main.app)


def login(name):
    return {"Authorization": "Bearer " + c.post("/auth/login", json={"code": name}).json()["token"]}


def test_flow():
    assert len(c.get("/canteens").json()) == 2
    dishes = c.get("/dishes").json()
    good = next(d for d in dishes if d["name"] == "牛肉面")["id"]
    bad = next(d for d in dishes if d["name"] == "麻辣烫（自选）")["id"]

    # 无 token 不能评价
    assert c.post("/reviews", json={"dish_id": good, "liked": True}).status_code == 401

    for i in range(4):  # 4 个用户给好菜好评，给雷菜差评
        h = login(f"u{i}")
        assert c.post("/reviews", json={"dish_id": good, "liked": True, "meal": "lunch"}, headers=h).status_code == 200
        assert c.post("/reviews", json={"dish_id": bad, "liked": False, "tags": ["太咸", "凉了"], "meal": "dinner"}, headers=h).status_code == 200

    # 同一用户同一天重复评价 = 覆盖，不增加条数
    c.post("/reviews", json={"dish_id": bad, "liked": False}, headers=login("u0"))
    assert c.get(f"/dishes/{bad}").json()["n"] == 4

    top = c.get("/rank/top").json()
    assert top[0]["id"] == good
    av = c.get("/rank/avoid").json()
    assert [d["id"] for d in av] == [bad]
    assert "太咸" in av[0]["bad_tags"]

    # 众包加菜进入 pending，不出现在列表
    h = login("u9")
    r = c.post("/dishes", json={"stall_id": 1, "name": "新菜", "price": 10}, headers=h).json()
    assert r["status"] == "pending"
    assert all(d["name"] != "新菜" for d in c.get("/dishes").json())

    assert c.get("/dishes/new").json()  # 刚录入的都算新菜
    assert c.get("/stalls/1/timeslots").status_code == 200
