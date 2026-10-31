// 需求分析结果：把后端抽出的五字段需求渲染成卡片网格。
import { Target, BookOpen, Clock, Video, Timer } from 'lucide-react';
import type { RequirementData } from '../types';

interface RequirementResultProps {
  /** 需求提取 Agent 的输出，字段可能为 null（用户没提到且无法推断） */
  data: RequirementData;
}

/**
 * 需求五字段展示。
 *
 * 每个字段都可能为空：后端只在识别到学习意图时才补默认值，
 * 所以这里统一用「未指定」兜底，而不是隐藏整行——空着比消失更容易让人理解。
 */
export function RequirementResult({ data }: RequirementResultProps) {
  // 五个字段与图标的固定映射，顺序即页面展示顺序
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
