# 上线方案：GitHub + 免费部署

## 核心架构

```
GitHub Repo ──auto-deploy──→ Streamlit Community Cloud (免费)
                                    │
                                    ├── SSL (自动)
                                    ├── 全球 CDN (自动)
                                    └── 100 用户 (免费额度够)
```

## 部署方案对比

| 方案 | 月费 | 运维 | 适合 |
|-----|------|------|------|
| **A. Streamlit Cloud** 🏆 | **$0** | 0 | 推荐 |
| B. 香港 VPS + Docker | ~$5-10 | 中 | 升级可选 |
| C. GitHub Pages | $0 | 低 | ❌ 不能跑 Python |

**推荐方案 A**：推送 GitHub → 自动部署到 Streamlit Cloud，自带 HTTPS 和域名。

---

## 不登录也能保存历史吗？

**可以。用浏览器 localStorage**。

原理：注入少量 JavaScript，把用户的股票历史存到他**自己的浏览器**里，不经过服务器。

```
用户添加股票 → 存入 localStorage (浏览器本地)
用户下次来 → 从 localStorage 读出 → 展示在侧边栏
```

这样：
- ✅ 无需登录
- ✅ 每个用户看到自己的历史
- ✅ 关闭页面再打开还在
- ✅ 不占服务器任何存储
- ❌ 清浏览器缓存会丢（可接受）

---

## 需要改动的代码

| 改动 | 原因 | 工作量 |
|------|------|--------|
| 1. `requirements.txt` 锁定版本 | 避免 Linux 上装错版本 | 5 分钟 |
| 2. `data_fetcher.py` SQLite 改 WAL 模式 | 100 人并发写不冲突 | 2 分钟 |
| 3. `app.py` 历史改用 localStorage | 不登录也能保存 | 30 分钟 |
| 4. 加 `packages.txt` | Streamlit Cloud 需要底层依赖 | 2 分钟 |
| 5. 加 `.gitignore` | 不上传 cache.db / __pycache__ | 2 分钟 |
| 6. baostock 降级为备备选 | Linux 上可能不可用 | 确认即可 |

---

## 100 用户够不够？

**够。** Streamlit Cloud 免费额度：
- 1 个应用
- 1 GB 内存
- 请求量无硬上限

100 个散户级别的使用（每人每天看 5-10 次）完全无压力。

唯一注意：免费版**应用闲置一段时间后会休眠**，下次访问等 10-30 秒唤醒。
解决：加一个免费的 UptimeRobot 每 5 分钟 ping 一次，就不休眠了。

---

## 执行步骤

1. 我把代码改好（上述 1-6 项）
2. 你推送 GitHub
3. 注册 streamlit.io → 连接 GitHub repo → 点 Deploy
4. 搞定上线

---

要开始吗？还是你有其他想调整的地方？
