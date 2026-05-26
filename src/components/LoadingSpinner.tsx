import { Loader2 } from 'lucide-react';

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
