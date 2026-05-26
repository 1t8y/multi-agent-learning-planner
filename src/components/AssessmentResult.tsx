import { Star, TrendingUp, AlertTriangle, Lightbulb } from 'lucide-react';
import type { AssessmentData } from '../types';

interface AssessmentResultProps {
  data: AssessmentData;
}

const priorityColors: Record<string, string> = {
  '高': 'bg-red-500',
  '中': 'bg-yellow-500',
  '低': 'bg-green-500',
};

export function AssessmentResult({ data }: AssessmentResultProps) {
  const { assessment_summary, assessment_metrics, adjustment_suggestions, recommendations } = data;

  return (
    <div className="space-y-6">
      <div className="bg-gradient-to-br from-amber-50 to-yellow-50 rounded-xl p-5 border border-amber-100">
        <div className="flex items-center gap-3 mb-4">
          <Star className="w-6 h-6 text-amber-500" />
          <span className="font-semibold text-gray-800">整体评估</span>
        </div>
        <div className="flex items-center gap-4 mb-4">
          <span className="text-3xl font-bold text-amber-600">{assessment_summary.overall_rating}</span>
          <div className="flex-1 grid grid-cols-2 gap-2">
            <div className="text-center p-2 bg-white rounded-lg">
              <p className="text-2xl font-bold text-primary-600">{assessment_summary.feasibility_rating}</p>
              <p className="text-xs text-gray-500">可行性</p>
            </div>
            <div className="text-center p-2 bg-white rounded-lg">
              <p className="text-2xl font-bold text-primary-600">{assessment_summary.content_rating}</p>
              <p className="text-xs text-gray-500">内容性</p>
            </div>
            <div className="text-center p-2 bg-white rounded-lg">
              <p className="text-2xl font-bold text-primary-600">{assessment_summary.time_rating}</p>
              <p className="text-xs text-gray-500">时间性</p>
            </div>
            <div className="text-center p-2 bg-white rounded-lg">
              <p className="text-2xl font-bold text-primary-600">{assessment_summary.method_rating}</p>
              <p className="text-xs text-gray-500">方法性</p>
            </div>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-green-500" />
          <span className="font-semibold text-gray-800">评估指标</span>
        </div>
        <div className="space-y-3">
          {assessment_metrics.map((item, index) => (
            <div key={index} className="bg-white rounded-xl p-4 border border-gray-100">
              <h4 className="font-semibold text-gray-800 mb-3">{item.phase}</h4>
              <div className="space-y-2">
                {item.metrics.map((metric, mIndex) => (
                  <div key={mIndex} className="flex items-center gap-3 text-sm">
                    <span className="font-medium text-gray-700">{metric.name}</span>
                    <span className="text-gray-500">-</span>
                    <span className="text-gray-600">{metric.description}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-orange-500" />
          <span className="font-semibold text-gray-800">调整建议</span>
        </div>
        <div className="space-y-3">
          {adjustment_suggestions.map((suggestion, index) => (
            <div key={index} className="bg-white rounded-xl p-4 border border-gray-100">
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-2 h-2 ${priorityColors[suggestion.priority] || 'bg-gray-400'} rounded-full`} />
                <span className="font-semibold text-gray-800">{suggestion.area}</span>
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                  {suggestion.priority}优先级
                </span>
              </div>
              <p className="text-sm text-gray-600 mb-1">
                <span className="text-gray-500">问题：</span>{suggestion.issue}
              </p>
              <p className="text-sm text-primary-600">
                <span className="text-gray-500">建议：</span>{suggestion.suggestion}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-5 h-5 text-yellow-500" />
          <span className="font-semibold text-gray-800">综合建议</span>
        </div>
        <div className="space-y-2">
          {recommendations.map((rec, index) => (
            <div key={index} className="flex items-start gap-3 bg-white rounded-xl p-4 border border-gray-100">
              <span className="w-6 h-6 bg-yellow-100 text-yellow-600 rounded-full flex items-center justify-center text-sm font-semibold flex-shrink-0">
                {index + 1}
              </span>
              <p className="text-gray-700">{rec}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
