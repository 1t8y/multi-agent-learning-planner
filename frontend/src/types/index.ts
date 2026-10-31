export interface RequirementData {
  learning_objective: string;
  current_foundation: string | null;
  daily_available_time: string;
  learning_preference: string | null;
  time_expectation: string | null;
}

export interface Stage {
  stage_name: string;
  study_content: string;
  time_allocation: string;
  milestone: string;
}

export interface LearningPath {
  stage_count: number;
  stages: Stage[];
}

export interface PlanData {
  goal_feasibility: string;
  estimated_duration: string;
  learning_path: LearningPath;
}

export interface Resource {
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

export interface ResourcesData {
  resources: Resource[];
}

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

export interface ResourcesDataWithRag extends ResourcesData {
  rag_info?: RagInfo;
}

export interface Metric {
  name: string;
  description: string;
  target_value: string;
  measurement_method: string;
}

export interface AssessmentMetricItem {
  phase: string;
  metrics: Metric[];
}

export interface AdjustmentSuggestion {
  area: string;
  issue: string;
  suggestion: string;
  priority: string;
}

export interface AssessmentSummary {
  overall_rating: string;
  feasibility_rating: number;
  content_rating: number;
  time_rating: number;
  method_rating: number;
}

export interface AssessmentData {
  assessment_summary: AssessmentSummary;
  assessment_metrics: AssessmentMetricItem[];
  adjustment_suggestions: AdjustmentSuggestion[];
  recommendations: string[];
}

export interface PlanResponse {
  requirement_data: RequirementData;
  plan: PlanData;
  resources: ResourcesDataWithRag;
  assessment: AssessmentData;
}

export interface FeedbackSubmission {
  resource_id: string;
  resource_title: string;
  resource_url: string;
  feedback_type: 'useful' | 'not_useful' | 'add_new';
  rating: number;
  comment: string;
  learning_objective: string;
}

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
