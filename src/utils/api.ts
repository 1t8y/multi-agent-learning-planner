import type { PlanResponse } from '../types';

// 生产环境(Vercel): API 与前端同域，使用相对路径
// 开发环境: 连接本地后端
const API_BASE_URL = import.meta.env.MODE === 'production' ? '' : 'http://localhost:8000';

export async function generateLearningPlan(userInput: string): Promise<PlanResponse> {
  const response = await fetch(`${API_BASE_URL}/api/plan`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ userInput }),
  });

  if (!response.ok) {
    throw new Error('生成学习规划失败');
  }

  return response.json();
}

export function getMockPlanResponse(): PlanResponse {
  return {
    requirement_data: {
      learning_objective: '学习Python编程',
      current_foundation: '零基础',
      daily_available_time: '2小时',
      learning_preference: '视频',
      time_expectation: '快速入门',
    },
    plan: {
      goal_feasibility: '目标可行，适合一周内快速入门',
      estimated_duration: '约1周',
      learning_path: {
        stage_count: 2,
        stages: [
          {
            stage_name: '第一阶段：快速入门',
            study_content: 'Python基础语法、数据类型（列表、字典）、基本控制流程（if-else、for循环）',
            time_allocation: '4天',
            milestone: '能够编写简单的Python程序，理解变量和基本数据结构',
          },
          {
            stage_name: '第二阶段：实战演练',
            study_content: '函数定义与调用、常用内置函数、简单项目实战',
            time_allocation: '3天',
            milestone: '能够完成简单的自动化脚本，如文件处理、数据统计',
          },
        ],
      },
    },
    resources: {
      resources: [
        {
          phase: '第一阶段：快速入门',
          type: '视频教程',
          title: 'Python快速入门7天精通',
          description: '7天学会Python基础，适合零基础快速上手',
          duration: '14小时',
          difficulty: '入门',
          recommendation_reason: '内容紧凑，适合短期快速学习',
          url: 'https://www.bilibili.com/video/BV1wD4y1o7AS/',
        },
        {
          phase: '第一阶段：快速入门',
          type: '文字教程',
          title: 'Python简明教程',
          description: '简洁的Python入门指南，重点突出',
          duration: '3小时',
          difficulty: '入门',
          recommendation_reason: '快速掌握核心概念',
          url: 'https://docs.python.org/3/tutorial/introduction.html',
        },
        {
          phase: '第二阶段：实战演练',
          type: '实战项目',
          title: 'Python一日一练',
          description: '7个简单实用的Python小项目',
          duration: '7小时',
          difficulty: '入门',
          recommendation_reason: '边学边练，快速上手',
          url: 'https://github.com/knausj85/knausj_talon',
        },
      ],
    },
    assessment: {
      assessment_summary: {
        overall_rating: '优秀',
        feasibility_rating: 9,
        content_rating: 8,
        time_rating: 8,
        method_rating: 9,
      },
      assessment_metrics: [
        {
          phase: '第一阶段',
          metrics: [
            {
              name: '进度完成率',
              description: '每周学习任务完成情况',
              target_value: '90%以上',
              measurement_method: '每周检查学习进度',
            },
            {
              name: '知识点掌握',
              description: '核心概念理解程度',
              target_value: '85分以上',
              measurement_method: '章节测验',
            },
          ],
        },
        {
          phase: '第二阶段',
          metrics: [
            {
              name: '代码质量',
              description: '代码规范性和可读性',
              target_value: '良好',
              measurement_method: '代码审查',
            },
            {
              name: '项目完成度',
              description: '实战项目完成情况',
              target_value: '100%',
              measurement_method: '项目验收',
            },
          ],
        },
      ],
      adjustment_suggestions: [
        {
          area: '时间安排',
          issue: '周末学习时间可以适当增加',
          suggestion: '建议周末每天学习3-4小时',
          priority: '中',
        },
        {
          area: '实践练习',
          issue: '理论学习与实践结合不够',
          suggestion: '每学完一个知识点立即进行练习',
          priority: '高',
        },
      ],
      recommendations: [
        '建议每周进行一次小测验检验学习效果',
        '加入学习社群与其他学习者交流',
        '定期回顾复习已学知识',
      ],
    },
  };
}
