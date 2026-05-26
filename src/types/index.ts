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
  phase: string;
  type: string;
  title: string;
  description: string;
  duration: string;
  difficulty: string;
  recommendation_reason: string;
  url: string;
}

export interface ResourcesData {
  resources: Resource[];
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
  resources: ResourcesData;
  assessment: AssessmentData;
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
