// 加载态占位：请求进行中时替换结果区，避免用户以为页面卡死。
/**
 * 骨架 + 一句提示。
 *
 * 这里没有进度百分比：后端是一次性返回，无法给出真实进度，
 * 写死一个「70%」反而是误导，所以只表达「正在处理」。
 */
export function LoadingSpinner() {
  return (
    <div className="skeleton" role="status" aria-live="polite">
      <p className="skeleton__status">四个智能体正在分析你的需求，通常需要十几秒。</p>
      <div className="skeleton__bar skeleton__bar--head" aria-hidden="true" />
      <div className="skeleton__bar skeleton__bar--wide" aria-hidden="true" />
      <div className="skeleton__bar skeleton__bar--narrow" aria-hidden="true" />
      <div className="skeleton__bar skeleton__bar--wide" aria-hidden="true" />
    </div>
  );
}
