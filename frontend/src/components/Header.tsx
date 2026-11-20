// 顶栏：纯展示组件，不接收 props，也不读写全局状态。
/** 顶栏：站点名与一句说明；应用只有这一屏，所以没有导航链接。 */
export function Header() {
  return (
    <header className="topbar">
      <div className="shell topbar__inner">
        <h1 className="wordmark">
          <span className="wordmark__mark" aria-hidden="true" />
          学习规划助手
        </h1>
        <p className="topbar__note">一句话说清目标，四个智能体给出需求、规划、资源与评估</p>
      </div>
    </header>
  );
}
