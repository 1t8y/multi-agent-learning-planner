import { Target, BookOpen, Clock, Video, Timer } from 'lucide-react';
import type { RequirementData } from '../types';

interface RequirementResultProps {
  data: RequirementData;
}

export function RequirementResult({ data }: RequirementResultProps) {
  const infoItems = [
    {
      icon: <Target className="w-5 h-5" />,
      label: '学习目标',
      value: data.learning_objective || '未指定',
    },
    {
      icon: <BookOpen className="w-5 h-5" />,
      label: '现有基础',
      value: data.current_foundation || '未指定',
    },
    {
      icon: <Clock className="w-5 h-5" />,
      label: '每日可用时间',
      value: data.daily_available_time || '未指定',
    },
    {
      icon: <Video className="w-5 h-5" />,
      label: '学习偏好',
      value: data.learning_preference || '未指定',
    },
    {
      icon: <Timer className="w-5 h-5" />,
      label: '时间期望',
      value: data.time_expectation || '未指定',
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {infoItems.map((item) => (
        <div
          key={item.label}
          className="bg-white rounded-xl p-4 border border-gray-100 hover:border-primary-200 transition-all duration-300"
        >
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary-50 rounded-lg flex items-center justify-center text-primary-500">
              {item.icon}
            </div>
            <div>
              <p className="text-sm text-gray-500">{item.label}</p>
              <p className="font-semibold text-gray-800">{item.value}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
