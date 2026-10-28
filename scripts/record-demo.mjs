/**
 * 演示录制脚本：用 CDP 驱动无头 Edge 跑一轮真实交互，按真实耗时抓帧。
 *
 * 之所以不用录屏软件：这台机器没有 ffmpeg，逐帧截图 + 按真实时间戳合成 GIF
 * 反而更可控（能精确停在被讲解的那一屏），而且抓的是真实页面、真实后端响应。
 *
 * 用法：
 *   node scripts/record-demo.mjs [输入文本]
 * 输出：
 *   <DEMO_FRAMES_DIR>/frame_XX.png  + timeline.json（每帧相对起始的毫秒数）
 */
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const EDGE_CANDIDATES = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Google/Chrome/Application/chrome.exe',
];
const PORT = Number(process.env.DEMO_CDP_PORT || 9333);
const PAGE_URL = process.env.DEMO_URL || 'http://localhost:5173';
const OUT_DIR = process.env.DEMO_FRAMES_DIR || path.join(tmpdir(), 'demo_frames');
const PROMPT =
  process.argv[2] ||
  '我是零基础，每天能学2小时，想用视频学 Python 编程，希望三个月内能做出一个小项目';

const exec = (file, args) =>
  new Promise((resolve, reject) => {
    const child = spawn(file, args, { stdio: 'ignore' });
    child.on('error', reject);
    child.on('exit', (code) => resolve(code));
  });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** 极简 CDP 客户端：Node 22 自带 WebSocket，不需要额外依赖 */
class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.seq = 0;
    this.pending = new Map();
    ws.addEventListener('message', (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        msg.error ? reject(new Error(`${msg.error.message} (${JSON.stringify(msg.error.data ?? '')})`)) : resolve(msg.result);
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.seq;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`CDP 超时: ${method}`));
        }
      }, 30000);
    });
  }

  async evaluate(expression) {
    const { result, exceptionDetails } = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (exceptionDetails) throw new Error(`页面脚本报错: ${exceptionDetails.text}`);
    return result.value;
  }
}

/** 等待页面出现某段文字，用于等真实后端返回 */
async function waitForText(cdp, needle, timeoutMs, label) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const hit = await cdp.evaluate(`document.body.innerText.includes(${JSON.stringify(needle)})`);
    if (hit) return Date.now() - started;
    await sleep(600);
  }
  throw new Error(`等待「${label}」超时（${timeoutMs}ms）`);
}

