// 课程规划结果：可行性 / 预估周期两条概要 + 分阶段学习路径。
import type { PlanData } from '../types';

interface PlanResultProps {
  /** 课程规划 Agent 的输出：可行性判断、总时长、阶段列表 */
  data: PlanData;
}

/**
 * 学习路径展示。
 *
 * 阶段顺序完全按后端返回的数组顺序渲染，前端不重排：
 * 阶段之间存在先后依赖，重排会把学习顺序打乱。
 * 序号由真实的有序列表给出，视觉上的两位数只是这个序列的写法。
 */
export function PlanResult({ data }: PlanResultProps) {
  // 预估周期常写成「6个月（约360小时）」：括号里是对时长的换算，排成小一号的注，正文只留那个数字
  const duration = data.estimated_duration || '';
  const cut = duration.search(/[（(]/);
  const durationHead = cut > 0 ? duration.slice(0, cut).trim() : duration;
  const durationNote = cut > 0 ? duration.slice(cut).trim() : '';

  return (
    <div className="plan">
      <dl className="plan__figures">
        <div className="plan__figure">
          <dt className="plan__label">目标可行性</dt>
          <dd className="plan__value">{data.goal_feasibility}</dd>
        </div>
        <div className="plan__figure">
          <dt className="plan__label">预估周期</dt>
          <dd className="plan__duration">
            {durationHead}
            {durationNote && <span className="plan__detail">{durationNote}</span>}
          </dd>
        </div>
      </dl>

      <ol className="stages">
        {data.learning_path.stages.map((stage, index) => (
          <li className="stage" key={index}>
            <h3 className="stage__name">{stage.stage_name}</h3>
            <p className="stage__time">{stage.time_allocation}</p>
            <p className="stage__line">
              <span className="stage__key">学习内容</span>
              {stage.study_content}
            </p>
            <p className="stage__line">
              <span className="stage__key">阶段目标</span>
              <span className="stage__goal">{stage.milestone}</span>
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}
