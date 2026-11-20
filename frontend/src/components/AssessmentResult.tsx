// 评估反馈结果：总分与四维评分、逐阶段指标、调整建议、综合建议。
import { Fragment } from 'react';
import type { AssessmentData } from '../types';

interface AssessmentResultProps {
  /** 评估 Agent 的输出；score_average 低于 6 时后端会自动重规划，前端只展示最终结果 */
  data: AssessmentData;
}

/**
 * 学习方案评估展示。
 *
 * 四块内容分别对应后端 assessment 的四个字段，
 * 全部按数组顺序渲染，前端不做筛选或排序。
 */
export function AssessmentResult({ data }: AssessmentResultProps) {
  const { assessment_summary, assessment_metrics, adjustment_suggestions, recommendations } = data;

  const stats = [
    { label: '可行性', value: assessment_summary.feasibility_rating },
    { label: '内容性', value: assessment_summary.content_rating },
    { label: '时间性', value: assessment_summary.time_rating },
    { label: '方法性', value: assessment_summary.method_rating },
  ];

  return (
    <div className="assessment">
      <dl className="score">
        <div className="score__lead">
          <dt className="score__label">整体评估</dt>
          <dd className="score__rating">{assessment_summary.overall_rating}</dd>
        </div>
        <div className="score__stats">
          {stats.map((stat) => (
            <div className="stat" key={stat.label}>
              <dt className="stat__label">{stat.label}</dt>
              <dd className="stat__num">{stat.value}</dd>
            </div>
          ))}
        </div>
      </dl>

      <div className="block">
        <h3 className="block__title">评估指标</h3>
        <div className="metrics">
          {assessment_metrics.map((item, index) => (
            <div className="metrics__group" key={index}>
              <h4 className="metrics__phase">{item.phase}</h4>
              <dl className="metrics__rows">
                {item.metrics.map((metric, mIndex) => (
                  <Fragment key={mIndex}>
                    <dt>{metric.name}</dt>
                    <dd>{metric.description}</dd>
                  </Fragment>
                ))}
              </dl>
            </div>
          ))}
        </div>
      </div>

      <div className="block">
        <h3 className="block__title">调整建议</h3>
        <div className="advice">
          {adjustment_suggestions.map((suggestion, index) => (
            <div className="advice__item" key={index}>
              <div className="advice__head">
                <h4 className="advice__area">{suggestion.area}</h4>
                <span className="advice__prio">{suggestion.priority}优先级</span>
              </div>
              <p className="advice__line">
                <span className="advice__key">问题</span>
                {suggestion.issue}
              </p>
              <p className="advice__line">
                <span className="advice__key">建议</span>
                <span className="advice__fix">{suggestion.suggestion}</span>
              </p>
            </div>
          ))}
        </div>
      </div>

      <div className="block">
        <h3 className="block__title">综合建议</h3>
        <ol className="tips">
          {recommendations.map((rec, index) => (
            <li className="tips__item" key={index}>
              <span>{rec}</span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
