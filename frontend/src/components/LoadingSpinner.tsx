// 加载态占位：请求进行中时替换结果区，避免用户以为页面卡死。
import { Loader2 } from 'lucide-react';

/**
 * 转圈动画 + 一句提示。
 *
 * 这里没有进度百分比：后端是一次性返回，无法给出真实进度，
 * 写死一个「70%」反而是误导，所以只表达「正在处理」。
 */
export function LoadingSpinner() {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="relative">
        <Loader2 className="w-12 h-12 text-primary-500 animate-spin" />
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="w-4 h-4 bg-primary-100 rounded-full" />
        </div>
      </div>
      <p className="mt-4 text-gray-500">智能体正在分析您的需求...</p>
    </div>
  );
}
