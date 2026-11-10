# 原版 Human Benchmark Reaction Time 逻辑 & 与本地复刻的差异

对照对象：

- 原版：`original/index-BOhEtgge.js`（humanbenchmark.com 生产构建，Vite/React 18 + styled-components）
  - 第 1078 行：`Fz / jz / zz / Mh / sw`（常量、初始 state、reducer、随机等待、平均分）
  - 第 1079–1129 行：styled component `Bz`（各 phase 背景色）
  - 第 1130 行：React 组件 `Hz`（reaction time 页面）
  - 第 931 行：`qi` / `q3` / `xz`（结算面板、"Save score" 提交）
- 本地：`../app.js`、`../index.html`、`../style.css`

下面代码均为该 bundle 手工反压缩后的等价形态（变量名保持原样，便于回查）。

---

## 一、原版的完整逻辑

### 1. 常量与初始状态

```js
Fz = 5;                              // 一次测试 5 个 trial
Q3 = { phase: "splash", trials: [] };
jz = Q3;                             // useReducer 初始 state
```

phase 取值：`splash | waiting | go | result | scold | score`

（CSS 里还留着 `view-saving`、`view-leaderboard`、`.progress .tries/.average` 的样式，属旧版本残留。）

### 2. 随机等待时长

```js
function Mh() {
  return { timeWaited: ~~((2500 + Math.random() * 2500) * 1) };
}
```

- 每个 trial 在开始等待时生成一个 `currentTrial`，只有 `timeWaited` 一个字段。
- `~~` 截断 → 整数，范围 **2500–4999 ms**。

### 3. reducer（状态机与计时打点）

```js
function zz(e, t) {
  switch (t.type) {
    case "click":
      switch (e.phase) {
        case "splash":
          return { ...e, currentTrial: Mh(), phase: "waiting" };

        case "waiting":                       // 绿灯前点击
          return { ...e, phase: "scold" };

        case "go": {
          const n = new Date;                 // 点击时刻（墙钟）
          return {
            ...e,
            trials: [...e.trials, {
              ...e.currentTrial,
              clickedTime: n,
              result: n.getTime() - e.currentTrial.turnedGreenTime.getTime()
            }],
            currentTrial: undefined,
            phase: e.trials.length + 1 >= Fz ? "score" : "result"
          };
        }

        case "scold":                         // 点掉 "Too soon!" 的同时开始下一轮等待
          return { ...e, currentTrial: Mh(), phase: "waiting" };

        case "result":                        // 点掉单次结果，开始下一轮等待
          return { ...e, currentTrial: Mh(), phase: "waiting" };

        case "score":                         // 结算页点击 = 空操作
          return e;

        default:
          throw new Vk(e.phase);
      }

    case "enterGoPhase":                      // 变绿：时间戳在这里打
      return {
        ...e,
        phase: "go",
        currentTrial: { ...e.currentTrial, turnedGreenTime: new Date }
      };

    case "reset":
      return Q3;                              // 回 splash，清空 trials
  }
}
```

要点：

- **绿灯时间戳 `turnedGreenTime` 写在 reducer 内**，即 `setTimeout` 回调 dispatch 的那一刻。此时 React 尚未 render/commit，绿灯还没上屏。
- 时间戳用的是 `new Date()`（系统墙钟，1ms 分辨率，受系统时间调整影响）。
- 单次结果 `result` 直接就是两个整数毫秒之差，不做四舍五入、不做任何过滤。
- `scold` 和 `result` 都由**同一次点击**直接进入下一轮 `waiting`，不自动推进。
- `score` 阶段点击整块无效（必须按 "Save score" / "Try again"）。

### 4. 组件与事件

```js
function Hz() {
  const [e, t] = useReducer(zz, jz);

  useEffect(() => {
    if (e.phase === "waiting") {
      const r = window.setTimeout(() => t({ type: "enterGoPhase" }), e.currentTrial.timeWaited);
      return () => window.clearTimeout(r);      // 换 phase / 换 trial / 卸载时清掉
    }
  }, [e.currentTrial, e.phase]);

  const n = () => t({ type: "click" });         // 所有点击都收敛成一个 "click" action

  return (
    <Bz
      onMouseDown={e.phase !== "score" ? n : undefined}
      onTouchStart={e.phase !== "score" ? n : undefined}
      onTouchEnd={e.phase !== "score" ? zo : undefined}   // zo = stopPropagation + preventDefault
      className={"view-" + e.phase}
      style={{ cursor: e.phase !== "score" ? "pointer" : "default" }}
    >
      ...
    </Bz>
  );
}
```

