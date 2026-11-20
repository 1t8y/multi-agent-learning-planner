// 单个资源的评价控件：折叠态一个按钮，展开后是 有用/没用 + 五星 + 备注。
import { useState } from 'react';
import type { Resource, FeedbackSubmission } from '../types';

interface ResourceFeedbackProps {
  resource: Resource;
  learningObjective: string;
  /** 提交反馈到后端；失败时抛错，由本组件展示错误 */
  onSubmit: (feedback: FeedbackSubmission) => Promise<void>;
}

/**
 * 资源评价。
 *
 * 三态展示：可评价 → 提交中（按钮禁用 + 转圈）→ 已提交（换成一句回执）。
 * 「已提交」是终态，本轮不再允许改评，避免重复计数把平均分刷乱。
 */
export function ResourceFeedback({ resource, learningObjective, onSubmit }: ResourceFeedbackProps) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [feedbackType, setFeedbackType] = useState<'useful' | 'not_useful' | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  /**
   * 提交评价。
   *
   * 评分是必填项（0 星直接拦在前端），有用/没用则通过按钮参数区分。
   * 失败时只在本组件内显示红字，不影响页面上其它资源的评价。
   */
  const handleSubmit = async (type: 'useful' | 'not_useful') => {
    if (rating === 0) {
      setErrorMessage('请先选择评分');
      return;
    }

    setErrorMessage(null);
    setSubmitting(true);
    try {
      await onSubmit({
        // 没有 id 的是网络/LLM 资源，后端不会更新知识库评分，但仍然记录反馈
        resource_id: resource.id ?? '',
        resource_title: resource.title,
        resource_url: resource.url,
        feedback_type: type,
        rating,
        comment,
        learning_objective: learningObjective,
      });
      setFeedbackType(type);
      setSubmitted(true);
      setShowFeedback(false);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setSubmitting(false);
    }
  };

  const hasStats = typeof resource.feedback_count === 'number' && resource.feedback_count > 0;

  if (submitted) {
    return (
      <p className="feedback__done">
        <span>已记下：{feedbackType === 'useful' ? '有用' : '不太有用'}</span>
        {hasStats && (
          <span className="feedback__done-note">
            当前 {Number(resource.rating ?? 0).toFixed(1)} 分，{resource.feedback_count} 条反馈
          </span>
        )}
      </p>
    );
  }

  return (
    <div className="feedback">
      {!showFeedback ? (
        <button type="button" className="feedback__trigger" onClick={() => setShowFeedback(true)}>
          评价此资源
        </button>
      ) : (
        <div className="feedback__panel">
          <div className="feedback__head">
            <p className="feedback__question">这个资源对你有帮助吗？</p>
            <button
              type="button"
              className="feedback__close"
              onClick={() => setShowFeedback(false)}
              aria-label="收起评价"
            >
              ×
            </button>
          </div>

          <div className="stars" role="group" aria-label="评分">
            {[1, 2, 3, 4, 5].map((star) => (
              <button
                key={star}
                type="button"
                className={`stars__btn ${(hoverRating || rating) >= star ? 'is-on' : ''}`}
                onClick={() => setRating(star)}
                onMouseEnter={() => setHoverRating(star)}
                onMouseLeave={() => setHoverRating(0)}
                disabled={submitting}
                aria-label={`${star} 分`}
                aria-pressed={rating === star}
              >
                {(hoverRating || rating) >= star ? '★' : '☆'}
              </button>
            ))}
          </div>

          <label className="visually-hidden" htmlFor={`comment-${resource.id || resource.title}`}>
            补充评价
          </label>
          <textarea
            id={`comment-${resource.id || resource.title}`}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="补充一句（可选）"
            disabled={submitting}
            className="feedback__comment"
          />

          <div className="feedback__actions">
            <button
              type="button"
              className="btn btn--sm"
              onClick={() => handleSubmit('useful')}
              disabled={submitting}
            >
              有用
            </button>
            <button
              type="button"
              className="btn btn--sm"
              onClick={() => handleSubmit('not_useful')}
              disabled={submitting}
            >
              不太有用
            </button>
            {submitting && (
              <span className="feedback__pending" role="status">
                提交中…
              </span>
            )}
          </div>

          {errorMessage && (
            <p className="feedback__error" role="alert">
              提交失败：{errorMessage}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
