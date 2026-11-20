// 结果区通用区块：一条上墨线、一个标题、一段正文，内容由调用方通过 children 传入。
import { ReactNode } from 'react';

interface ResultCardProps {
  /** 区块标题，例如「需求分析」「课程规划」 */
  title: string;
  /** 标题右侧的补充事实或一个次要动作，没有就不渲染 */
  aside?: ReactNode;
  /** 区块正文内容 */
  children: ReactNode;
}

/**
 * 区块骨架。
 *
 * 只负责版式，不做任何数据裁剪：内容为空时由调用方决定怎么提示。
 * 结果区不用卡片围栏，四个区块靠一条墨线和一个标题分开，读起来是一份记录。
 */
export function ResultCard({ title, aside, children }: ResultCardProps) {
  return (
    <section className="section">
      <div className="section__head">
        <h2 className="section__title">{title}</h2>
        {aside && <div className="section__tools">{aside}</div>}
      </div>
      {children}
    </section>
  );
}
