# 用代码描述动画：主流框架的内部抽象，与「最小完备形式化」的架构结论

**要回答的问题**：什么样的最小形式化，既**完备**（任何人类能想出的动效都能表达），又**紧凑**（描述越复杂的效果越省笔墨，而不是越写越长）？

**取证纪律**：本文每条事实附来源 URL。源码证据取自 npm 包（jsDelivr 解包）与 GitHub raw；官方文档取自官方站点。**六个研究方向分派独立子代理取证，其 URL 逐条要求实测 HTTP 200**；凡未命中者一律写「未找到」，不做推断填充。**A~E 五节的结论是本文自己的综合**（标注为「本文推断」），不假托任何框架作者。

---

## 1. Motion Canvas（TypeScript）

### 1.1 核心抽象：这里没有「Signal 类」

题面假设的 `Signal` 类与 `signal()` 包装常量**在本版本不存在**（v3.17.2，全仓 grep 0 命中）。`Signal<S,T,Owner>` 是**接口**：它同时是 `SignalSetter`（1 参=写）/ `SignalGetter`（0 参=读）/ `SignalTween`（3–4 参=补间）。运行时是 `SignalContext.toSignal()` 返回的**被 bind 的函数对象**，靠 `invoke()` 按实参个数分派：

```ts
invoke(value, duration, timingFunction = easeInOutCubic, interpolationFunction = this.interpolation) {
  if (value === undefined)      return this.get();
  if (duration === undefined)   return this.set(value);
  const queue = this.createQueue(timingFunction, interpolationFunction);
  return queue.to(value, duration);
}
```
 来源：[SignalContext.ts](https://github.com/motion-canvas/motion-canvas/blob/main/packages/core/src/signals/SignalContext.ts)（自取：`@motion-canvas/core@3.17.2/lib/signals/SignalContext.js`）

**「某一时刻的值」成为一等公民，靠的是三合一调用签名，而不是新类型**：`radius` 这个对象既是当前值、又是写入口、又是"从当前值补间到目标"的入口。题面所问的 `signal()` 包装位，实际由类型 `SignalValue<T> = T | (() => T)` 承担（`isReactive(v) = typeof v === 'function'`）**任何值都可以是字面量，也可以是惰性求值函数**。

### 1.2 依赖追踪不是注册出来的，是 getter 现场采集的

```ts
getter() {
  if (this.event.isRaised() && isReactive(this.current)) {
    this.clearDependencies();
    this.startCollecting();
    this.current ... this.last = this.parse(this.current());
    this.finishCollecting();
  }
  this.event.reset();
  this.collect();
  return this.last;
}
```
官方文档把三条性质写明（[motioncanvas.io/docs/signals](https://motioncanvas.io/docs/signals/)）：**Laziness / Caching / Dependency tracking**；lazy 靠 `event` 脏标记 + `last` 缓存。收集栈是静态的，重入即抛 `'A circular dependency occurred between signals.'`。

**`CompoundSignal` 的关键是「父值从子值实时聚合」**，所以不存在父子同步问题：

```ts
getter() { return this.parse(Object.fromEntries(this.signals.map(([key, p]) => [key, p()]))); }
```
子信号用 `Object.defineProperty(this.invokable, key, {value: signal})` 挂成属性；`Vector2SignalContext` 的 `add/mul/div/sub/dot/cross/mod/edit` 每个都是**双签名重载**：无 `duration` → 返回 `TOwner`（同 set），有 `duration` → 返回 `SignalGenerator`。

### 1.3 时间模型：谁拥有时间，一帧怎么被推进

```
PlaybackManager(frame, fps=30, speed)          ← 唯一时钟
  └ PlaybackStatus.deltaTime = framesToSeconds(1) * speed
      └ threads() 每轮读 deltaTime → thread.update(dt)
          └ Thread.time  ← 本身就是一个 createSignal(0)
```
`threads()` 是整个动画的调度器（**以下为源码原文片段**，[threads.ts](https://raw.githubusercontent.com/motion-canvas/motion-canvas/main/packages/core/src/threading/threads.ts)）：

```ts
while (queue.length > 0) {
  const result = thread.next();
  if (result.done) { thread.cancel(); continue; }
  if (isThreadGenerator(result.value)) {          // yield 一个 generator
    const child = new Thread(result.value);
    thread.add(child);
    queue.push(thread); queue.push(child);        // 这就是「并发」的实现
  } else if (result.value) {                      // yield 一个 Promise
    thread.value = yield result.value;
    queue.push(thread);
  } else {                                        // 裸 yield
    thread.update(dt);                            // ← 只有裸 yield 才推进时间
    thread.drain(task => { ... newThreads.unshift(child); });
    newThreads.unshift(thread);
  }
}
```
**结论：每帧推进一次，而 `yield` 什么决定被推进什么。** 裸 `yield` = 消耗一帧；`yield gen` = 起并发；`yield* gen` = 同步委托。`View2D` 的时间就是 `PlaybackStatus`，无自持时钟。

### 1.4 三个时间算子的真实实现（全部源码原文）

```ts
// flow/waitFor.ts  挂起
const step = usePlayback().framesToSeconds(1);
const targetTime = thread.time() + seconds;
while (targetTime - step > thread.fixed) { yield; }
thread.time(targetTime);
// 源码注释：「subtracting the step is not necessary, but it keeps the thread time
//            ahead of the project time.」

// flow/all.ts  并发后汇合
export function* all(...tasks) { for (const t of tasks) yield t; yield* join(...tasks); }

// flow/sequence.ts  错落启动（注意：不等待前一个完成）
export function* sequence(delay, ...tasks) {
  for (const task of tasks) { yield task; yield* waitFor(delay); }
  yield* join(...tasks);
}

// flow/loop.ts  每轮现造 generator（generator 不可重置）
for (let i = 0; i < iterations; i++) {
  const generator = factory(i);
  if (generator) yield* generator; else yield;
}

// threading/join.ts  汇合后把父时钟拉到子时钟最大值
while (threads.find(t => !t.canceled)) { yield; }
parent.time(Math.max(startTime, childTime));
```

### 1.5 Tween：唯一的逐帧原语

```ts
export function* tween(seconds, onProgress, onEnd) {
  const startTime = thread.time();
  const endTime = thread.time() + seconds;
  onProgress(0, 0);
  while (endTime > thread.fixed) {           // ← 与 fps 相关
    const time = thread.fixed - startTime;
    if (time > 0) onProgress(time / seconds, time);
    yield;
  }
  thread.time(endTime);
  onProgress(1, seconds);
}
```
`spring` 走**另一条可复现性路线**：固定步长 120Hz 物理积分（`const simulationFrames = 120;`），刻意与 fps 解耦；7 个命名预设 `BeatSpring/PlopSpring/BounceSpring/SwingSpring/JumpSpring/StrikeSpring/SmoothSpring`。默认插值是 `deepLerp`（对象/数组/Map 天然可补间），默认缓动 `easeInOutCubic`。

**已核实的题面错项**：`toSignal` / `toSignalAsync` / `toCompletion` / `duration()` / `smoothStep` / `threading/Generators`  **全部 0 命中（未找到）**。本版本不存在「generator → 随时间变化的 signal」这条路；最接近的是 `createComputed` / `createComputedAsync`。

### 1.6 压缩与逃生口

| 机制 | 压缩掉什么 |
|---|---|
| `SignalValue = T \| (() => T)` | 声明依赖/订阅/失效三份样板 → 上下文即依赖图 |
| `CompoundSignal` | 设 `x` 要同步 `position` 的样板（一个声明三个入口） |
| `SignalGenerator` 的 `to/back/wait/run/do` | N 段动画 → N 个 `yield*` 压成一行链式 |
| `all/any/chain/sequence/delay/loop/loopFor/loopUntil` | 手写并发/串行/重复调度 |
| `spring` 的 7 个命名预设 | 三个物理参数 → 一个名字（"手感"成为一等公民） |
| `deepLerp` 默认插值 | 每种类型写一个 lerp |
| `DEFAULT` symbol | 恢复默认值要重写默认值 |
| `useDuration('event')` | 把时长从代码移到时间轴数据里 |

**逃生口三档粒度**：逐属性（signal 第 3/4 参换缓动与插值）→ 逐帧（`tween` 的 progress 闭包）→ 逐线程（`spawn/run/threads/every/yield promise/useThread().time(t)`）。
**代价（源码可证）**：① **不可序列化**signal 当前值本就可能是闭包，`raw()` 只能原样返回闭包；② **时钟一致性可被打破**`waitFor` 注释直认线程时间与项目帧时间是两个量；③ **fps 依赖分叉**`tween` 依赖 `thread.fixed`，`spring` 固定 120Hz；④ **性能**依赖闭包每次脏标记就整棵重跑。

---

## 2. Remotion（React）

### 2.1 帧函数模型：整个组件就是一个 `f(frame)`

```ts
export const useCurrentFrame = (): number => {
  const frame = useTimelinePosition();
  const context = useContext(SequenceContext);
  const contextOffset = context ? context.cumulatedFrom + context.relativeFrom : 0;
  return (frame - contextOffset) * (context?.playbackRate ?? 1);   // ← Sequence 内自动相对化
};
```
官方原话把模型讲得最清楚：「**Think of your component as a function that transforms a frame number into an image.**」（[flickering](https://www.remotion.dev/docs/flickering)）

`<Series>` **不是新时间机制，是用 `<Sequence>` 递归拼出来的**，时长**相加**而非缩放：

```tsx
const currentStartFrame = startFrame + offset;
const nextStartFrame = startFrame + timelineDurationInFrames + offset;
```
`<Loop>` 编译成 `<Sequence from={iteration * iterationDurationInFrames}>`；`<Freeze>` 直接改写 timeline 上下文并把 `isPlaying` 置 false。

### 2.2 无状态：interpolate 是分段贪心映射；spring 是"无状态但 O(frame)"

```ts
function interpolateFunction(input, inputRange, outputRange, options) {
  // ... extrapolate: extend | clamp | identity | wrap
  result = (result - inputMin) / (inputMax - inputMin);   // 归一化
  result = easing(result);                                // 缓动
  return result * (outputMax - outputMin) + outputMin;
}
```
`spring` 的关键实现事实：**每次调用都从 frame 0 逐帧重算到当前帧**，再靠 `calculationCache`/`advanceCache` 兜住：

```ts
for (let f = 0; f <= Math.floor(frameClamped); f++) {
  animation = advance({animation, now: (f / fps) * 1000, config: resolvedConfig});
}
calculationCache[cacheKey] = animation;
```
物理量：`zeta = c / (2*sqrt(k*m))`、`omega0 = sqrt(k/m)`，欠阻尼/临界阻尼两支解析解。`measureSpring` 要求差值**连续 20 帧**低于 `threshold`（默认 0.005）才算稳定。`durationInFrames` 把曲线**拉伸**到指定时长（不改变形状），操作顺序 stretch → reverse → delay。

### 2.3 可预测性：五条机制，各自防什么

| 机制 | 防的是什么 |
|---|---|
| 纯函数约定四条 | ①每次调用视觉相同 ②不依赖帧被按序渲染 ③暂停时不动画 ④不依赖随机 |
| `random(seed)` 取代 `Math.random()` | 多标签页并行渲染时随机不可复现 |
| `delayRender` / `continueRender` / `cancelRender` | 资源未就绪就截图（默认 30s 超时） |
| 禁 `setTimeout` / CSS transition / `requestAnimationFrame` | 动画脱离 `useCurrentFrame` 后，并行渲帧会抖 |
| `--concurrency=1` | **逃生口而非修复**：官方明说更慢、时序仍不保证、且**会堵住 Lambda** |

### 2.4 压缩与逃生口

压缩：`interpolate` 分段（一个数组描述整条曲线族）、`spring` 用物理参数取代手写曲线、`Series/Sequence` 表达"顺序"、`useVideoConfig()` 提供 `fps/durationInFrames` 让时间写成相对量。
**逃生口粒度 = 整个组件**（最粗的一档）：不是"给动画留个洞"，而是"动画本身就是程序"。代价：必须满足四条确定性约定，否则并行渲染下不可复现。

**未找到**：`remotion.dev/docs/concurrency` → 404（并发语义改以 `/docs/flickering` 与 `/docs/cli/render#--concurrency` 为源）。

---

## 3. Manim（Python）

### 3.1 时间模型：不是全局帧，是「全局秒 + 每动画内部 alpha」

```python
def update_to_time(self, t: float) -> None:
    dt = t - self.last_t
    self.last_t = t
    for animation in self.animations:
        animation.update_mobjects(dt)
        alpha = t / animation.run_time        # ← 关键一行
        animation.interpolate(alpha)
```
`Scene.time` 直接代理 `renderer.time`（Cairo 按 `dt = 1 / self.camera.frame_rate` 累加）。**全局帧只存在于渲染器记账层。**

`Animation` 生命周期三段：`begin()`（拷起点 + `suspend_updating()` 避免双重推进）→ 每帧 `interpolate(alpha)` → `finish()`。

### 3.2 `lag_ratio` 的精确语义（源码公式）

对 submobject（[animation.py](https://raw.githubusercontent.com/ManimCommunity/manim/main/manim/animation/animation.py)）：
```python
lag_ratio = self.lag_ratio
full_length = (num_submobjects - 1) * lag_ratio + 1
value = alpha * full_length
lower = index * lag_ratio
return self.rate_func(value - lower)
```
对子动画（`AnimationGroup`）则是另一套：`lags = run_times[:-1] * self.lag_ratio; start[1:] = cumsum(lags); max_end_time = max(end)`。
**两套语义都是"把 N 次错落启动压成 1 个标量"**  这是本文找到的、表述"错落"最省笔墨的形式化（见 B 节）。

### 3.3 `.animate` 的真身与 updater

`.animate` 返回 `_AnimationBuilder`：构造即 `generate_target()`，方法调用记进 `methods` 并**立即作用到 target**，`build()` 返回 `_MethodAnimation(MoveToTarget)`，其 `finish()` 才把方法**只应用一次**到原 mobject。限制：动画参数必须在取方法**之前**传（之后 `cannot_pass_args=True` 抛错）。

```python
Mobject.add_updater(update_function, index=None, call_updater=False)
def update(self, dt=0, recursive=True):
    if "dt" in inspect.signature(updater).parameters:
        time_based_updater(self, dt)
    else:
        updater(self)
```
`always_redraw(func)` 本体就是 `mob.add_updater(lambda _: mob.become(func()))`。官方对 `.animate` 的警告很重要：它**在"前/后两组点"之间插值**，沿路径或旋转会不自然，要沿途形态得用 `ValueTracker` + updater。

### 3.4 压缩与逃生口

压缩靠**时间轴向量化**：`AnimationGroup` 预计算 `start/end` 数组，每帧只对"已开始且未结束"的子动画算 `sub_alpha`；`Succession`(lag_ratio=1) / `LaggedStart`(0.05) / `LaggedStartMap` 是同一机制的三个预设。
逃生口：`ValueTracker` + `add_updater`（逐帧回调，可表达任意状态）、`always_*` 系列、`turn_animation_into_updater`/`cycle_animation`、`Scene.always_update_mobjects`、`suspend_mobject_updating=False`。
**代价**：失去「纯 alpha 函数」的可分析性；唯一真正**有状态**的动画是 `PhaseFlow`（用 `last_alpha` 做离散积分）这恰好说明"无状态"在 Manim 里是一条被刻意维持的不变量。

---

## 4. GSAP Timeline

### 4.1 数据模型：有序双向链表 + 层级时间继承（不是"扁平列表 + ticker"）

`_addToTimeline` 按 `_start` 排序插入链表；子时间换算：
```
_parentToChildTotalTime = (parentTime - child._start) * child._ts + (child._ts >= 0 ? 0 : child._tDur)
```
ticker 是 rAF 心跳，`_gap = 1000/240`（默认 240fps 上限），`lagSmoothing(500, 33)`。`from()/fromTo()` 会先建一个零时长 set-tween 钉住起始值（`_startAt`，并设 `_dp = 0` 禁止回到根时间轴）。

### 4.2 position parameter：压缩时间描述的经典答案（源码级判据）

源码 `_parsePosition`（**原文**，取自 [gsap-core.js](https://raw.githubusercontent.com/greensock/GSAP/master/src/gsap-core.js)）：

```js
i = position.indexOf("=");
if (offset === "<" || offset === ">") {
  i >= 0 && (position = position.replace(/=/, ""));
  return (offset === "<" ? recent._start : recent.endTime(recent._repeat >= 0))
       + (parseFloat(position.substr(1)) || 0)
       * (isPercent ? (i < 0 ? recent : percentAnimation).totalDuration() / 100 : 1);
}
```

| 写法 | 语义 | 百分比基准 |
|---|---|---|
| `3` | 时间轴绝对 3s | — |
| 省略 | `"+=0"`（`position == null → clippedDuration`） | — |
| `"+=1"` / `"-=1"` | 末尾后 1s（空隙）/ 末尾前 1s（重叠） | — |
| `"<"` / `">"` | 上一个动画的**开始** / **结束** | — |
| `"<2"` ≡ `"<+=2"` | 上动画开始 + 2s（`=` 可省，源码先 `replace(/=/, "")` 归一） | — |
| `">-0.5"` | 上动画结束 − 0.5s | — |
| `"<25%"` | 上动画开始 + **上动画**总时长×25%（走 `i<0` 分支取 `recent`） | **上一个** |
| `"<+=25%"` | 上动画开始 + **被插入动画**总时长×25%（走 `i>=0` 取 `percentAnimation`） | **被插入** |
| `"myLabel+=30%"` | 标签处 + 被插入动画×30%；**label 不存在则自动建在末尾** | 被插入 |

**「上一个动画」= `_recent` = 最近一次插入的动画，不是时间轴上最靠末尾的那个**（官方文档脚注与源码一致）。

### 4.3 stagger：错落的参数化

```js
gsap.to('.box', { y: 100, stagger: 0.1 });                    // 数字简写 = {each: 0.1}
gsap.to('.box', { y: 100, stagger: {
  each: 0.1,                     // 或 amount: 1（总量摊薄）两者同一插槽的 || 短路，同时给 amount 赢
  from: 'center',                // 'start'|'center'|'edges'|'end'|'random'|索引|[x,y] 网格坐标
  grid: 'auto', axis: 'x',       // grid 用 getBoundingClientRect() 当场算列数（resize 后不重算）
  ease: 'power2.inOut',          // 用缓动分布启动时刻
  repeat: -1                     // 放 stagger 内 = 逐元素重复；放顶层 = 整段重复
}});
stagger: function (index, target, list) { return index * 0.1; }  // 返回「相对起点的总延迟」
```
`from:"random"` **不需要**`gsap.utils.shuffle` 配合（源码内部已 `shuffle(distances)`）。stagger 实际被**编译成一条内部嵌套 Timeline**。

### 4.4 复用与逃生口

```js
gsap.registerEffect({
  name: "fade",
  effect: (targets, config) => gsap.to(targets, {duration: config.duration, opacity: 0}),
  defaults: {duration: 2},
  extendTimeline: true,          // 之后可 tl.fade(".box", {duration:3}, "+=2")
});
```
硬约束：`extendTimeline: true` 的效果**必须返回 Tween 或 Timeline**（可被插入时间轴的东西）。`gsap.timeline({paused:true})` 是"参数化效果函数"的另一范式。
逃生口：`onUpdate` + `gsap.ticker`（逐帧 JS，补 WAAPI 没有的洞）、`ease` 可传函数、`lazy:false`/`immediateRender`/`overwrite`/`inherit` 等渲染时序开关。

---

## 5. Web Animations API / CSS Animations

### 5.1 keyframe 数据模型

```js
new KeyframeEffect(target, keyframes, {
  duration, easing: 'linear', delay, endDelay, iterations, iterationStart,
  direction: 'normal', fill: 'none', composite: 'replace', iterationComposite
});
```
- 每帧特殊键：`offset`(0–1，null=等距)、`easing`（**关键帧级 easing：从本帧到下一帧**）、`composite`（`auto` 表示用 effect 上的设置）。
- `composite` 三值：`replace` / `add`（叠加，`translateX(-200px)` 与 `rotate(20deg)` 并列而不相消）/ `accumulate`（累加，`blur(2)+blur(5)=blur(7)`）。
- MDN 的对象形式原例证明**各属性可有不同 offset 密度**：`{opacity:[0,1], backgroundColor:["red","yellow","green"]}` 注释写明 `// offset: 0, 1` 与 `// offset: 0, 0.5, 1`；`easing`/`composite` 数组不够长时循环复用。→ **模型是「每属性一条关键帧位置列表 + 一个无状态 timing 输出 progress」，不是"数值函数"。**

### 5.2 规范明文：无状态（这是本框架的边界，也是它的定义）

W3C Web Animations L1 §4.1.1 原文：「the output is based solely on the input time and **is independent of previous inputs**」，并给出三条推论：Frame-rate independent / Direction-agnostic / Constant-time seeking。

**推论（本文）**：CSS/WAAPI **不能表达"值依赖于上一帧的值"**（弹簧、粒子、追踪、累积），因此它必然是某个更高层系统的**编译目标**而不是创作语言。生态正是这么长出来的：Motion 的 hybrid engine  可硬件加速的 `opacity/filter/transform` 交 WAAPI，其余退回 rAF，**自定义 easing 被自动编译成一段 `linear()` CSS 缓动**。

### 5.3 CSS 侧与时间模型

`@keyframes` 百分比（`from`=0%、`to`=100%，`0` 无单位非法）；帧内**仅 `animation-timing-function` 生效**（其余 `animation-*` 被忽略）。`animation-direction: normal|reverse|alternate|alternate-reverse`（reverse 时 easing 也反转）；`animation-fill-mode: none|forwards|backwards|both`；`animation-delay` 负值 = 立即开始但跳过周期内对应时长。
**`linear()` 已是标准**：`standard_track: true`，Chrome 113 / Firefox 112 / Safari 17.2。语义：`linear(0, 0.25, 1)` 等距；`linear(0, 0.25 75%, 1)` 非等距；`linear(0, 0.5 25% 75%, 1)` 双百分比 = 停驻段（等价 `linear(0,0.5 25%,0.5 75%,1)`）；数值可超出 0–1。
时间轴层级：`AnimationTimeline` → `DocumentTimeline` / `ScrollTimeline(source, axis)`；CSS 侧 `animation-timeline: scroll(...)` + `animation-range`（scroll-driven 目前 **not Baseline**）。

---

## 6. Lottie / Bodymovin

### 6.1 数据模型：属性二态 + 每段一段贝塞尔

```json
// 非动画
{"a": 0, "k": 256}
// 动画
{"a": 1, "k": [ {"t": 0, "s": [0], "o": {"x":[0.333],"y":[0]}, "i": {"x":[0.667],"y":[1]}}, ... ]}
```
官方定义（[properties/](https://lottiefiles.github.io/lottie-docs/properties/)）：`i`/`o` 是**立方贝塞尔的控制点**，「starting at [0,0] and ending at [1,1]，x 轴=时间、y 轴=值插值比例」；线性即 `o={x:0,y:0}, i={x:1,y:1}`，缓入缓出即 `0.333 / 0.667`。`h:1` 是阶梯（此时不需要 `i`/`o`）。旧式 `e` 字段已废弃（迁移式：`keyframes[n-1].s = keyframes[n-2].e`）。
**一条容易被忽略的官方说明**：「For multi-dimensional animated properties, these are arrays, **with one element per dimension so you can have different easing curves per dimension**」**缓动的粒度是"每个属性的每一维"**。

### 6.2 图层与复用

```json
{ "v": "5.7.1", "fr": 60, "ip": 0, "op": 60, "w": 512, "h": 512,
  "assets": [ { "id": "Star", "layers": [ { "ty": 4, "shapes": [] } ] } ],
  "layers": [ { "ty": 0, "refId": "Star", "ind": 0, "st": 0, "ip": 0, "op": 60,
                "w": 512, "h": 512, "ks": {} } ] }
```
`ty`: 0 precomp / 1 solid / 2 image / 3 null / 4 shape / 5 text / 6 audio / 13 camera / 15 data。precomp 图层**必须给 `w`/`h`，否则什么都不显示**。父级继承**只含 transform、不含 opacity**。`sr`（Time Stretch）只能等比加减速；**倒放与任意重映射必须用 `tm`（Time Remapping）**。

### 6.3 expressions：为什么需要这条逃生口，以及它跑在哪

格式层给属性留了 `x` 字段（表达式源码字符串）。AE 表达式要求**每个表达式声明并赋值 `$bm_rt`**，可访问 `time` / `value` / `thisComp` / `thisLayer` / `thisProperty` / `Property.loopOut()` / `valueAtTime()` / `smooth()` / `posterizeTime()` / `createPath()` 等。

```json
{ "k": [256, 256], "a": 0,
  "x": "var $bm_rt = [];\n $bm_rt[0] = value[0] + Math.cos(2 * Math.PI * time) * 100;\n $bm_rt[1] = value[1];" }
```

**它为什么必须存在**：因为 6.1 的数据模型只能表达"分段贝塞尔"，而 wind、粒子、追踪、跨图层联动、噪声这些是**关系**而不是**曲线**。把关系硬塞进贝塞尔数组，就是 8.4 节说的"描述越复杂越写越长"。

**它跑在哪（关键限制）**：lottie-web 是唯一真跑表达式的官方播放器，源码三条件：

```js
// 门控（默认可关，关掉即退化为纯关键帧）
if (!elem.globalData.renderConfig.runExpressions) { return noOp; }
// 真求值
var expression_function = eval('[function _expression_function(){' + val + ';scoped_bm_rt=$bm_rt}]')[0];
```
官方支持矩阵里 `Expressions` 一行在 **Android / iOS(Core Animation) / iOS(Main Thread) / Windows 四列全 ⛔，仅 Web 三渲染器 👍**（[airbnb.io/lottie/#/supported-features](https://airbnb.io/lottie/#/supported-features)）。dotLottie 是唯一反例：theme rule 带 `expression` 字段，其官方 web 内核 ThorVG 自称支持率 **75%**，但 `posterizeTime` / `footage()` / `createPath` / `thisComp.marker.*` / `activeCamera` 明确 ❌。
**结论：带表达式的 Lottie 实质是 Web-only 资产**；要跨端落地就得在 AE 里烘焙（见 E 节）。

### 6.4 表达力边界（格式层 vs 播放器层，必须分开说）

- **播放器层**（官方矩阵）：Mask 的 Intersect 仅 Android/iOS；Lighten/Darken/Difference/Feather 几乎全 ⛔；文字高级项（Text Path、Per-character 3D、Range selector 全子项、expression selector）**仅 Web** 👍，其余全 ⛔；Time Stretch / Time remap 在 Windows ⛔；Repeater 与 Trim Path 在两套 iOS 引擎上互补（CA 👍 / Main Thread ⛔）。
- **格式层**（`compat/`）：v4.1.9 颜色分量由 `[0,255]` 变 `[0,1]`；v4.4.14 前静态 text document；v4.4.18 前 shape closing 用布尔；v5.0.0 前用 `e`；v5.7.15 前 text-follow-path 属性是裸数字。
- **未找到**：3D 图层/摄像机的「格式 vs 播放器」权威分列页；`tm` 挂 `time*25` 的官方 JSON 样例。

---

## 7. Blender：F-Curve / F-Modifier / Driver

### 7.1 数据结构

```python
kp = fcurve.keyframe_points.insert(frame=10.0, value=25.0)
kp.co                  # (frame, value)
kp.handle_left_type    # FREE | ALIGNED | VECTOR | AUTO | AUTO_CLAMPED
kp.interpolation       # CONSTANT|LINEAR|BEZIER|SINE|QUAD|CUBIC|QUART|QUINT|EXPO|CIRC|BACK|BOUNCE|ELASTIC
kp.easing              # AUTO | EASE_IN | EASE_OUT | EASE_IN_OUT
fcurve.extrapolation   # CONSTANT | LINEAR（首尾关键帧之外的延拓）
fcurve.sampled_points  # 采样数据（与 keyframe_points 互斥）
```
**关键语义：插值定义在「段左端点」上**  本关键帧的 `interpolation` + `easing` 管「本帧到下一帧」。

### 7.2 压缩机制：F-Modifier 与 Driver 各压缩掉什么

| 机制 | 压缩掉什么 |
|---|---|
| `CYCLES` | 一个循环段 → N 次重复（Before/After: No Cycles / Repeat Motion / Repeat with Offset / Repeat Mirrored；Count=0 无限）。**约束：必须在列表首位，故与 SMOOTH 不兼容** |
| `GENERATOR` | 整段关键帧 → 多项式 `y=A+Bx¹+Cx²+…`（32 系数、1–100 阶、可 `use_additive`） |
| `FNGENERATOR` | 表达式族曲线（sin/cos/tan/sqrt/ln/sinc）→ 4 个参数 |
| `ENVELOPE` | 同动作不同振幅 → 上下包络 |
| `NOISE` | 手 Key 抖动 → 噪声（Blend Type: Replace[-0.5,0.5] / Add[0,1] / Subtract / Multiply） |
| `STEPPED` | 降帧采样并保持 |
| `LIMITS` / `SMOOTH` / `NULL` | 只留 Min/Max；高斯平滑；占位 |

求值顺序：**先按关键帧插值出基础值，再按 modifier 栈自顶向下逐层施加**；每层另有 `influence`(0–1)、`blend_in`/`blend_out`、`frame_start`/`frame_end` + `use_restricted_range`、`mute`。

### 7.3 Driver：跨属性函数（不是时间函数）

```python
driver.type           # AVERAGE | SUM | SCRIPTED | MIN | MAX
driver.expression     # '#frame / 20.0'、'#sin(frame)'
driver.variables[0].type   # SINGLE_PROP | TRANSFORMS | ROTATION_DIFF | LOC_DIFF | CONTEXT_PROP
driver.is_simple_expression  # 只读：能否不经完整 Python 解释器求值
```
**Driver 的结构性区别**：输入来自其它属性/变换通道，输出经一条 driver 曲线落到目标属性  于是「姿态 → 形态键」这类 rig 逻辑可以**直接建成函数关系，不必逐帧 Key**。
**逃生口代价（官方原话的要点）**：表达式"足够简单"时走原生求值（`is_simple_expression`），否则**回落完整 Python 解释器：更慢，且文件作者未知时存在安全风险**。

### 7.4 逃生口粒度

逐属性（driver 是一条函数关系）→ 逐通道（TRANSFORMS 变量可读世界/变换/局部空间的九个通道）→ 逐场景（`CONTEXT_PROP` 可读活动摄像机这类外层状态）。`use_fallback_value` 是为"链接到别的场景后属性不存在"准备的**这是跨文件复用时的真实工程缺口，被显式建模了**。

---

## 8. Rive / Spine：骨骼与状态机

### 8.1 Rive：状态机 + 混合

**State Machine = Graph + States + Transitions + Layers**。**一个 layer 同时只播一个 state**；并行要加 layer；**layer 列表靠下的优先**。
转场 = Path / Conditions / Properties / Actions。条件三段式：**Source value**（属性/事件/内建宽高等）→ **Operator**（`equals`、`does not equal`、`>`、`>=`、`<`、`<=`）→ **Comparison value**（常量或绑定到另一属性）。**同一转场内多条件 = AND；同一对状态间建多条转场 = OR**。
转场属性：`duration`（默认 0，立即切换）、`exitTime`（时间值或百分比）、`interpolationType`（默认 linear）、`randomWeight`，另有 Pause Source When Exiting、Allow Exit During Transition。

**1D 混合的权重算法（源码原文，`blend_state_1d_instance.cpp`）**：
```cpp
mix     = (value - fromValue) / (toValue - fromValue);
mixFrom = 1.0f - mix;
for (auto& animation : m_AnimationInstances) {
    if (m_To && animation.blendAnimation()->value() == toValue)     animation.mix(mix);
    else if (m_From && animation.blendAnimation()->value() == fromValue) animation.mix(mixFrom);
    else animation.mix(0.0f);
}
```
**⚠️ 与官方措辞冲突（如实标注）**：states 页称 1D 混合 "not linear, but is additive"，源码实测是**相邻两动画线性加权**（权重和 = 1）。
**⚠️ API 变更**：官方文档现已把 **Inputs 整节标为 DEPRECATED**，推荐改用 Data Binding（View Models）。

### 8.2 少量数据驱动大量视觉

1. **骨骼 + 权重网格**：矢量路径的**顶点与贝塞尔手柄**可绑定一至多根 bone 并调权重；位图加 mesh 后把**网格顶点**绑多根 bone，带权重即可平滑弯曲拉伸。网格由 contour 三角化（默认 4 顶点/2 三角形），顶点可 key 也可由 bone 驱动。三者可在同一 rig 混用。
2. **状态机 + 转场图**：少量 input 属性 + 条件驱动整段动画。运行时**只能间接控制**（官方明说限制对 state 的直接读写，靠属性条件驱动），以防设计侧改动变成破坏性变更。
3. **blend 而非逐组合手画**：1D 用一个 number 在相邻动画间插值；Direct/Additive 用多个 number 直接给权重  **组合数不必等于动画数**。

### 8.3 Spine：时间轴数据模型与 curve 压缩

```json
"animations": { "idle": { "bones": { "torso": {
  "rotate":    [ {"time": 0, "value": 0, "curve": [0.19, 0, 0.56, 2]},
                 {"time": 0.75, "value": 2} ],
  "translate": [ {"time": 0, "x": 0, "y": 0, "curve": [0.19,0,0.56,0, 0.19,0,0.56,3]},
                 {"time": 0.75, "x": 0, "y": 3} ] } } } }
```
官方对 `curve` 有两类写法，**必须分清**：
- 骨骼轴：`[cx1, cy1, cx2, cy2]`，**X 轴单位=帧、Y 轴单位=值（绝对值）**；省略=线性，字符串 `"stepped"`=阶梯。
- 槽 color/twoColor：`[cx1, c2, c3, c4]` 是 **0–1 归一化**（X = 两帧之间的时间百分比，Y = 值差百分比），缺省 `c2=0, c3=1, c4=1`。
- ⛔「translate/scale/shear 需 8 元素」**官方页无明文**，只见于第三方 spec。未找到官方确认。

**压缩发生在运行时而非 JSON**：`CurveTimeline` 在**加载期**把 `(time1,value1,cx1,cy1,cx2,cy2,time2,value2)` 展开成 **18 个采样点**存进 `curves[]`（`BEZIER_SIZE = 18`），每个关键帧只留 **1 字节类型**：`0=LINEAR`、`1=STEPPED`、`2+i=BEZIER(第 i 条)`。求值时先线性扫 `frames` 定位段，再在 18 点上线性查值。
**这是一个极妙的折中：把「贝塞尔求值」的代价从运行期搬到了加载期，同时保留 JSON 的紧凑。**（见 E 节「局部降级」）

### 8.4 运行时混合

`AnimationState.tracks[]` 下标即轨道号；`apply(skeleton)` 按**轨道 0 → n 依次施加**（低轨先、高轨后覆盖）；未 Key 的属性不被覆盖。
```ts
applyMixingFrom (to) {
  const mix = to.mix();
  const a = from.alpha * fromMix, keep = 1 - mix * to.alpha;
  const alphaMix  = a * (1 - mix);
  const alphaHold = keep > 0 ? alphaMix / keep : a;
}
```
`TrackEntry.alpha`（官方注释：「Values < 1 mix this animation with the skeleton's current pose … **Alpha should be 1 on track 0**」）、`mixDuration`/`mixTime`、`timeScale`（**不支持负值，倒放用 `reverse`**）。从 setup pose mix in/out 靠**空动画**：`setEmptyAnimation(track, 0)` + `addAnimation` + `entry.mixDuration = 1.5`。

---

## 9. AE 表达式：程序 vs 关键帧两条路

### 9.1 两条路是**叠加**关系，不是替代关系

官方定义：「All properties in After Effects that can be animated have a **pre-expression value** and a **post-expression value**.」表达式里的 `value` 就是**关键帧那条路的当前值**；UI 上预表达式值蓝、后表达式值红。所以 `value+90` 会在既有动画之上加 90 度  **两条路同时生效**。

### 9.2 核心 API 与真实片段

```js
// 抖动：freq 次/秒；amp 以属性单位计；octaves 默认 1；amp_mult 默认 0.5；t 默认 time
thisLayer.position.wiggle(freq, amp, octaves = 1, amp_mult = 0.5, t = time);
thisLayer.position.temporalWiggle(5, 20, 3, 0.5, time);   // 只抖时间轴采样点

// 循环：cycle | pingpong | offset | continue
thisLayer.position.loopOut([type = "cycle"][, numKeyframes = 0]);
thisLayer.position.loopIn(...);

// 反向查询与随机
thisLayer.position.valueAtTime(t);      // t 为秒
seedRandom(1, true); valueAtTime(random(4) | 0);

// 跨图层
var other_position = thisComp("layer_name").transform.position;
var $bm_rt = [other_position[0], value[1]];
```
两个真实的坑：① `loopOut` 的返回值**已含当前值**，叠加时要减一次 `value`；Source Text、path shape 属性、Levels 的 Histogram **不支持循环**。② `seedRandom(offset, timeless)` 的 offset **同时决定 wiggle 的初值**。

### 9.3 粒度与代价

粒度 = **逐属性、逐帧**（官方：「evaluate to a single value for a single layer property at a specific point in time」）。
**跨图层与循环依赖**：⛔ **Adobe 官方没有对求值顺序/循环依赖的说明页（未找到）**。可引的实现层硬约束来自 lottie-docs：「Since property values are initialized to their non-expression value, **you can't access updated value of the property you are changing from the expression**」只能把图层对象当可变状态（`thisLayer.my_value += dt * speed`），且 `time == 0` 不是可靠初始化判据（循环会回到 0）。

### 9.4 `Convert Expression to Keyframes` 的做法与损失

官方原文只有一句：「**Analyzes the current expression and creates keyframes to represent the property values it describes.**」
可确证的推论：① **参数化信息丢失**`wiggle(5,20)` 退化为离散点，改频率/振幅必须重打；② `seedRandom(timeless=false)` 的随机序列被冻结；③ 体积随帧数线性膨胀（每个采样点一组 `s`/`i`/`o`）。
⛔ **未找到**：官方对"转换后原表达式被自动删除"、"是否严格逐帧/能否自定义采样率/缓动近似误差"的任何表述。

---

## A. 完备性：哪个抽象层不可再省？

**本文推断。** 先给结论，再给判据。

把九个框架的"能表达什么"还原成三层，砍到不能再砍只剩：

```
① 值层：属性轨道 = Time → Value        （FRP 意义上的 Behavior；关键帧只是它的分段多项式表示）
② 组合层：并发 / 串联 / 延迟 / 重复 / 错落（关系型时间，而非绝对时间）
③ 时间基层：谁拥有时间、时间如何继承与缩放（嵌套时间轴 / Sequence / 时间缩放 / 混合权重）
```

**判据一：关键帧不是"另一条路"，是 ① 的一种表示。**
- WAAPI/CSS 的 keyframe 数组 = 分段函数的一种**序列化**；Lottie 的 `{"a":1,"k":[...]}` 同上；Blender F-Curve 同上。
- AE 的「Convert Expression to Keyframes」之所以能存在，正是因为**这两者同构**：程序只是同一函数的一种更紧凑的写法。**这解释了整条降级编译链（E 节）为什么可行。**
- 反过来：CSS/WAAPI 被规范死定义为 **stateless**（「the output is based solely on the input time and is independent of previous inputs」），所以它**表达不了"值依赖上一帧"**。这类效果只能由 ① 里允许"状态"的实现承担（AE `thisLayer.x += dt`、Manim `PhaseFlow` 的 `last_alpha`、Rive 状态机）。

**判据二：② 是不能省的，而且它就是"压缩性"的所在。**
- 若只有 ①，任何效果都能表达（你可以写 `f(t)` 返回任何东西）但那时**压缩性归零**：复杂度全部落在函数体里，不可分析、不可复用、不可交错检查。
- ② 的每一种形式，都在**显式地描述"关系"而不是"结果"**：`lag_ratio`（错落）、`"<"`/`">"`（相对定位）、`Sequence from`（嵌套偏移）、`mixDuration`（过渡期的混合）、`AnimationGroup`（并发+汇合）。**这些关系无法由 ① 的组合自然涌现，只能被声明。**
- 反证（本项目的实证对照）：**ASS 的 `\t` 是这个谱系的最简端点**  只有幂函数缓动族（`y = x^accel`）、粒度是「每条标签×每个时间窗」、没有 keyframe 数组、没有组合子、没有时间基继承（只有行起点）。本项目 `doc/KFX-SEMANTIC-MODEL.md` 已记下后果：「想做过冲就拼两段 `\t`……不承诺 spring / 贝塞尔  那是**格式天花板**，靠拼接近似」。**一个只有 ① 没有 ② 的格式，复杂效果的笔墨量是超线性的。**

**判据三：③ 决定了"复用"能否发生。**
- 没有时间基继承，`Series`/nested timeline/precomp 都不成立，复用只能靠复制。

**最终答案**：不可再省的是 **`（值函数）+（组合子）+（时间基继承）`** 这个三元组。
- ① 提供**完备性**（因为它允许任意函数）；
- ② 提供**压缩性**（因为它把"错落/重叠/并发/重复"从函数体里提出来变成算子）；
- ③ 提供**复用性**（因为它让一段动画能被放进另一个时间坐标里）。
- 再加上一条横切的**合成律**：加法/累积（SMIL `accumulate="sum"`、WAAPI `composite: add|accumulate`）、混合（Spine `alpha`/`mix`、Rive blend）、覆盖（Blender modifier 栈、`overwrite`）。缺少合成律时，"多个动画作用于同一属性"就退化成"谁最后写谁赢"。

**一个对本题特别重要的推论**：题面问"任意 keyframe 数组 + easing 是否就完备"。**不完备**它缺的是"错落"这类关系型效果（除非把 N 条轨道手工展开，那正是"越写越长"）。`lag_ratio` / `stagger` 的存在本身，就是这条不完备性的存在性证明：**如果 keyframe 数组完备，这两个机制就没有理由出现。**

---

## B. 压缩性：哪些机制专为"更少字描述更复杂"而存在

| 机制 | 压缩掉什么重复 | 证据形态 |
|---|---|---|
| **GSAP position parameter** `"<"` / `">"` / `"<+=25%"` | 压缩"上一个动画的起止时刻"这个**变量**（免去手算/命名） | `_parsePosition` 源码先 `indexOf("=")` 再决定基准 |
| **GSAP stagger** `each` / `amount` / `from` / `grid` | 压缩"N 个错落启动时间" → 1 个标量（或 1 个对象） | `stagger: {each:0.1, from:'center', grid:'auto'}` |
| **Manim `lag_ratio`** | 同上，且**递归生效**（嵌套 submobject 也错落） | `full_length = (n-1)*lag_ratio + 1; rate_func(alpha*full_length - index*lag_ratio)` |
| **`loop` / `CYCLES` / `repeatCount` / `iterations`** | 压缩"重复"（含 repeatDur 小数次、`accumulate="sum"` 累积） | `<animateMotion path="..." dur="5s" accumulate="sum" repeatCount="4"/>` |
| **precomp / nested timeline / `<Sequence>`** | 压缩"复用的编排"（一段动画放 N 处、可独立缩放/倒放） | Lottie `{ty:0, refId}`；GSAP `tl.add(other, position)` |
| **程序化替代关键帧**（`wiggle`/`loopOut`/表达式/generator） | 压缩"手写每个值" | `wiggle(5,20,3)` 描述一族噪声 |
| **SMIL `accumulate="sum"`** | 压缩"4 段弧线拼成 1 段弹跳"官方原话：「The **same animation could be described as a complete path of 4 arcs, but in the general case the path description can get quite large and cumbersome to edit.**」 | `path="m 0 0 c ..." accumulate="sum" repeatCount="4"` |
| **CSS/WAAPI `linear()`** | 压缩"任意缓动" → 一个标量列表（程序算出的缓动被编译进来） | `linear(0, 0.25 75%, 1)` |
| **`composite: add / accumulate`** | 压缩"手算叠加后的值" | `blur(2) + blur(5) = blur(7)` |
| **`sr` / `tm` / `timeScale` / `playbackRate`** | 压缩"为变速/倒放重画一遍" | Lottie `tm` 才能倒放 |
| **骨骼 + 权重网格** | 压缩"每个姿态手画" → 少量 bone 参数 × 权重 | 顶点/手柄/网格顶点绑 bone |
| **blend state / 混合树** | 压缩"为每个组合手画"（组合数不必等于动画数） | `mix = (v-from)/(to-from)`；Direct 权重 |
| **`mixDuration`** | 压缩"写一段过渡动画" | Spine `setEmptyAnimation(track,0)` + `mixDuration=1.5` |
| **Driver（Blender）** | 压缩"逐帧 Key 一条函数关系" | `#frame / 20.0` |
| **F-Modifier `GENERATOR`** | 压缩整段关键帧 → 多项式 | 32 系数 / 1–100 阶 |
| **`ease` 分布启动时刻（GSAP stagger）** | 压缩"非线性错落"的手算 | `ease:'power2.inOut'` |
| **`SignalGenerator.to(...)`（Motion Canvas）** | 压缩"N 段动画 = N 个 `yield*`" → 一行链式 | `yield* radius(4,2).to(3,2)` |

**可归纳的三条压缩律**：
1. **把标量换成关系**（绝对时刻 → `<`/`>`/`lag_ratio`）压缩率最高，因为它消除的是**变量**而非重复项。
2. **把重复换成算子**（loop/repeat/modifier）压缩率随重复次数线性增长。
3. **把值换成函数**（表达式/generator/driver）压缩率取决于函数描述的那族值的规模；**代价是失去可分析性**（C 节）。

---

## C. 逃生口：粒度与代价

### C.1 四档粒度

| 粒度 | 代表机制 | 说明 |
|---|---|---|
| **逐属性** | AE 单属性表达式；Motion Canvas signal 第 3/4 参；GSAP `ease` 传函数；Lottie 属性级 `x` | 只接管一个属性的"值从哪来" |
| **逐帧** | Manim `add_updater(func)`（可接 `dt`）；Motion Canvas `tween(seconds, (v,t)=>...)`；GSAP `onUpdate` + ticker | 接管"这一帧算什么" |
| **逐对象** | Manim `Mobject.add_updater`；Three.js 式逐对象回调；Spine/Blender 的逐通道 | 对象内部可有**跨属性**状态 |
| **逐线程 / 逐程序** | Motion Canvas generator + `spawn`/`threads`/`yield promise`；Remotion **整个组件就是一个 `f(frame)`**；Blender Python driver | 逃生口大到"你写的就是模型" |

**Remotion 的逃生口粒度是九者中最粗的**：它不给动画留洞，而是把**整个组件**定义为帧的纯函数。这既是它可预测性的来源，也是它表达力的边界凡是不能写成 `f(frame)` 的（依赖历史的、依赖真实时钟的），都要靠 `delayRender` 之类的屏障或干脆放弃并行。

### C.2 代价的五个真实形态（每条有证据）

1. **不可序列化**（→ 不能存盘、不能跨进程、不能上编辑器）
   Motion Canvas：signal 的当前值本就可以是闭包（`SignalValue<T> = T | (() => T)`），`CompoundSignalContext.raw()` 只能原样返回闭包。
2. **跨平台不可移植**
   Lottie 表达式：`Expressions` 在 Android / iOS(CA) / iOS(MT) / Windows **四列全 ⛔**，仅 Web 👍；即便 ThorVG 也只到 75%（且 `posterizeTime` ❌）。**含表达式的 Lottie 实质是 Web-only 资产。**
3. **fps 依赖**
   AE bake、Blender `nla.bake(step)`、Motion Canvas `tween` 的 `while (endTime > thread.fixed)`  精度上限 = 采样帧率。
   **反例（两条路线并存）**：Motion Canvas 的 `spring` 用固定 120Hz 积分换取与 fps 无关。
4. **求值顺序 / 循环依赖**
   Motion Canvas：依赖收集重入即抛 `'A circular dependency occurred between signals.'`。
   Lottie/AE：「you can't access updated value of the property you are changing from the expression」→ 只能把图层对象当可变状态。
   Blender：`use_fallback_value` 显式建模"跳转场景后变量不存在"。
   **Adobe 官方对求值顺序无说明页（未找到）**这类语义在工业系统里常常是"实现即规范"。
5. **性能**
   Motion Canvas：脏标记一 raise 就重跑整棵依赖闭包；Blender：Python driver 比 native 慢（官方点名，并提共享文件的安全风险）；Remotion `spring`：无状态但 O(frame)（靠 `calculationCache` 兜）。
6. **（附加）安全面**：lottie-web 的表达式走 `eval(...)`，源码里留有被注释掉的"potential network calls"净化  **"动画文件即代码"这个攻击面是被认知过的**。

---

## D. "效果"如何被复用：参数化效果函数 vs 可组合算子

| 框架 | 机制 | 形态 |
|---|---|---|
| **Motion Canvas** | **generator function** | `function* myEffect(node, t) { ... }`，调用处 `yield* myEffect(rect, 2)`；`useDuration('event')` 把时长外置到时间轴 |
| **Manim** | **`Animation` 子类**（类名即效果名，`__init__` 即参数） | `class MyEffect(Animation)`；`override_animate` 把 `mob.my_effect(...)` 变成 `.animate` 式调用 |
| **GSAP** | **`registerEffect`**（最接近"参数化效果函数"的教科书形态） | `gsap.registerEffect({name, effect:(targets,config)=>Tween\|Timeline, defaults, extendTimeline})` |
| **GSAP** | 暂停的 timeline 当函数 | `const fx = gsap.timeline({paused:true}); ...; fx.play()` |
| **Lottie** | **precomp 资产** | `{id, layers[]}` + `{ty:0, refId}`；`sr` 变速、`tm` 倒放 |
| **Remotion** | **React 组件 + props** | 复用的前提是 **props 必须可序列化**（否则并行渲染拿不到） |
| **WAAPI/CSS** | `@keyframes` 名 + `animation` 简写 | **没有参数**参数化必须由上层（Motion/GSAP）在生成 keyframes 时注入 |
| **Blender** | Action 数据块 + NLA + Driver | 同一 Action 供多个对象；driver 表达式可复制粘贴 |
| **Rive** | **Components**（可多次实例化的可复用 artboard）/ nested artboard | 官方推荐的复用单元 |
| **Spine** | 同名 timeline 复用 + `skins` | 同一套动画，换皮即换外观 |

**一条结构性观察**：能"参数化"的前提是**效果本身是一个函数**（有入参、有返回值/可被 yield）。因此凡是把效果做成"数据片段"的系统（Lottie precomp、CSS @keyframes），**参数化能力必然外移到生成器**这正是 Lottie 生态把"程序"塞进 `x` 表达式、CSS 生态把程序放进 JS 生成 keyframes 的原因。

---

## E. 程序 → 关键帧的降级编译（lowering）

### E.1 逐条清单

| 机制 | 做法 | 粒度/采样率 | 损失 | 来源 |
|---|---|---|---|---|
| **AE「Convert Expression to Keyframes」** | 对选中属性求值后写关键帧 | 官方只说 "creates keyframes to represent the property values it describes"；逐帧粒度出自社区实测 | 丢参数化、随机序列被冻结、体积膨胀 | [Adobe 帮助原文](https://helpx.adobe.com/after-effects/desktop/animate-in-after-effects/animation-keyframes/setting-selecting-deleting-keyframes.html) |
| **Blender `nla.bake`** | `bake(frame_start, frame_end, step, visual_keying, clear_constraints, clean_curves, bake_types, ...)` | **每 `step` 帧**（默认 1=逐帧，可跳步） | `visual_keying` 把**约束结果**烘进去；`clear_constraints` 销毁参数化；曲线变密集 | [bpy.ops.nla](https://docs.blender.org/api/current/bpy.ops.nla.html) |
| **lottie-web 表达式** | **默认不烘焙**：`x` 字段存**原样字符串**，运行时 `eval` 逐帧求值 | 逐帧、逐属性 | 保留=零损失但**跨播放器不可移植**；烘焙=与上同 | [Expressions wiki](https://github.com/airbnb/lottie-web/wiki/Expressions) · [ExpressionManager.js](https://cdn.jsdelivr.net/npm/lottie-web@5.12.2/player/js/utils/expressions/ExpressionManager.js) |
| **bodymovin 导出侧** | `Convert expressions to keyframes`（全局）或注释 `// lottie:bake`（单条）；**均不改原工程** | 同上 | 同上 | [DeepWiki: Expressions and Effects](https://deepwiki.com/bodymovin/bodymovin-extension/3.3-expressions-and-effects) |
| **glTF 导出** | glTF 只有 `STEP` / `LINEAR` / `CUBICSPLINE`，规范内**无约束/IK/驱动/物理**概念 → 导出必经采样 | 采样式 | 不可回推原始约束 | [glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html) |
| **glTF-Transform `resample`** | **反向**：无损去重 | 键级 | 无损（示例 14 键 → 6 键） | [resample](https://gltf-transform.dev/modules/functions/functions/resample) 明写重复键源于 "animation **baked** by the authoring software to apply IK constraints" |
| **USD `UsdSkelBakeSkinning`** | 把蒙皮/blendShape 结果烘到点/法线/xform | 逐帧 | 权重与绑定关系被结果取代 | [bakeSkinning.h](https://openusd.org/dev/api/bake_skinning_8h_source.html) |
| **Motion（hybrid engine）** | 程序 API → 运行时按需编译；**自定义 easing 自动生成 `linear()` CSS 缓动** | 运行时 | 交合成器的动画无法逐帧读中间值 | [motion.dev](https://motion.dev/docs/improvements-to-the-web-animations-api-dx) |
| **SMIL → CSS（`smil2css`）** | 转换工具（第三方，0.2.0 才支持 `begin` syncbase） | 结构级 | `begin="a.end+1s"` 同步基、`additive`/`accumulate` 在 CSS **无对应物** → 语义丢失 | [webframes/smil2css](https://github.com/webframes/smil2css) |
| **Spine `CurveTimeline`** | 加载期把贝塞尔段展开成 18 个采样点 | **段级**（不是整条动画） | 精度固定在 18 点；换来运行期零求值成本 | [Animation.ts](https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/master/spine-ts/spine-core/src/Animation.ts) |

### E.2 三类模式

- **A 每帧采样（最重）**：AE bake / Blender `nla.bake` / glTF 导出 / USD bake。源程序被求值结果**取代**，精度上限 = fps，不可回推。
- **B 按需重建（源程序仍是一等资产）**：lottie-web 表达式（默认保留字符串、运行时求值，烘焙是**可选**开关）；Motion hybrid engine（自定义 easing 编译成 `linear()`，必要时退回 rAF）；Theatre.js（JSON state 运行时求值）。**关键点帧是缓存、可抛**。
- **C 运行时不降级**：Rive `.riv` + `Artboard::advance`（二进制资产 + 状态机求解，从不生成关键帧表）；Spine 的 18 点展开介于 C 与 A 之间  **本文称之为「局部降级」：只把一段贝塞尔编译成采样点，其余结构（分轨、混合、皮肤、事件）完全保留。**

### E.3 精度损失的具体形态

1. **丢参数化**：`wiggle(5,20)` 变成离散点后，改一个参数无法全局重算（AE bake、Blender `clear_constraints`、蒙皮烘焙）。
2. **fps 依赖**：所有逐帧采样产物的精度上限 = 采样帧率；换帧率或变速播放时中间值不可恢复。
3. **曲线密度爆炸**：N 帧 → N 个关键帧（这正是 `resample` / `clean_curves` 存在的理由）。
4. **跨平台丢失**：不烘焙的表达式在无表达式引擎的播放器上直接失效 → bodymovin 生态把烘焙当兼容手段。
5. **语义不可表达**：SMIL 的 `begin syncbase` / `additive` / `accumulate` 与 CSS keyframes 之间**没有对应物**，转换即降级；glTF 的三种插值无法表达弹簧/物理/条件逻辑。
6. **不可回推**：bake 之后原程序不可从关键帧反解（切线拟合只是近似）。

### E.4 反方向：关键帧 → 程序 的压缩

- **无损去冗**：`glTF-Transform resample`（"losslessly deduplicating keyframes"）、Blender `bake(clean_curves=True)`（"After baking curves, remove redundant keys"）。
- **有损简化**：Blender F-Curve **Decimate** 修改器（按 ratio 删键）、Ramer–Douglas–Peucker（容差 ε 内保形）。
- **不是压缩而是反向程序化**：AE 的 `smooth()` / `loopOut()` 是**运行时表达式**，用程序**替代**关键帧，不是压缩关键帧。
- ⛔ **未找到**：AE 名为 "Simplify" 的官方关键帧助手；名为 `lottie-optimizer` 的真实工具。

### E.5 对本题的结论

**「程序 → 关键帧」的降级之所以在九个框架里都存在，正是因为两者同构（A 节判据一）。** 而工程上的最优解已经被 Spine 演示了：**降级粒度不必是"整条动画"，可以是"一段曲线"**把最贵的那部分（贝塞尔求值）在加载期编译成采样表，把最省的那部分（结构、混合、事件）保留为数据。这是"完备性 × 压缩性"在实现层的落点。

---

## 附：一处与本题直接相关的本项目实证

`doc/KFX-SEMANTIC-MODEL.md` 记录了 ASS 格式天花板的一条实测后果：`\t(...,accel)` 的数学形式是 `y = x^accel`（**只有幂函数族**），因此「想做过冲就拼两段 `\t`；不承诺 spring / 贝塞尔」。`doc/ASS-Tag-Coverage.md` 进一步给出 `\t` 内**只允许有 `pwr` 分支的标签**（安全集限定为 `\bord \xbord \ybord \shad \xshad \yshad \fax \fay \blur \be \frx \fry \frz \fscx \fscy \fsp \fs \1c..\4c \1a..\4a \alpha \clip(矩形) \iclip(矩形)`，其余放进去等于没写），并实测拿到 **12 条静默失效路径**（其中 4 条是「标签前缀互相劫持」；例如漏写 accel 的逗号会让整条 `\t` 退化成全程恒定终值  `cnt==1` 时该参被当作 `accel`、值为 0、`y=x^0` 恒为 1）。
**这就是"① 完备、② 缺失、③ 缺失"的系统长什么样**：能用，但复杂效果的描述长度超线性增长，且失败是静默的。

---

## 来源清单（按框架）

**Motion Canvas**：[SignalContext.ts](https://github.com/motion-canvas/motion-canvas/blob/main/packages/core/src/signals/SignalContext.ts) · [CompoundSignalContext.ts](https://github.com/motion-canvas/motion-canvas/blob/main/packages/core/src/signals/CompoundSignalContext.ts) · [threads.ts](https://raw.githubusercontent.com/motion-canvas/motion-canvas/main/packages/core/src/threading/threads.ts) · [signals 文档](https://motioncanvas.io/docs/signals/) · [flow 文档](https://motioncanvas.io/docs/flow) · 本机解包 `@motion-canvas/core@3.17.2`（jsDelivr）

**Remotion**：[use-current-frame.ts](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/core/src/use-current-frame.ts) · [Sequence.tsx](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/core/src/Sequence.tsx) · [interpolate.ts](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/core/src/interpolate.ts) · [spring/index.ts](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/core/src/spring/index.ts) · [spring-utils.ts](https://raw.githubusercontent.com/remotion-dev/remotion/main/packages/core/src/spring/spring-utils.ts) · [flickering](https://www.remotion.dev/docs/flickering) · [spring](https://www.remotion.dev/docs/spring) · [random](https://www.remotion.dev/docs/random) · [delay-render](https://www.remotion.dev/docs/delay-render) · `--concurrency` 页 404（未找到）

**Manim**：[animation.py](https://raw.githubusercontent.com/ManimCommunity/manim/main/manim/animation/animation.py) · [composition.py](https://raw.githubusercontent.com/ManimCommunity/manim/main/manim/animation/composition.py) · [mobject.py](https://raw.githubusercontent.com/ManimCommunity/manim/main/manim/mobject/mobject.py) · [scene.py](https://raw.githubusercontent.com/ManimCommunity/manim/main/manim/scene/scene.py) · [rate_functions.py](https://raw.githubusercontent.com/ManimCommunity/manim/main/manim/utils/rate_functions.py) · [updaters/](https://raw.githubusercontent.com/ManimCommunity/manim/main/manim/animation/updaters/mobject_update_utils.py)

**GSAP**：[position parameter](https://gsap.com/resources/position-parameter/) · [Staggers](https://gsap.com/resources/getting-started/Staggers/) · [registerEffect](https://gsap.com/docs/v3/GSAP/gsap.registerEffect()/) · [gsap.to()](https://gsap.com/docs/v3/GSAP/gsap.to()/) · [gsap-core.js 源码](https://raw.githubusercontent.com/greensock/GSAP/master/src/gsap-core.js)

**WAAPI / CSS**：[KeyframeEffect()](https://developer.mozilla.org/en-US/docs/Web/API/KeyframeEffect/KeyframeEffect) · [Keyframe Formats](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API/Keyframe_Formats) · [web-animations-1 §4.1.1 Stateless](https://drafts.csswg.org/web-animations-1/#keyframe-effects) · [css-animations-1](https://drafts.csswg.org/css-animations-1/#keyframes) · [linear()](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/easing-function/linear) · [ScrollTimeline](https://developer.mozilla.org/en-US/docs/Web/API/ScrollTimeline) · [Motion hybrid engine](https://motion.dev/docs/improvements-to-the-web-animations-api-dx)

**Lottie / AE**：[properties/](https://lottiefiles.github.io/lottie-docs/properties/) · [layers/](https://lottiefiles.github.io/lottie-docs/layers/) · [expressions/](https://lottiefiles.github.io/lottie-docs/expressions/) · [compat/](https://lottiefiles.github.io/lottie-docs/compat/) · [precomps](https://lottiefiles.github.io/lottie-docs/breakdown/precomps/) · [supported-features](https://airbnb.io/lottie/#/supported-features) · [ExpressionManager.js](https://cdn.jsdelivr.net/npm/lottie-web@5.12.2/player/js/utils/expressions/ExpressionManager.js) · [ThorVG 支持率](https://github.com/thorvg/thorvg/wiki/Lottie-Support) · [Expression basics](https://helpx.adobe.com/after-effects/desktop/work-with-expressions/expression-basics/expression-basics.html) · [Expression language reference](https://helpx.adobe.com/after-effects/desktop/work-with-expressions/expression-language-reference/expression-language-reference.html) · [Property 对象（wiggle/loopOut）](https://ae-expressions.docsforadobe.dev/objects/property/) · [Keyframe Assistant 原文](https://helpx.adobe.com/after-effects/desktop/animate-in-after-effects/animation-keyframes/setting-selecting-deleting-keyframes.html)

**Blender**：[FCurve](https://docs.blender.org/api/current/bpy.types.FCurve.html) · [Keyframe](https://docs.blender.org/api/current/bpy.types.Keyframe.html) · [FModifier](https://docs.blender.org/api/current/bpy.types.FModifier.html) · [Driver](https://docs.blender.org/api/current/bpy.types.Driver.html) · [Drivers Panel](https://docs.blender.org/manual/en/latest/animation/drivers/drivers_panel.html) · [F-Curve Modifiers](https://docs.blender.org/manual/en/latest/editors/graph_editor/fcurves/modifiers.html) · [bpy.ops.nla](https://docs.blender.org/api/current/bpy.ops.nla.html) · [rna_fcurve.cc](https://raw.githubusercontent.com/blender/blender/main/source/blender/makesrna/intern/rna_fcurve.cc)

**Rive**：[state-machine](https://rive.app/docs/editor/state-machine/state-machine.md) · [transitions](https://rive.app/docs/editor/state-machine/transitions.md) · [states](https://rive.app/docs/editor/state-machine/states.md) · [layers](https://rive.app/docs/editor/state-machine/layers.md) · [bones](https://rive.app/docs/editor/manipulating-shapes/bones.md) · [inputs（已废弃）](https://rive.app/docs/editor/state-machine/inputs.md) · [blend_state_1d_instance.cpp](https://raw.githubusercontent.com/rive-app/rive-runtime/main/src/animation/blend_state_1d_instance.cpp) · [loop.hpp](https://raw.githubusercontent.com/rive-app/rive-runtime/main/include/rive/animation/loop.hpp) · [state_transition_base.hpp](https://raw.githubusercontent.com/rive-app/rive-runtime/main/include/rive/generated/animation/state_transition_base.hpp)

**Spine**：[spine-json-format](https://en.esotericsoftware.com/spine-json-format) · [spine-applying-animations](https://esotericsoftware.com/spine-applying-animations) · [Animation.ts](https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/master/spine-ts/spine-core/src/Animation.ts) · [AnimationState.ts](https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/master/spine-ts/spine-core/src/AnimationState.ts)。注：`spine-json-skeleton` 与 `spine-ts/.../TrackEntry.ts`、`CurveTimeline.ts` **实测 404**。

**SMIL / glTF**：[SMIL 3.0 Animation](https://www.w3.org/TR/SMIL/smil-animation.html) · [glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html) · [glTF-Transform resample](https://gltf-transform.dev/modules/functions/functions/resample) · [UsdSkelBakeSkinning](https://openusd.org/dev/api/bake_skinning_8h_source.html) · [smil2css](https://github.com/webframes/smil2css)

**本项目**：[doc/KFX-SEMANTIC-MODEL.md](doc/KFX-SEMANTIC-MODEL.md) · [doc/ASS-Tag-Coverage.md](doc/ASS-Tag-Coverage.md) · [doc/KFX-RULES.md](doc/KFX-RULES.md)

---

## 未找到（明确标注，未编造）

- Motion Canvas：`Signal` 类、`signal()` 常量包装、`toSignal` / `toSignalAsync` / `toCompletion` / `duration()`、`smoothStep`、`threading/Generators`  全部 0 命中。
- Remotion：`remotion.dev/docs/concurrency` → 404。
- GSAP：`gsap.utils.shuffle` 独立文档页 → 404。
- Lottie：`tm` 挂 `time*25` 的官方 JSON 样例；3D 图层/摄像机的「格式 vs 播放器」权威分列页。
- AE：关于表达式求值顺序与循环依赖的官方说明页；`Convert Expression to Keyframes` 的采样率与精度损失官方说明；新旧表达式引擎切换开关官方原文；名为 "Simplify" 的关键帧助手（疑不存在）。
- Rive：官方 `runtimes/web/overview` 页（本轮 404）；2D Direct Blend 的源码级权重说明。
- Spine：「translate/scale/shear 的 curve 需 8 元素」官方明文（仅第三方 spec）。
- 其他：Flash/Animate → Lottie 的一手导出工具与文档；名为 `lottie-optimizer` 的工具。
