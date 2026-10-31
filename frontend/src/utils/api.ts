import type { FeedbackSubmission, PlanResponse, ResourceStats, ResourceSubmission } from '../types';

// 生产环境: API 与前端同域，使用相对路径
// 开发环境: 连接本地后端（默认 8001，8000 常被其他服务占用）
const DEFAULT_DEV_API_BASE_URL = 'http://localhost:8001';
const API_BASE_URL =
  import.meta.env.MODE === 'production'
    ? ''
    : import.meta.env.VITE_API_BASE_URL || DEFAULT_DEV_API_BASE_URL;

export interface FeedbackResponse {
  success: boolean;
  feedback_id: string;
}

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

export async function generateLearningPlan(userInput: string): Promise<PlanResponse> {
  return requestJson<PlanResponse>('/api/plan', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ userInput }),
  });
}

export async function submitFeedback(feedback: FeedbackSubmission): Promise<FeedbackResponse> {
  return requestJson<FeedbackResponse>('/api/feedback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(feedback),
  });
}

export async function fetchResourceStats(resourceId: string): Promise<ResourceStats> {
  return requestJson<ResourceStats>(
    `/api/resources/${encodeURIComponent(resourceId)}/stats`,
    { method: 'GET' },
  );
}

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
