// 后端接口的唯一调用入口。
// 所有网络错误都在这里被翻译成人能看懂的中文提示，组件层只负责展示，
// 因此组件的 catch 里拿到的一定是可读文本，不会是 "Failed to fetch"。
import type { FeedbackSubmission, PlanResponse, ResourceStats, ResourceSubmission } from '../types';

// 生产环境: API 与前端同域，使用相对路径
// 开发环境: 连接本地后端（默认 8001，8000 常被其他服务占用）
const DEFAULT_DEV_API_BASE_URL = 'http://localhost:8001';
const API_BASE_URL =
  import.meta.env.MODE === 'production'
    ? ''
    : import.meta.env.VITE_API_BASE_URL || DEFAULT_DEV_API_BASE_URL;

/** 反馈提交成功的返回体：feedback_id 用于后续定位这条评价。 */
export interface FeedbackResponse {
  success: boolean;
  feedback_id: string;
}

/** 资源提交成功的返回体：新资源进待审核队列，status 正常为 pending。 */
export interface ResourceSubmissionResponse {
  success: boolean;
  submission_id: string;
  /** 后端返回的提交状态，正常情况下为 pending */
  status?: string;
}

/** 把 fetch 抛出的原始异常翻译成用户能看懂的错误信息 */
function describeError(error: unknown): string {
  if (error instanceof Error) {
    if (error.name === 'AbortError') {
      return '请求已取消';
    }
    if (error instanceof TypeError || /failed to fetch|networkerror|load failed/i.test(error.message)) {
      return `无法连接后端服务（${API_BASE_URL || '当前域名'}），请确认后端已启动`;
    }
    return error.message;
  }
  return String(error);
}

/** 读取响应体：优先当 JSON 解析，失败时给出可诊断的提示而不是原始的解析异常 */
async function readBody(response: Response): Promise<Record<string, unknown> | string> {
  const text = await response.text();
  if (!text) {
    return '';
  }
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return text.slice(0, 120);
  }
}

/** 统一请求入口：负责错误翻译、非 2xx 处理和非 JSON 响应识别 */
async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    throw new Error(describeError(error));
  }

  const body = await readBody(response);

  if (!response.ok) {
    const detail = typeof body === 'object' && body !== null ? body.detail : body;
    throw new Error(
      detail
        ? `服务端返回 ${response.status}：${String(detail)}`
        : `服务端返回 ${response.status}`,
    );
  }

  if (typeof body === 'string' && !body) {
    throw new Error('服务端返回了空响应，请查看后端日志');
  }

  if (typeof body === 'string') {
    // 端口被其他服务占用时最典型的表现：返回 HTML 而不是 JSON
    throw new Error(`响应不是合法 JSON，请确认端口未被其他服务占用：${body}`);
  }

  return body as unknown as T;
}

/**
 * 请求学习规划：输入一句自然语言描述，返回需求、计划、资源、评估四块结果。
 *
 * 这是全站最慢的接口（要走 LLM，约十几秒），调用方必须自行处理加载态。
 */
export async function generateLearningPlan(userInput: string): Promise<PlanResponse> {
  return requestJson<PlanResponse>('/api/plan', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ userInput }),
  });
}

/**
 * 提交一条资源评分/意见。
 *
 * 后端会把评分写进反馈记录，并更新该资源的平均分与反馈条数。
 */
export async function submitFeedback(feedback: FeedbackSubmission): Promise<FeedbackResponse> {
  return requestJson<FeedbackResponse>('/api/feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(feedback),
  });
}

/**
 * 查询某个资源的实时评分与反馈条数。
 *
 * 资源 id 来自 /api/plan 的返回，必须原样透传；编码是防御性的，
 * 避免 id 里出现特殊字符时把路径拼坏。
 */
export async function fetchResourceStats(resourceId: string): Promise<ResourceStats> {
  return requestJson<ResourceStats>(
    `/api/resources/${encodeURIComponent(resourceId)}/stats`,
    { method: 'GET' },
  );
}

/**
 * 提交用户推荐的新资源。
 *
 * 不会直接进知识库：后端先落进待审核队列，审核通过才会被检索到。
 * 领域只接受 AI / 编程 / 数学，其它值会被后端拒绝。
 */
export async function submitResource(
  submission: ResourceSubmission,
): Promise<ResourceSubmissionResponse> {
  return requestJson<ResourceSubmissionResponse>('/api/resources/submit', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(submission),
  });
}
