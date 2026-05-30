import { useState } from 'react';
import { ThumbsUp, ThumbsDown, Star, X, Check } from 'lucide-react';
import type { Resource, FeedbackSubmission } from '../types';

interface ResourceFeedbackProps {
  resource: Resource;
  index: number;
  learningObjective: string;
  onSubmit: (feedback: FeedbackSubmission) => void;
}

export function ResourceFeedback({ resource, index, learningObjective, onSubmit }: ResourceFeedbackProps) {
  const [showFeedback, setShowFeedback] = useState(false);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [comment, setComment] = useState('');
  const [feedbackType, setFeedbackType] = useState<'useful' | 'not_useful' | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (type: 'useful' | 'not_useful') => {
    if (rating === 0) {
      alert('请选择评分');
      return;
    }

    const feedback: FeedbackSubmission = {
      resource_id: resource.id || `resource_${index}`,
      resource_title: resource.title,
      resource_url: resource.url,
      feedback_type: type,
      rating: rating,
      comment: comment,
      learning_objective: learningObjective
    };

    onSubmit(feedback);
    setFeedbackType(type);
    setSubmitted(true);
    setShowFeedback(false);
  };

  if (submitted) {
    return (
      <div className="flex items-center gap-2 mt-3 text-sm">
        <Check className="w-4 h-4 text-green-500" />
        <span className="text-green-600">
          感谢反馈！已记录为{feedbackType === 'useful' ? '有用' : '不太有用'}
        </span>
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
              className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-green-100 hover:bg-green-200 text-green-700 rounded-lg transition-colors"
            >
              <ThumbsUp className="w-4 h-4" />
              有用
            </button>
            <button
              onClick={() => handleSubmit('not_useful')}
              className="flex-1 flex items-center justify-center gap-1 px-3 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg transition-colors"
            >
              <ThumbsDown className="w-4 h-4" />
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
                  className="p-0.5"
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
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg resize-none h-16 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          />
        </div>
      )}
    </div>
  );
}
