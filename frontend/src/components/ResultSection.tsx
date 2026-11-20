// 结果区：四个区块（需求 / 规划 / 资源 / 评估）的版式容器。
// 同时负责反馈提交后的统计刷新，以及「推荐资源」弹窗的开关。
import { useState } from 'react';
import { usePlanStore } from '../store/planStore';
import { fetchResourceStats, submitFeedback } from '../utils/api';
import { ResultCard } from './ResultCard';
import { RequirementResult } from './RequirementResult';
import { PlanResult } from './PlanResult';
import { ResourcesResult } from './ResourcesResult';
import { AssessmentResult } from './AssessmentResult';
import { ResourceSubmitModal } from './ResourceSubmitModal';
import { LoadingSpinner } from './LoadingSpinner';
import type { FeedbackSubmission, ResourceStats } from '../types';

/**
 * 学习方案结果区。
 *
 * 三种状态：正在生成（骨架）、还没生成（说明会得到什么）、已生成（四个区块）。
 * 「没生成过」和「生成失败」在视觉上不会混在一起，失败只由根组件的错误条表达。
 */
export function ResultSection() {
  const { planResult, isLoading } = usePlanStore();
  // 反馈提交后刷新的资源统计，按资源 ID 覆盖到区块展示上
  const [resourceStats, setResourceStats] = useState<Record<string, ResourceStats>>({});
  const [submitModalOpen, setSubmitModalOpen] = useState(false);

  if (!planResult) {
    return isLoading ? <LoadingSpinner /> : <EmptyState />;
  }

  const learningObjective = planResult.requirement_data?.learning_objective || '';
  const resources = planResult.resources.resources || [];

  /**
   * 提交评分，并在成功后刷新该资源的统计。
   *
   * 分两步：先提交反馈（失败要抛给调用方，让用户看到），
   * 再拉一次最新统计（失败只打警告，因为反馈已经落库了，不能误报成提交失败）。
   */
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

  /** 打开「推荐新资源」弹窗。 */
  const handleAddResource = () => {
    setSubmitModalOpen(true);
  };

  return (
    <div className="result">
      <ResultCard
        title="需求分析"
        aside={<span className="section__count" role="status">已生成</span>}
      >
        <RequirementResult data={planResult.requirement_data} />
      </ResultCard>

      <ResultCard
        title="课程规划"
        aside={<span className="section__count">共 {planResult.plan.learning_path.stage_count} 个阶段</span>}
      >
        <PlanResult data={planResult.plan} />
      </ResultCard>

      <ResultCard
        title="资源推荐"
        aside={
          resources.length > 0 ? (
            <>
              <span className="section__count">共 {resources.length} 个</span>
              <button type="button" className="btn btn--quiet btn--sm" onClick={handleAddResource}>
                贡献新资源
              </button>
            </>
          ) : null
        }
      >
        <ResourcesResult
          data={planResult.resources}
          learningObjective={learningObjective}
          onFeedbackSubmit={handleFeedbackSubmit}
          onAddResource={handleAddResource}
          resourceStats={resourceStats}
        />
      </ResultCard>

      <ResultCard title="评估反馈">
        <AssessmentResult data={planResult.assessment} />
      </ResultCard>

      <ResourceSubmitModal
        open={submitModalOpen}
        onClose={() => setSubmitModalOpen(false)}
      />
    </div>
  );
}

/**
 * 还没生成时的说明。
 *
 * 只陈述这个工具会返回什么，不放示例结果，避免把演示数据当成真实输出。
 */
function EmptyState() {
  return (
    <div className="empty">
      <p className="empty__lead">生成后，这一屏会出现四块内容</p>
      <ul className="empty__list">
        <li className="empty__item">
          <h2 className="empty__name">需求分析</h2>
          <p className="empty__line">从你的一句话里抽出目标、基础、每天可用时间、学习偏好和时间期望。</p>
        </li>
        <li className="empty__item">
          <h2 className="empty__name">课程规划</h2>
          <p className="empty__line">按阶段拆开，每个阶段写明学习内容、时间分配和阶段目标。</p>
        </li>
        <li className="empty__item">
          <h2 className="empty__name">资源推荐</h2>
          <p className="empty__line">从知识库检索，覆盖不到时联网补充，并标明每条资源的来源。</p>
        </li>
        <li className="empty__item">
          <h2 className="empty__name">评估反馈</h2>
          <p className="empty__line">给方案打分，指出哪一步偏紧、该怎么调；均分低于 6 分会重新生成。</p>
        </li>
      </ul>
    </div>
  );
}
