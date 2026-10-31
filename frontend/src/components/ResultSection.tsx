import { useState } from 'react';
import { Target, Route, BookOpen, ClipboardCheck } from 'lucide-react';
import { usePlanStore } from '../store/planStore';
import { fetchResourceStats, submitFeedback } from '../utils/api';
import { ResultCard } from './ResultCard';
import { RequirementResult } from './RequirementResult';
import { PlanResult } from './PlanResult';
import { ResourcesResult } from './ResourcesResult';
import { AssessmentResult } from './AssessmentResult';
import { ResourceSubmitModal } from './ResourceSubmitModal';
import type { FeedbackSubmission, ResourceStats } from '../types';

export function ResultSection() {
  const { planResult } = usePlanStore();
  // 反馈提交后刷新的资源统计，按资源 ID 覆盖到卡片展示上
  const [resourceStats, setResourceStats] = useState<Record<string, ResourceStats>>({});
  const [submitModalOpen, setSubmitModalOpen] = useState(false);

  if (!planResult) {
    return null;
  }

  const learningObjective = planResult.requirement_data?.learning_objective || '';

  const handleFeedbackSubmit = async (feedback: FeedbackSubmission) => {
    await submitFeedback(feedback);

    if (!feedback.resource_id) {
      return;
    }
    try {
      const latest = await fetchResourceStats(feedback.resource_id);
      setResourceStats((prev) => ({ ...prev, [feedback.resource_id]: latest }));
    } catch (error) {
      // 反馈已经落库，只是统计没刷新成功，不应把它报成提交失败
      console.warn('反馈已提交，但刷新资源统计失败:', error);
    }
  };

  const handleAddResource = () => {
    setSubmitModalOpen(true);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-white mb-2">学习规划已生成</h2>
        <p className="text-white/80">以下是为您量身定制的学习方案</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ResultCard
          title="需求分析"
          icon={<Target className="w-5 h-5 text-white" />}
          color="bg-gradient-to-r from-blue-500 to-indigo-600"
        >
          <RequirementResult data={planResult.requirement_data} />
        </ResultCard>

        <ResultCard
          title="课程规划"
          icon={<Route className="w-5 h-5 text-white" />}
          color="bg-gradient-to-r from-green-500 to-emerald-600"
        >
          <PlanResult data={planResult.plan} />
        </ResultCard>

        <ResultCard
          title="资源推荐"
          icon={<BookOpen className="w-5 h-5 text-white" />}
          color="bg-gradient-to-r from-purple-500 to-pink-600"
        >
          <ResourcesResult 
            data={planResult.resources} 
            learningObjective={learningObjective}
            onFeedbackSubmit={handleFeedbackSubmit}
            onAddResource={handleAddResource}
            resourceStats={resourceStats}
          />
        </ResultCard>

        <ResultCard
          title="评估反馈"
          icon={<ClipboardCheck className="w-5 h-5 text-white" />}
          color="bg-gradient-to-r from-orange-500 to-amber-600"
        >
          <AssessmentResult data={planResult.assessment} />
        </ResultCard>
      </div>

      <ResourceSubmitModal
        open={submitModalOpen}
        onClose={() => setSubmitModalOpen(false)}
      />
    </div>
  );
}