async function main() {
  try {
    rmSync(OUT_DIR, { recursive: true, force: true });
  } catch {
    // 上次异常退出时 Edge 可能还占着 profile，换个新目录继续
  }
  mkdirSync(OUT_DIR, { recursive: true });

  const edge = EDGE_CANDIDATES.find((p) => existsSync(p));
  if (!edge) throw new Error('没找到 Edge / Chrome 可执行文件');

  const profile = path.join(OUT_DIR, 'profile');
  // 注意：本机 `--headless=new` 截图是全白（渲染进程未真正出图），只能用旧无头模式
  const child = spawn(
    edge,
    [
      `--remote-debugging-port=${PORT}`,
      `--user-data-dir=${profile}`,
      '--headless=old',
      '--hide-scrollbars',
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-extensions',
      '--window-size=1440,900',
      '--force-device-scale-factor=1',
      'about:blank',
    ],
    { stdio: 'ignore' },
  );

  // 等 DevTools 端口就绪
  let targets = null;
  for (let i = 0; i < 40 && !targets; i += 1) {
    await sleep(300);
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await res.json();
      targets = list.find((t) => t.type === 'page');
    } catch {
      /* 端口还没起来 */
    }
  }
  if (!targets) throw new Error('DevTools 端口未就绪');

  const ws = new WebSocket(targets.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve, { once: true });
    ws.addEventListener('error', () => reject(new Error('WebSocket 连接失败')), { once: true });
  });

  const cdp = new Cdp(ws);
  const timeline = [];
  let index = 0;
  const t0 = Date.now();

  const shot = async (label) => {
    const { data } = await cdp.send('Page.captureScreenshot', { format: 'png' });
    index += 1;
    const name = `frame_${String(index).padStart(2, '0')}.png`;
    writeFileSync(path.join(OUT_DIR, name), Buffer.from(data, 'base64'));
    timeline.push({ frame: name, at: Date.now() - t0, label });
    console.log(`[shot] ${name} t=${((Date.now() - t0) / 1000).toFixed(1)}s ${label}`);
  };

  try {
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 900,
      deviceScaleFactor: 1,
      mobile: false,
    });

    await cdp.send('Page.navigate', { url: PAGE_URL });
    // 等 React 挂载 + 字体就位
    for (let i = 0; i < 40; i += 1) {
      const ready = await cdp.evaluate(
        "document.readyState === 'complete' && !!document.querySelector('textarea')",
      );
      if (ready) break;
      await sleep(400);
    }
    await sleep(1800);
    await shot('初始页：输入框与空状态');

    // 逐段输入，模拟真人打字
    const chunks = [PROMPT.slice(0, 12), PROMPT.slice(12, 26), PROMPT.slice(26, 40), PROMPT.slice(40)];
    for (let i = 0; i < chunks.length; i += 1) {
      const text = chunks.slice(0, i + 1).join('');
      await cdp.evaluate(`(() => {
        const el = document.querySelector('textarea');
        const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
        setter.call(el, ${JSON.stringify(text)});
        el.dispatchEvent(new Event('input', { bubbles: true }));
        return el.value.length;
      })()`);
      await sleep(450);
    }
    await sleep(700);
    await shot('已填写学习需求');

    // 点击生成
    const clicked = await cdp.evaluate(`(() => {
      const btn = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('生成'));
      if (!btn) return false;
      btn.click();
      return true;
    })()`);
    if (!clicked) throw new Error('没找到「生成」按钮');

    await sleep(1200);
    await shot('请求发出：按钮进入 loading');

    // 真实后端约 12~15 秒：等待期间连拍，抓到 loading 与结果出现的瞬间
    const waitStarted = Date.now();
    let appeared = false;
    while (Date.now() - waitStarted < 90000) {
      const state = await cdp.evaluate(`({
        done: !!document.querySelector('h3') && document.body.innerText.includes('推荐资源'),
        failed: document.body.innerText.includes('生成失败'),
        text: document.body.innerText.slice(0, 400),
      })`);
      if (state.failed) {
        throw new Error(`后端返回失败：${state.text.replace(/\s+/g, ' ').slice(0, 200)}`);
      }
      if (state.done) {
        appeared = true;
        break;
      }
      await shot('等待多智能体链路返回');
      await sleep(3200);
    }
    if (!appeared) throw new Error('等待结果超时');

    await sleep(900);
    // 结果刚出来时页面在顶部，稍微往下让「需求分析 / 课程规划」并排出现
    await cdp.evaluate(`(() => {
      const el = [...document.querySelectorAll('h2, h3, div')].find(
        (e) => e.textContent.trim().startsWith('学习规划已生成'));
      if (el) window.scrollTo({ top: el.getBoundingClientRect().top + window.scrollY - 60, behavior: 'instant' });
    })()`);
    await sleep(1200);
    await shot('需求分析五字段 + 课程规划周期');

    // 依次滚到各区块
    const scrollTo = async (needle, offset = 0) =>
      cdp.evaluate(`(() => {
        const target = [...document.querySelectorAll('h2, h3, div')].find(
          (el) => el.textContent.trim().startsWith(${JSON.stringify(needle)}) && el.children.length < 4,
        );
        if (!target) return false;
        const top = target.getBoundingClientRect().top + window.scrollY - ${offset};
        window.scrollTo({ top, behavior: 'instant' });
        return true;
      })()`);

    if (await scrollTo('学习路径', 110)) {
      await sleep(2200);
      await shot('阶段化学习计划（4 阶段，含每周任务）');
    }

    // 诊断条在「推荐资源」标题上方，定位到它才能把来源/质量/候选/重排一起框进来
    if (await scrollTo('检索来源', 100)) {
      await sleep(2400);
      await shot('资源列表 + RAG 诊断条（来源 / 质量 / 候选 / 重排）');
    }

    if (await scrollTo('整体评估', 140)) {
      await sleep(2200);
      await shot('六维评估与评估指标');
    }

    // 回到资源区做一次反馈
    await scrollTo('检索来源', 100);
    await sleep(900);
    const opened = await cdp.evaluate(`(() => {
      const btn = [...document.querySelectorAll('button')].find((b) => b.textContent.includes('评价此资源'));
      if (!btn) return false;
      btn.scrollIntoView({ block: 'center' });
      btn.click();
      return true;
    })()`);
    if (!opened) throw new Error('没找到「评价此资源」按钮');
    await sleep(1000);
    await shot('展开反馈表单');

    // 打 5 星
    const rated = await cdp.evaluate(`(() => {
      const box = [...document.querySelectorAll('div')].find((d) => d.textContent.trim().startsWith('评分：') && d.querySelectorAll('button').length === 5);
      if (!box) return false;
      const stars = [...box.querySelectorAll('button')];
      stars[4].click();
      return stars.length;
    })()`);
    if (!rated) throw new Error('没找到评分星标');
    await sleep(900);
    await shot('选择 5 星评分');

    // 提交「有用」
    const submitted = await cdp.evaluate(`(() => {
      const btn = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === '有用');
      if (!btn) return false;
      btn.click();
      return true;
    })()`);
    if (!submitted) throw new Error('没找到「有用」按钮');

    await waitForText(cdp, '已记录为', 20000, '反馈成功');
    await sleep(1500);
    await shot('反馈提交成功：评分与反馈条数已回写（真实写入后端）');

    // 收尾：回到顶部，露出整体
    await cdp.evaluate('window.scrollTo({ top: 0, behavior: "instant" })');
    await sleep(2500);
    await shot('整体视图');
    await sleep(3000);
    await shot('结束帧');
  } finally {
    writeFileSync(
      path.join(OUT_DIR, 'timeline.json'),
      JSON.stringify({ prompt: PROMPT, url: PAGE_URL, frames: timeline }, null, 2),
      'utf-8',
    );
    try {
      ws.close();
    } catch {
      /* ignore */
    }
    child.kill();
    // Edge 退出时还会占着 profile 里的文件，清理失败不影响产物
    for (let i = 0; i < 5; i += 1) {
      await sleep(400);
      try {
        rmSync(path.join(OUT_DIR, 'profile'), { recursive: true, force: true });
        break;
      } catch {
        /* 再试一次 */
      }
    }
  }

  const total = (timeline.at(-1).at / 1000).toFixed(1);
  console.log(`\n完成：${timeline.length} 帧，总时长 ${total}s，输出目录 ${OUT_DIR}`);
}

main().catch((error) => {
  console.error('录制失败:', error.stack || error.message);
  process.exit(1);
});
