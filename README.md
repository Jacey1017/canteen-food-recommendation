# 校园食堂点评推荐

帮助学生发现食堂新菜品、避开踩雷窗口的微信小程序。吃完饭 10 秒内点一下 👍/👎 加几个标签就能完成评价，系统据此给出推荐榜和避雷榜。

## 功能

- 找菜：食堂 → 窗口 → 菜品逐级浏览（窗口带评分），支持菜名搜索
- 一键评价：👍/👎 + 标签 + 可选一句话，自动记录餐次和时段
- 今天能吃到的：今天被评价过或被标记"今天有这道菜"的菜品，按好评率排序
- 好评榜、避雷榜（附差评高频标签，如"太咸"），菜品和窗口两个维度
- 本周新菜
- 窗口分时段好评率，用来发现"某个时段容易踩雷"
- 众包加菜，新增菜品先进入待审核状态

## 技术栈

| 部分 | 技术 |
|---|---|
| 后端 | Python、FastAPI、SQLite（标准库 `sqlite3`） |
| 认证 | 微信 `wx.login` 换 openid，签发 JWT |
| 前端 | 原生微信小程序 |

## 项目结构

```
canteen/
├── main.py            # 后端：全部接口、评分算法
├── seed.py            # 导入示例数据
├── test_smoke.py      # 冒烟测试
├── requirements.txt
└── miniprogram/       # 小程序前端（用微信开发者工具打开）
    ├── pages/index    # 今日推荐（今天能吃到的、好评榜、新菜）
    ├── pages/browse   # 找菜：食堂 → 窗口、搜索
    ├── pages/stall    # 窗口下的菜品列表
    ├── pages/avoid    # 避雷榜（踩雷窗口 + 踩雷菜品）
    ├── pages/dish     # 菜品详情 + 一键评价 + 标记今天有售
    └── utils/api.js   # 请求封装、自动登录
```

## 快速开始

需要 Python 3.9 或更高版本。

### 1. 启动后端

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed.py                   # 导入示例数据，只需执行一次
uvicorn main:app --reload
```

启动后访问 http://127.0.0.1:8000/docs 可以直接在网页上试接口。

### 2. 运行小程序

1. 安装[微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 导入 `miniprogram/` 目录，AppID 选测试号
3. **详情 → 本地设置**，勾选"不校验合法域名、web-view（业务域名）、TLS 版本以及 HTTPS 证书"
4. 保持后端运行，点击编译

### 3. 运行测试

```bash
pytest -q
```

## 配置

通过环境变量配置，不要把真实值写进代码或提交到仓库。

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DB_PATH` | SQLite 文件路径 | `canteen.db` |
| `JWT_SECRET` | JWT 签名密钥，**上线必须修改** | 开发用占位值 |
| `WX_APPID` | 小程序 AppID | 未设置 |
| `WX_SECRET` | 小程序 AppSecret | 未设置 |

未设置 `WX_APPID` 时，登录接口进入开发模式，直接用传入的 `code` 当作用户标识，仅用于本地调试。

## 接口

需要登录的接口在请求头带 `Authorization: Bearer <token>`，token 由 `/auth/login` 返回。

| 方法 | 路径 | 说明 | 登录 |
|---|---|---|---|
| POST | `/auth/login` | 用 `wx.login` 的 code 换 token | 否 |
| GET | `/canteens` | 食堂列表 | 否 |
| GET | `/stalls?canteen_id=` | 某食堂的窗口，带评分 | 否 |
| GET | `/dishes` | 菜品列表，参数：`stall_id`、`keyword`、`max_price`、`limit` | 否 |
| GET | `/dishes/new?days=7` | 近几天新增的菜品 | 否 |
| GET | `/dishes/today` | 今日有售：今天被评价或被标记过的菜 | 否 |
| GET | `/dishes/{id}` | 菜品详情和最近评价 | 否 |
| POST | `/dishes` | 众包加菜，进入待审核 | 是 |
| POST | `/dishes/{id}/available` | 标记"今天有这道菜"，每人每菜每天一条 | 是 |
| POST | `/reviews` | 提交评价，同一用户同一菜品每天一条，重复提交覆盖 | 是 |
| GET | `/rank/top` | 推荐榜 | 否 |
| GET | `/rank/avoid` | 避雷菜品榜 | 否 |
| GET | `/rank/stalls?worst=` | 窗口榜，`worst=true` 为踩雷窗口 | 否 |
| GET | `/stalls/{id}/timeslots` | 窗口分时段好评率 | 否 |

## 评分算法

菜品得分是**带时间衰减的贝叶斯平均好评率**，范围 0 到 1：

- **贝叶斯平均**：评价很少时，得分向全站平均好评率靠拢，避免一两条评价就把菜品顶到榜首或打入谷底。先验权重相当于 5 条虚拟评价。
- **时间衰减**：评价权重按半衰期 14 天指数衰减，菜品换厨师或供应商后，近期评价更有参考价值。
- **窗口得分**：把窗口下所有菜品的评价合并，用同样的公式计算。
- **避雷榜**：评价数不少于 3 条，且差评率不低于 40%，按得分从低到高排序，菜品和窗口都适用。

参数在 `main.py` 顶部：`HALF_LIFE_DAYS`、`PRIOR_N`、`MIN_AVOID_N`。

## 上线前待办

- [ ] 众包菜品的审核接口（目前 `pending` 状态只能手动改库）
- [ ] 评价内容安全检查（微信 `msgSecCheck`）
- [ ] 接口限流和异常评价检测（含"今日有售"标记的防恶意：目前一个人标记就算有售）
- [ ] 个性化：价格、口味、忌口筛选
- [ ] 菜品 CSV 批量导入
- [ ] 数据库换 PostgreSQL，并做定期备份
- [ ] 已备案的 https 域名，配置到小程序后台，并修改 `miniprogram/utils/api.js` 中的 `BASE`

## License

待定。