- **无 rAF**，无 `performance.now()`，无键盘支持。
- 鼠标 + 触摸双通道：触摸时 `onTouchEnd` 的 `preventDefault` 抑制浏览器合成的 mousedown，避免一次点击记两下。
- 计时器在 `useEffect` 里启动 → 红线屏已经上屏（commit+paint 之后）才开始计时。
- 没有防连点/防陈旧回调的额外机制，靠 effect cleanup 的 `clearTimeout` 保证。

### 5. 各 phase 的渲染

| phase | 背景 | 内容 |
| --- | --- | --- |
| `splash` | `#2B87D1` | 图标 + "Reaction Time Test" + "When the red box turns green, click as quickly as you can." / "Click anywhere to start."（带 0/300ms 延迟的淡入） |
| `waiting` | `#ce2636` | ⚠ 图标 + "Wait for green" |
| `go` | `#4BDB6A` | ⚠ 图标 + "Click!" |
| `result` | `#2B87D1` | 时钟图标 + `<上一次 result> ms` + "Click to keep going" |
| `scold` | `#2B87D1` | 感叹号图标 + "Too soon!" + "Click to try again." |
| `score` | `#2B87D1` | `qi`：大图标 + `sw(e).toFixed()+"ms"` + "Save score" / "Try again" |

- 背景色是 styled component 的静态 class 切换，**没有 transition**，变色是瞬时的。
- 内层内容包了 `.anim-slide-fade-in`（`slideFadeIn`：opacity 0→1、translateY 20px→0，0.5s ease-out），但该节点没有 `key`，跨 phase 复用同一个 DOM 节点，动画只在首次挂载时跑一次，不影响绿灯时机。

### 6. 得分与提交

```js
function sw(e) {
  let t = 0;
  for (let n of e.trials) t += n.result;
  return t / e.trials.length || 0;      // 纯算术平均，无剔除
}
```

- 显示：`sw(e).toFixed(0) + "ms"`；提交：`qi → q3 → xz().save({ testId: "reactiontime", score: sw(e) })`
- `save()` → `POST /api/v4/scores`，成功后 `navigate("/dashboard")`。
- **没有任何本地持久化**：历史、排行榜都在服务端，需要登录；"Try again" 走 `dispatch({type:"reset"})`。
- 右侧 Statistics 面板用打包内置的全局直方图 `oM.reactiontime`（25ms 一档的 count）画分布图，不请求网络；关于文字里写"平均（中位）反应时间 273 ms"。

### 7. 一次完整测试的时序

```
splash ──click──▶ waiting ──timeWaited(2500–4999ms)──▶ go ──click──▶ result(1..4 次) ──click──▶ waiting ...
   │                  └──click──▶ scold ──click──▶ waiting（新的 timeWaited）
   └──第 5 次 click──▶ score ──"Save score"──▶ POST /api/v4/scores ──▶ /dashboard
```

---

## 二、与本地复刻的差异

### 差异总表

