import { useState } from 'react';
import { ThumbsUp, ThumbsDown, Star, X, Check, Loader2 } from 'lucide-react';
import type { Resource, FeedbackSubmission } from '../types';

interface ResourceFeedbackProps {
  resource: Resource;
  learningObjective: string;
  /** 提交反馈到后端；失败时抛错，由本组件展示错误 */
  onSubmit: (feedback: FeedbackSubmission) => Promise<void>;
}

export function ResourceFeedback({ resource, learningObjective, onSubmit }: ResourceFeedbackProps) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [feedbackType, setFeedbackType] = useState<'useful' | 'not_useful' | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

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
      <div className="flex flex-wrap items-center gap-2 mt-3 text-sm">
        <Check className="w-4 h-4 text-green-500" />
        <span className="text-green-600">
          已记录为{feedbackType === 'useful' ? '有用' : '不太有用'}
        </span>
        {hasStats && (
          <span className="text-xs text-amber-600">
            该资源当前 {Number(resource.rating ?? 0).toFixed(1)} 分（{resource.feedback_count} 条反馈）
          </span>
        )}
      </div>
    );
  }

  return (
    <div className="mt-3">
      {!showFeedback ? (
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowFeedback(true)}
            className="flex items-center gap-1 px-3 py-1.5 text-xs bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-lg transition-colors"
          >
            <Star className="w-3.5 h-3.5" />
            评价此资源
          </button>
          {resource.source && (
            <span className="text-xs px-2 py-1 rounded-full bg-blue-50 text-blue-600">
              {resource.source === 'knowledge_base' ? '📚 知识库' : 
               resource.source === 'web_search' ? '🌐 网络' : '🤖 AI推荐'}
            </span>
          )}
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg p-3 mt-2">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm font-medium text-gray-700">这个资源对你有帮助吗？</span>
            <button
              onClick={() => setShowFeedback(false)}
              className="text-gray-400 hover:text-gray-600"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex gap-2 mb-3">
            <button
              onClick={() => handleSubmit('useful')}
              disabled={submitting}
              className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ThumbsUp className="w-4 h-4" />}
              有用
            </button>
            <button
              onClick={() => handleSubmit('not_useful')}
              disabled={submitting}
              className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ThumbsDown className="w-4 h-4" />}
              不太有用
            </button>
          </div>

          <div className="mb-3">
            <span className="text-sm text-gray-600 mb-1 block">评分：</span>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHoverRating(star)}
                  onMouseLeave={() => setHoverRating(0)}
                  disabled={submitting}
                  className="p-0.5 disabled:cursor-not-allowed"
                >
                  <Star
                    className={`w-5 h-5 ${
                      (hoverRating || rating) >= star
                        ? 'fill-yellow-400 text-yellow-400'
                        : 'text-gray-300'
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>

          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="补充评价（可选）..."
            disabled={submitting}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none h-16 focus:outline-none focus:ring-2 focus:ring-blue-500/20 disabled:bg-gray-100"
          />

          {errorMessage && (
            <p className="mt-2 text-xs text-red-600">提交失败：{errorMessage}</p>
          )}
        </div>
      )}
    </div>
  );
}
