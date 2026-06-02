# 📈 股票 K 线同图对比工具

多只 A 股 K 线叠加在同一张图上，涨跌幅 % 归一化对比，方便比较走势强弱。

## 功能

| 功能 | 说明 |
|------|------|
| **多股同图** | 全部股票 K 线蜡烛叠加，各自独立配色 |
| **涨跌幅 %** | 以起始日收盘价为 0% 基准，归一化对比 |
| **成交量** | 彩色柱叠加，透明度分层 |
| **5MA 均线** | 每只股票同色虚线显示自身 5 日均线 |
| **智能搜索** | 股票代码 / 中文名称 / 拼音首字母 |
| **历史记录** | 自动保存在浏览器，无需登录 |
| **时间范围** | 7/15/30/60/120 日 + 自定义 |
| **交互** | 缩放、平移、悬停查看数据 |

## 快速开始

### 本地运行

```bash
cd stock-kline-tool
pip install -r requirements.txt
streamlit run app.py
```

浏览器打开 http://localhost:8501

### 在线部署（免费）

1. 把 `stock-kline-tool/` 推送到 GitHub 仓库
2. 注册 [Streamlit Community Cloud](https://streamlit.io/cloud)
3. 点 **New app** → 选择你的仓库 → 填写入口文件为 `app.py`
4. 部署完成，得到一个 `https://xxx.streamlit.app` 链接

> 免费版应用闲置后会休眠，可用 [UptimeRobot](https://uptimerobot.com/) 每 5 分钟 ping 一次保持唤醒。

## 项目结构

```
stock-kline-tool/
├── app.py              # Streamlit 主界面
├── data_fetcher.py     # 多信源并行抓取（新浪日K + baostock）
├── chart_engine.py     # Plotly 多股 K 线同图绘制
├── stock_list.py       # 全量 A 股搜索（5524 只）
├── stock_index.json    # 拼音索引（自动生成）
├── build_index.py      # 重建股票索引脚本
├── requirements.txt    # Python 依赖
├── packages.txt        # Streamlit Cloud 系统依赖
└── .gitignore
```

## 数据源

| 源 | 角色 | 说明 |
|----|------|------|
| **新浪日K** | 主源 | Tier 1，~0.7s，稳定 |
| **baostock** | 备选 | Tier 2，Sina 失效时自动切换 |

两源并行请求，谁先返回用谁。

## 技术栈

- **前端**：Streamlit
- **图表**：Plotly
- **数据**：新浪财经 API / baostock
- **缓存**：SQLite (WAL 模式)
- **搜索**：pypinyin 拼音索引
- **历史**：浏览器 localStorage

## 自定义

### 重建股票索引

```bash
python build_index.py
```

从新浪重新拉取全量 A 股列表（约 5500 只），重新生成拼音索引。

## License

MIT