| 维度 | 原版 | 本地 |
| --- | --- | --- |
| 时钟源 | `new Date()`（墙钟，1ms） | `performance.now()`（单调，亚毫秒） |
| 绿灯打点位置 | reducer 内（`setTimeout` 回调 dispatch 时，早于 render/paint） | `requestAnimationFrame` 回调内，与切换 class 同一行 |
| 点击打点位置 | `onMouseDown`/`onTouchStart` 处理器里 `new Date` | `pointerdown` 处理器里 `performance.now()` |
| 单次结果 | `click - green` 的整数差值 | `Math.round(perf - goTime)` |
| 等待时长 | `2500 + rand*2500`，取整 → 2500–4999ms | `2500 + rand*3000` → 2500–5500ms |
| 计时器启动时机 | `useEffect` 内，红线已上屏 | `beginWait()` 内同步 `setTimeout`，红线尚未 paint |
| 输入通道 | mousedown + touchstart，touchend 里 `preventDefault` 防双触发 | 单一 `pointerdown`；额外支持 Space/Enter；用 `closest("button,a,label,input")` 过滤可交互元素 |
| 键盘 | 无 | 空格 / 回车 |
| 轮数 | 5（`Fz`） | 5（`ROUNDS_PER_TEST`） |
| 得分算法 | 全部 5 次的算术平均 | `computeStats()`：以 `min(mean, median)` 为基线，剔除偏离 >150ms 的尝试（默认开启） |
| 结果展示精度 | `toFixed(0)` | `Math.round()`（等价） |
| 单次结果页 | 只有 "xxx ms / Click to keep going" | 同上，另加 attempts 列表与剔除说明 |
| 结束页 | `score`：点击视口无效，必须点 "Save score"/"Try again" | `final`：**点击任意处即回到开始页**（`toStartScreen`），另有 "Try again" |
| 持久化 | 无本地存储，服务端 `POST /api/v4/scores` | `localStorage`：`reactionTimeHistory`（上限 200 条）+ `reactionTimeOutlierPref`；历史表格 + 清空 + 剔除提示 |
| 统计对比 | 内置全局分布直方图（`oM.reactiontime`，endIdx 20） | 无 |
| 状态管理 | `useReducer` 状态机（6 phase） | 命令式 `phase` 字符串 + 直接操作 DOM |
| 文案/配色 | "Wait for green" / "Click!" / "Too soon!" / "Click to try again."；`#ce2636` / `#4BDB6A` / `#2B87D1`，无 transition | 完全一致 |
| 防陈旧回调 | 仅 effect cleanup 的 `clearTimeout` | 额外 `waitGen` 代际号 + `cancelAnimationFrame` |

### 1. 测量偏差（最值得注意）

两边都把"绿灯时间戳"打在实际 paint 之前，所以读数里的 `measured = (paint − stamp) + 真实反应`，那一段 `paint − stamp` 是白送的：

- 原版：`setTimeout` 回调 → dispatch → React render/commit → 下一帧 paint。差值是**不到一帧到一帧多**（~0–16ms，慢设备上更多）。
- 本地：`rAF` 回调里改 class + 打点，紧接同一帧的 style/paint。差值只有几毫秒。

所以**同样手速下，本地读数会比原版小约 0–16ms（通常几 ms）**。要和对岸数字可比，需要把打点方式对齐（见第三节）。另外 `app.js` 里"打点就在 paint 那一刻"的注释并不严格准确——rAF 回调之后才 paint，只是差距小得多。

### 2. 得分算法不可比

原版是 5 次的纯平均，慢的那次照样计入并提交服务器。本地默认剔除"偏离 `min(mean, median)` 超过 150ms"的尝试，会把显示值压得比原版低。这是复刻版自创的规则，不是 HB 行为。

### 3. 收尾阶段行为反了

原版 `score` 阶段对页面点击完全无响应（避免误重置、也避免没有点击目标）；本地 `final` 阶段点击任意位置直接 `toStartScreen()`，用户想点 "Try again" 时手一抖就重置。

### 4. 其它细节

- 原版 `new Date` 写在 reducer 里，reducer 不纯（理论上 StrictMode 双跑/并发渲染下会取到不同时刻）；本地把时钟放在模块作用域，没有这个隐患。
- 原版双击/连点没有专门防护，第二次点击会落在下一 phase 上（`go` 双击 → 记住结果后立刻开始下一轮等待）；本地靠同步更新的 `phase` 变量，行为基本一致。
- 原版 `scold`/`result` 阶段点一下即开始新一轮；本地 `early` 阶段点一下 `beginWait()`，行为相同（`app.js` 里"不自动推进"的注释是对自己早期版本的说明，与原版一致）。

---

## 三、若要更贴近原版的最小改动

1. `app.js` 的 `turnGreen()`：去掉 rAF，直接在 `setTimeout` 回调里切 class 并 `goTime = performance.now()`（对齐打点位置；若坚持 rAF，则接受本地偏快几毫秒）。
2. `beginWait()`：`delay = 2500 + Math.random() * 2500`。
3. 计时器改到 `requestAnimationFrame`/微任务之后启动，模拟"红线已上屏再开始等待"（可选，影响 <1 帧）。
4. 默认关闭离群值剔除（或仅做展示、不参与均值），让分数与原版同义。
5. `final` 阶段点击不重置：只在 "Try again" 按钮上响应。
6. （可选）去掉键盘触发，或保留但明确这是增强项；保留 `pointerdown` 反而比原版更稳（无非双触发问题）。
