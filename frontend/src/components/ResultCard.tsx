// 结果区通用卡片：统一标题栏样式，内容由调用方通过 children 传入。
import { ReactNode } from 'react';

interface ResultCardProps {
  /** 卡片标题，例如「学习需求」「学习路径」 */
  title: string;
  /** 标题栏左侧图标，直接传 lucide 图标元素 */
  icon: ReactNode;
  /** 标题栏背景色类名（Tailwind），不同模块用不同颜色区分 */
  color: string;
  /** 卡片正文内容 */
  children: ReactNode;
}

/**
 * 带彩色标题栏的内容卡片。
 *
 * 只负责版式，不做任何数据裁剪：内容为空时由调用方决定怎么提示。
 */
export function ResultCard({ title, icon, color, children }: ResultCardProps) {
  return (
    <div className="bg-white/10 backdrop-blur-sm rounded-lg shadow-lg overflow-hidden">
      <div className={`${color} px-4 py-3 flex items-center gap-2`}>
        {icon}
        <h3 className="text-lg font-semibold text-white">{title}</h3>
      </div>
      <div className="p-4 text-white/90">
        {children}
      </div>
    </div>
  );
}
