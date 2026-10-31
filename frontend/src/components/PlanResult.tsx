import { CheckCircle, Clock, Target } from 'lucide-react';
import type { PlanData } from '../types';

interface PlanResultProps {
  data: PlanData;
}

export function PlanResult({ data }: PlanResultProps) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 rounded-xl p-4 border border-green-100">
          <div className="flex items-center gap-3 mb-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <span className="text-sm font-medium text-green-700">目标可行性</span>
          </div>
          <p className="text-gray-800 font-semibold">{data.goal_feasibility}</p>
        </div>
        <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl p-4 border border-blue-100">
          <div className="flex items-center gap-3 mb-2">
            <Clock className="w-5 h-5 text-blue-500" />
            <span className="text-sm font-medium text-blue-700">预估周期</span>
          </div>
          <p className="text-gray-800 font-semibold">{data.estimated_duration}</p>
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <Target className="w-5 h-5 text-primary-500" />
          <span className="font-semibold text-gray-800">学习路径（共{data.learning_path.stage_count}个阶段）</span>
        </div>
        <div className="space-y-3">
          {data.learning_path.stages.map((stage, index) => (
            <div
              key={index}
              className="bg-white rounded-xl p-4 border border-gray-100 hover:border-primary-200 transition-all duration-300"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                  <span className="w-8 h-8 bg-primary-100 text-primary-600 rounded-full flex items-center justify-center font-semibold text-sm">
                    {index + 1}
                  </span>
                  <h4 className="font-semibold text-gray-800">{stage.stage_name}</h4>
                </div>
                <span className="text-sm bg-primary-50 text-primary-600 px-3 py-1 rounded-full">
                  {stage.time_allocation}
                </span>
              </div>
              <p className="text-gray-600 mb-2">
                <span className="text-sm text-gray-500">学习内容：</span>
                {stage.study_content}
              </p>
              <p className="text-sm text-gray-600">
                <span className="text-gray-500">阶段目标：</span>
                <span className="font-medium text-primary-600">{stage.milestone}</span>
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
