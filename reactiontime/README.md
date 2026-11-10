# Reaction Time Test

Human Benchmark [反应时间测试](https://humanbenchmark.com/tests/reactiontime) 的本地复刻：红屏随机等待后变绿，看到绿色就点，测 5 次取平均。

线上体验：<https://react.crazyh.fun/>

## 玩法

1. 点任意位置开始，屏幕变红等待。
2. 变绿的瞬间点一下，记录本次反应时间。
3. 满 5 次给出平均值，结果自动存在浏览器里，下方历史表格可回看。

支持鼠标/触摸，也支持空格、回车。历史记录在 `localStorage`。

## 运行

纯静态页面，无需构建。直接打开或任意静态服务器指向本目录即可：

```bash
python -m http.server 8000
# 打开 http://localhost:8000
```