import { Video, FileText, Code, BookOpen, ExternalLink, Plus, Database, Globe, Bot } from 'lucide-react';
import type { ResourcesDataWithRag, Resource, FeedbackSubmission } from '../types';
import { ResourceFeedback } from './ResourceFeedback';

interface ResourcesResultProps {
  data: ResourcesDataWithRag;
  learningObjective: string;
  onFeedbackSubmit: (feedback: FeedbackSubmission) => void;
  onAddResource: () => void;
}

const typeIcons: Record<string, React.ReactNode> = {
  '视频教程': <Video className="w-5 h-5" />,
  '文字教程': <FileText className="w-5 h-5" />,
  '实战项目': <Code className="w-5 h-5" />,
  '文档资料': <BookOpen className="w-5 h-5" />,
};

const typeColors: Record<string, string> = {
  '视频教程': 'bg-blue-50 text-blue-600',
  '文字教程': 'bg-green-50 text-green-600',
  '实战项目': 'bg-orange-50 text-orange-600',
  '文档资料': 'bg-purple-50 text-purple-600',
};

const sourceIcons: Record<string, React.ReactNode> = {
  'knowledge_base': <Database className="w-3.5 h-3.5" />,
  'web_search': <Globe className="w-3.5 h-3.5" />,
  'LLM生成': <Bot className="w-3.5 h-3.5" />,
};

const sourceLabels: Record<string, string> = {
  'knowledge_base': '知识库',
  'web_search': '网络搜索',
  'LLM生成': 'AI推荐',
};

export function ResourcesResult({ data, learningObjective, onFeedbackSubmit, onAddResource }: ResourcesResultProps) {
  const resources = data.resources || [];
  const ragInfo = data.rag_info;

  return (
    <div className="space-y-4">
      {ragInfo && (
        <div className="bg-gradient-to-r from-indigo-50 to-purple-50 rounded-xl p-3 mb-4">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-4">
              <span className="text-gray-600">
                <span className="font-medium text-indigo-600">检索来源：</span>
                {ragInfo.source_info || 'AI生成'}
              </span>
              <span className="text-gray-600">
                <span className="font-medium text-indigo-600">知识库匹配度：</span>
                {(ragInfo.kb_relevance * 100).toFixed(0)}%
              </span>
            </div>
            {ragInfo.used_web_search && (
              <span className="flex items-center gap-1 px-2 py-1 bg-orange-100 text-orange-700 rounded-full text-xs">
                <Globe className="w-3 h-3" />
                已联网搜索补充
              </span>
            )}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-gray-700">推荐资源（{resources.length}个）</h3>
        <button
          onClick={onAddResource}
          className="flex items-center gap-1 px-3 py-1.5 text-xs bg-indigo-100 hover:bg-indigo-200 text-indigo-700 rounded-lg transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          贡献新资源
        </button>
      </div>

      {resources.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <BookOpen className="w-12 h-12 mx-auto mb-2 opacity-50" />
          <p>暂无推荐资源</p>
        </div>
      ) : (
        resources.map((resource, index) => (
          <ResourceCard
            key={resource.id || index}
            resource={resource}
            index={index}
            learningObjective={learningObjective}
            onFeedbackSubmit={onFeedbackSubmit}
          />
        ))
      )}

      <div className="text-center mt-4 pt-3 border-t border-gray-100">
        <p className="text-xs text-gray-400">
          资源推荐基于AI智能检索，您的反馈将帮助优化推荐质量
        </p>
      </div>
    </div>
  );
}

interface ResourceCardProps {
  resource: Resource;
  index: number;
  learningObjective: string;
  onFeedbackSubmit: (feedback: FeedbackSubmission) => void;
}

function ResourceCard({ resource, index, learningObjective, onFeedbackSubmit }: ResourceCardProps) {
  return (
    <div
      className="bg-white rounded-xl p-4 border border-gray-100 hover:shadow-md transition-all duration-300"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 ${typeColors[resource.type] || 'bg-gray-50 text-gray-600'} rounded-lg flex items-center justify-center`}>
            {typeIcons[resource.type] || <BookOpen className="w-5 h-5" />}
          </div>
          <div>
            <a
              href={resource.url}
              target="_blank"
              rel="noopener noreferrer"
              className="font-semibold text-primary-600 hover:text-primary-700 hover:underline flex items-center gap-1"
            >
              {resource.title}
              <ExternalLink className="w-4 h-4" />
            </a>
            <div className="flex items-center gap-2 mt-1">
              <span className={`text-xs px-2 py-1 rounded-full ${typeColors[resource.type] || 'bg-gray-100 text-gray-600'}`}>
                {resource.type}
              </span>
              {resource.source && (
                <span className="text-xs px-2 py-1 rounded-full bg-gray-100 text-gray-600 flex items-center gap-1">
                  {sourceIcons[resource.source]}
                  {sourceLabels[resource.source] || resource.source}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="text-right">
          <p className="text-sm text-gray-500">难度：{resource.difficulty}</p>
          <p className="text-sm text-gray-500">时长：{resource.duration}</p>
        </div>
      </div>
      
      <p className="text-gray-600 text-sm mb-2">{resource.description}</p>
      <p className="text-sm">
        <span className="text-gray-500">推荐理由：</span>
        <span className="text-primary-600">{resource.recommendation_reason}</span>
      </p>
      <p className="text-xs text-gray-400 mt-2">适用阶段：{resource.phase}</p>

      <ResourceFeedback
        resource={resource}
        index={index}
        learningObjective={learningObjective}
        onSubmit={onFeedbackSubmit}
      />
    </div>
  );
}
