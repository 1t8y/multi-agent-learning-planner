import { Target, Route, BookOpen, ClipboardCheck } from 'lucide-react';
import { usePlanStore } from '../store/planStore';
import { ResultCard } from './ResultCard';
import { RequirementResult } from './RequirementResult';
import { PlanResult } from './PlanResult';
import { ResourcesResult } from './ResourcesResult';
import { AssessmentResult } from './AssessmentResult';
import type { FeedbackSubmission } from '../types';

export function ResultSection() {
  const { planResult } = usePlanStore();

  if (!planResult) {
    return null;
  }

  const learningObjective = planResult.requirement_data?.learning_objective || '';

  const handleFeedbackSubmit = (feedback: FeedbackSubmission) => {
    console.log('提交反馈:', feedback);
    alert(`感谢您的反馈！\n资源: ${feedback.resource_title}\n反馈类型: ${feedback.feedback_type}`);
  };

  const handleAddResource = () => {
    console.log('添加新资源');
    alert('资源提交功能正在开发中，敬请期待！');
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
    </div>
  );
}
