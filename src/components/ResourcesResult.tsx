import { Video, FileText, Code, BookOpen, ExternalLink } from 'lucide-react';
import type { ResourcesData } from '../types';

interface ResourcesResultProps {
  data: ResourcesData;
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

export function ResourcesResult({ data }: ResourcesResultProps) {
  return (
    <div className="space-y-4">
      {data.resources.map((resource, index) => (
        <div
          key={index}
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
                <span className={`text-xs px-2 py-1 rounded-full ${typeColors[resource.type] || 'bg-gray-100 text-gray-600'}`}>
                  {resource.type}
                </span>
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
        </div>
      ))}
    </div>
  );
}
