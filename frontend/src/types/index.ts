// 前后端共用的数据结构定义。
// 字段名与后端 JSON 一一对应（后端是 snake_case），改名必须同时改后端，
// 否则运行时不报错、只是取到 undefined，排查成本很高。

/** 需求提取 Agent 的输出：五个字段，未识别到的为 null */
export interface RequirementData {
  /** 学习目标，例如「用视频学 Python 编程」 */
  learning_objective: string;
  /** 现有基础，例如「零基础」 */
  current_foundation: string | null;
  /** 每日可用时间，例如「2小时」 */
  daily_available_time: string;
  /** 学习偏好，例如「视频」 */
  learning_preference: string | null;
  /** 时间期望，例如「长期学习」 */
  time_expectation: string | null;
}

/** 学习路径中的一个阶段 */
export interface Stage {
  stage_name: string;
  study_content: string;
  time_allocation: string;
  milestone: string;
}

/** 分阶段学习路径 */
export interface LearningPath {
  stage_count: number;
  stages: Stage[];
}

/** 课程规划 Agent 的输出 */
export interface PlanData {
  goal_feasibility: string;
  estimated_duration: string;
  learning_path: LearningPath;
}

/** 一条推荐资源 */
export interface Resource {
  /** 知识库资源 id；LLM 凭空生成、未命中知识库时可能没有，反馈功能会因此失效 */
  id?: string;
  rank?: number;
  phase: string;
  type: string;
  title: string;
  description: string;
  duration: string;
  difficulty: string;
  recommendation_reason: string;
  url: string;
  /** 来源：知识库检索 / 联网搜索 / LLM 直接生成 */
  source?: 'knowledge_base' | 'web_search' | 'LLM生成';
  similarity?: number;
  rerank_score?: number;
  rerank_confidence?: number;
  /** 知识库资源的平均评分（0 表示还没有反馈） */
  rating?: number;
  /** 该资源累计收到的反馈条数 */
  feedback_count?: number;
}

/** 单个资源的反馈统计，由 /api/resources/{id}/stats 返回 */
export interface ResourceStats {
  id: string;
  title?: string;
  rating: number;
  feedback_count: number;
}

/** 资源推荐 Agent 的输出主体 */
export interface ResourcesData {
  resources: Resource[];
}

/** 检索链路自述信息：用于前端展示「结果是怎么来的」 */
export interface RagInfo {
  source_info: string;
  kb_relevance: number;
  rewrite_count: number;
  used_web_search: boolean;
  candidate_count?: number;
  search_query?: string;
  filters?: Record<string, unknown>;
  rerank?: {
    enabled: boolean;
    available: boolean;
    model: string;
  };
  quality?: {
    score: number;
    grade: 'high' | 'medium' | 'low' | string;
    passed: boolean;
    signals?: Record<string, number>;
    issues?: string[];
  };
}

/** 资源结果 + 检索自述信息 */
export interface ResourcesDataWithRag extends ResourcesData {
  rag_info?: RagInfo;
}

/** 评估指标：一个阶段下的单条指标 */
export interface Metric {
  name: string;
  description: string;
  target_value: string;
  measurement_method: string;
}

/** 某个阶段的所有评估指标 */
export interface AssessmentMetricItem {
  phase: string;
  metrics: Metric[];
}

/** 一条调整建议 */
export interface AdjustmentSuggestion {
  area: string;
  issue: string;
  suggestion: string;
  priority: string;
}

/** 评估总分与四个维度评分 */
export interface AssessmentSummary {
  overall_rating: string;
  feasibility_rating: number;
  content_rating: number;
  time_rating: number;
  method_rating: number;
}

/** 评估反馈 Agent 的输出 */
export interface AssessmentData {
  assessment_summary: AssessmentSummary;
  assessment_metrics: AssessmentMetricItem[];
  adjustment_suggestions: AdjustmentSuggestion[];
  recommendations: string[];
}

/** POST /api/plan 的完整返回体，四块结果对应页面四张卡片 */
export interface PlanResponse {
  requirement_data: RequirementData;
  plan: PlanData;
  resources: ResourcesDataWithRag;
  assessment: AssessmentData;
}

/** POST /api/feedback 的请求体 */
export interface FeedbackSubmission {
  resource_id: string;
  resource_title: string;
  resource_url: string;
  /** useful=有用，not_useful=没用，add_new=想补充新资源 */
  feedback_type: 'useful' | 'not_useful' | 'add_new';
  rating: number;
  comment: string;
  learning_objective: string;
}

/** POST /api/resources/submit 的请求体 */
export interface ResourceSubmission {
  title: string;
  description: string;
  url: string;
  resource_type: string;
  field: string;
  tags: string[];
  /** 难度等级，默认 intermediate；影响入库后能否被难度过滤命中 */
  level?: 'beginner' | 'intermediate' | 'advanced';
}

/** 全局状态容器的形状，字段与 setter 一一对应 */
export interface PlanStore {
  userInput: string;
  setUserInput: (input: string) => void;
  isLoading: boolean;
  setIsLoading: (loading: boolean) => void;
  planResult: PlanResponse | null;
  setPlanResult: (result: PlanResponse | null) => void;
  error: string | null;
  setError: (error: string | null) => void;
}
