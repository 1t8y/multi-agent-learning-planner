// 需求分析结果：把后端抽出的五字段需求排成一条事实带。
import type { RequirementData } from '../types';

interface RequirementResultProps {
  /** 需求提取 Agent 的输出，字段可能为 null（用户没提到且无法推断） */
  data: RequirementData;
}

/**
 * 需求五字段展示。
 *
 * 每个字段都可能为空：后端只在识别到学习意图时才补默认值，
 * 所以这里统一用「未指定」兜底，而不是隐藏整格，空着比消失更容易让人理解。
 */
export function RequirementResult({ data }: RequirementResultProps) {
  // 五个字段的固定顺序，与后端抽取顺序一致
  const infoItems = [
    { label: '学习目标', value: data.learning_objective || '未指定' },
    { label: '现有基础', value: data.current_foundation || '未指定' },
    { label: '每日可用时间', value: data.daily_available_time || '未指定' },
    { label: '学习偏好', value: data.learning_preference || '未指定' },
    { label: '时间期望', value: data.time_expectation || '未指定' },
  ];

  return (
    <dl className="facts">
      {infoItems.map((item) => (
        <div className="facts__item" key={item.label}>
          <dt className="facts__label">{item.label}</dt>
          <dd className="facts__value">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
