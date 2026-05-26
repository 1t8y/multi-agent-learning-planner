import { Target, Route, BookOpen, ClipboardCheck } from 'lucide-react';
import { usePlanStore } from '../store/planStore';
import { ResultCard } from './ResultCard';
import { RequirementResult } from './RequirementResult';
import { PlanResult } from './PlanResult';
import { ResourcesResult } from './ResourcesResult';
import { AssessmentResult } from './AssessmentResult';

export function ResultSection() {
  const { planResult } = usePlanStore();

  if (!planResult) {
    return null;
  }

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
          <ResourcesResult data={planResult.resources} />
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
