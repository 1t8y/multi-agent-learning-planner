// 文件：scripts/verify-api-errors.mjs
// 功能：验证前端 API 层在各类故障下的错误提示，确保不会静默回退到假数据
// 输入：src/utils/api.ts；输出：四条场景的 PASS/FAIL 与退出码
//
// 做法：用 esbuild 把真实源码转译成 ESM（替代 import.meta.env），
// 再在 Node 里替换 globalThis.fetch 注入各种响应，检查抛出的错误文案。
// 这样测的是 src/utils/api.ts 本身，而不是复制一份逻辑。

import { buildSync } from 'esbuild';
import { mkdirSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const outfile = path.join(root, 'node_modules', '.cache', 'api_probe.mjs');

mkdirSync(path.dirname(outfile), { recursive: true });
buildSync({
  entryPoints: [path.join(root, 'src', 'utils', 'api.ts')],
  bundle: true,
  format: 'esm',
  // 浏览器里由 Vite 注入，Node 里没有，显式给定以便走开发分支
  define: {
    'import.meta.env.MODE': '"development"',
    'import.meta.env.VITE_API_BASE_URL': 'undefined',
  },
  outfile,
  logLevel: 'silent',
});

const { generateLearningPlan, submitFeedback, fetchResourceStats, submitResource } = await import(
  pathToFileURL(outfile).href
);

const results = [];
function check(name, passed, detail) {
  results.push({ name, passed, detail });
}

async function expectFailure(name, fakeFetch, pattern) {
  globalThis.fetch = fakeFetch;
  try {
    const data = await generateLearningPlan('我是零基础想学 Python');
    check(name, false, `静默成功并返回数据：${JSON.stringify(data).slice(0, 120)}`);
  } catch (error) {
    check(name, pattern.test(error.message), error.message);
  }
}

// 1. 后端未启动：fetch 直接 reject
await expectFailure(
  '后端未启动',
  async () => {
    throw new TypeError('Failed to fetch');
  },
  /无法连接后端服务/,
);

// 2. 服务端 500 且返回 detail
await expectFailure(
  '服务端 500 带 detail',
  async () =>
    new Response(JSON.stringify({ detail: '需求提取失败：模型超时' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    }),
  /服务端返回 500.*模型超时/,
);

// 3. 端口被其他服务占用，返回 HTML 而不是 JSON
await expectFailure(
  '端口被占返回 HTML',
  async () =>
    new Response('<!DOCTYPE html><html><body>404 page not found</body></html>', {
      status: 200,
      headers: { 'Content-Type': 'text/html' },
    }),
  /不是合法 JSON/,
);

// 4. 正常返回：必须原样交回数据，不能被错误处理破坏
globalThis.fetch = async () =>
  new Response(JSON.stringify({ requirement_data: { learning_objective: 'ok' } }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
try {
  const data = await generateLearningPlan('我是零基础想学 Python');
  check('正常返回', data?.requirement_data?.learning_objective === 'ok', '数据完整透传');
} catch (error) {
  check('正常返回', false, `不该抛错：${error.message}`);
}

// 5. 反馈提交成功：必须拿到 feedback_id，否则前端无法确认落库
globalThis.fetch = async () =>
  new Response(JSON.stringify({ success: true, feedback_id: 'fb-123' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
const feedback = {
  resource_id: 'python-bilibili-001',
  resource_title: 'Python基础教程',
  resource_url: 'https://example.com',
  feedback_type: 'useful',
  rating: 5,
  comment: '',
  learning_objective: 'Python',
};
try {
  const data = await submitFeedback(feedback);
  check('反馈提交成功', data?.feedback_id === 'fb-123', `feedback_id=${data?.feedback_id}`);
} catch (error) {
  check('反馈提交成功', false, `不该抛错：${error.message}`);
}

// 6. 反馈提交被后端拒绝（如评分为 0）：错误必须冒泡给界面，不能当成功
globalThis.fetch = async () =>
  new Response(JSON.stringify({ detail: '反馈提交失败' }), {
    status: 400,
    headers: { 'Content-Type': 'application/json' },
  });
try {
  await submitFeedback({ ...feedback, rating: 0 });
  check('反馈提交失败', false, '静默成功，用户会以为已记录');
} catch (error) {
  check('反馈提交失败', /服务端返回 400.*反馈提交失败/.test(error.message), error.message);
}

// 7. 资源统计不存在：抛 404，前端据此跳过评分刷新而不是展示 0 分
globalThis.fetch = async () =>
  new Response(JSON.stringify({ detail: '资源不存在: ghost' }), {
    status: 404,
    headers: { 'Content-Type': 'application/json' },
  });
try {
  await fetchResourceStats('ghost');
  check('统计资源不存在', false, '静默成功');
} catch (error) {
  check('统计资源不存在', /服务端返回 404.*资源不存在/.test(error.message), error.message);
}

// 8. 资源提交成功：必须拿到 submission_id，前端据此提示「已提交，待审核」
const submission = {
  title: 'Python 官方教程',
  description: '官方入门文档',
  url: 'https://docs.python.org/3/tutorial/',
  resource_type: '文档资料',
  field: '编程',
  tags: ['Python', '官方'],
};
globalThis.fetch = async () =>
  new Response(JSON.stringify({ success: true, submission_id: 'sub-1', status: 'pending' }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
try {
  const data = await submitResource(submission);
  check('资源提交成功', data?.submission_id === 'sub-1' && data?.status === 'pending', `id=${data?.submission_id}`);
} catch (error) {
  check('资源提交成功', false, `不该抛错：${error.message}`);
}

// 9. 资源提交校验失败（如领域不在白名单）：400 必须冒泡，不能被当成 500
globalThis.fetch = async () =>
  new Response(JSON.stringify({ detail: '领域必须是 AI/数学/编程 之一' }), {
    status: 400,
    headers: { 'Content-Type': 'application/json' },
  });
try {
  await submitResource({ ...submission, field: '历史' });
  check('资源提交被拒', false, '静默成功，脏数据会进入待审核队列');
} catch (error) {
  check('资源提交被拒', /服务端返回 400.*领域/.test(error.message), error.message);
}

for (const item of results) {
  console.log(`${item.passed ? 'PASS' : 'FAIL'}  ${item.name.padEnd(18)} -> ${item.detail}`);
}
const failed = results.filter((item) => !item.passed).length;
console.log(`\n${results.length - failed}/${results.length} 通过`);
process.exit(failed === 0 ? 0 : 1);
