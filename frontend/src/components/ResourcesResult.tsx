// 资源推荐结果：检索来源一行 + 资源条目列表 + 贡献入口。
import type { ResourcesDataWithRag, Resource, FeedbackSubmission, ResourceStats } from '../types';
import { ResourceFeedback } from './ResourceFeedback';

interface ResourcesResultProps {
  data: ResourcesDataWithRag;
  learningObjective: string;
  onFeedbackSubmit: (feedback: FeedbackSubmission) => Promise<void>;
  onAddResource: () => void;
  /** 反馈提交后刷新到的资源统计，按资源 ID 覆盖展示 */
  resourceStats?: Record<string, ResourceStats>;
}

// 来源 → 中文名。知识库、联网、LLM 生成的资源要能一眼区分
const sourceLabels: Record<string, string> = {
  'knowledge_base': '知识库',
  'web_search': '网络搜索',
  'LLM生成': 'AI 推荐',
};

/**
 * 资源列表。
 *
 * 顶部那行检索信息不是装饰：它说明这批结果是走知识库、联网还是纯 LLM 生成。
 * 演示和排障要用的细节（候选条数、是否重排）收在「检索详情」里，不占正文。
 */
export function ResourcesResult({ data, learningObjective, onFeedbackSubmit, onAddResource, resourceStats }: ResourcesResultProps) {
  const resources = data.resources || [];
  const ragInfo = data.rag_info;

  return (
    <div className="resources">
      {ragInfo && (
        <div className="provenance">
          <p className="provenance__row">
            <span className="provenance__item">
              检索来源 <span className="provenance__value">{ragInfo.source_info || 'AI 生成'}</span>
            </span>
            <span className="provenance__item">
              知识库匹配度 <span className="provenance__value">{Math.round(ragInfo.kb_relevance * 100)}%</span>
            </span>
            {ragInfo.used_web_search && <span className="provenance__item">已联网搜索补充</span>}
          </p>

          <details className="provenance__fold">
            <summary>检索详情</summary>
            <p className="provenance__more">
              {ragInfo.quality && (
                <>
                  检索质量
                  {ragInfo.quality.grade === 'high' ? '高' : ragInfo.quality.grade === 'medium' ? '中' : '低'}
                  （{Math.round(ragInfo.quality.score * 100)}%）
                </>
              )}
              {typeof ragInfo.candidate_count === 'number' && <>；候选 {ragInfo.candidate_count} 条</>}
              {ragInfo.rerank?.available && <>；Cross-Encoder 已重排</>}
              {ragInfo.rewrite_count > 0 && <>；查询改写 {ragInfo.rewrite_count} 次</>}
            </p>
          </details>
        </div>
      )}

      {resources.length === 0 ? (
        <div className="res-empty">
          <p className="res-empty__line">这次没有匹配到资源，可以补一条你知道的。</p>
          <button type="button" className="btn btn--quiet btn--sm" onClick={onAddResource}>
            贡献新资源
          </button>
        </div>
      ) : (
        resources.map((resource, index) => (
          <ResourceCard
            key={resource.id || index}
            resource={resource}
            learningObjective={learningObjective}
            onFeedbackSubmit={onFeedbackSubmit}
            stats={resource.id ? resourceStats?.[resource.id] : undefined}
          />
        ))
      )}

      <p className="fineprint">反馈会更新这条资源的评分，也会影响下一次推荐时它的排序。</p>
    </div>
  );
}

interface ResourceCardProps {
  resource: Resource;
  learningObjective: string;
  onFeedbackSubmit: (feedback: FeedbackSubmission) => Promise<void>;
  stats?: ResourceStats;
}

/**
 * 单条资源。
 *
 * 展示的评分优先用 stats（反馈后重新拉到的实时值），
 * 没有就退回 resource 自带的那份（/api/plan 返回时的快照）。
 */
function ResourceCard({ resource, learningObjective, onFeedbackSubmit, stats }: ResourceCardProps) {
  // 提交后刷新的统计优先于接口返回时的快照
  const shown = stats
    ? { ...resource, rating: stats.rating, feedback_count: stats.feedback_count }
    : resource;
  const feedbackCount = shown.feedback_count ?? 0;

  return (
    <article className="res">
      <div className="res__head">
        <h3 className="res__title">
          <a href={resource.url} target="_blank" rel="noopener noreferrer">
            {resource.title}
          </a>
        </h3>
        {(resource.rank || typeof resource.rerank_confidence === 'number') && (
          <p className="res__internal">
            {resource.rank ? `排序 #${resource.rank}` : ''}
            {resource.rank && typeof resource.rerank_confidence === 'number' ? '，' : ''}
            {typeof resource.rerank_confidence === 'number'
              ? `重排置信度 ${Math.round(resource.rerank_confidence * 100)}%`
              : ''}
          </p>
        )}
      </div>

      <p className="res__desc">{resource.description}</p>
      <p className="res__reason">
        <span className="res__key">推荐理由</span>
        {resource.recommendation_reason}
      </p>

      <dl className="res__facts">
        <div className="res__fact">
          <dt>类型</dt>
          <dd>{resource.type}</dd>
        </div>
        {resource.source && (
          <div className="res__fact">
            <dt>来源</dt>
            <dd>{sourceLabels[resource.source] || resource.source}</dd>
          </div>
        )}
        <div className="res__fact">
          <dt>难度</dt>
          <dd>{resource.difficulty}</dd>
        </div>
        <div className="res__fact">
          <dt>时长</dt>
          <dd>{resource.duration}</dd>
        </div>
        <div className="res__fact">
          <dt>适用阶段</dt>
          <dd>{resource.phase}</dd>
        </div>
        {feedbackCount > 0 && (
          <div className="res__fact">
            <dt>评分</dt>
            <dd>
              {Number(shown.rating ?? 0).toFixed(1)}，{feedbackCount} 条反馈
            </dd>
          </div>
        )}
      </dl>

      <ResourceFeedback
        resource={shown}
        learningObjective={learningObjective}
        onSubmit={onFeedbackSubmit}
      />
    </article>
  );
}
