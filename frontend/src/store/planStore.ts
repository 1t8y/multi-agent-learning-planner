// 全局状态：输入内容、加载态、规划结果、错误信息。
// 只放跨组件共享的状态；组件内部的临时状态（弹窗开关等）留在组件里。
import { create } from 'zustand';
import type { PlanStore } from '../types';

/**
 * 学习规划页面的状态容器。
 *
 * 设计约束：请求失败时只写 error，不写 planResult。
 * 一旦这里被填入兜底的假数据，前端就无法区分「真的没结果」和「后端挂了」，
 * 回归探针 frontend/scripts/verify-api-errors.mjs 专门守这条线。
 */
export const usePlanStore = create<PlanStore>((set) => ({
  userInput: '',                                   // 用户当前输入的学习目标
  setUserInput: (input) => set({ userInput: input }),
  isLoading: false,                                // 是否正在请求 /api/plan
  setIsLoading: (loading) => set({ isLoading: loading }),
  planResult: null,                                // 后端返回的计划结果，未成功时为 null
  setPlanResult: (result) => set({ planResult: result }),
  error: null,                                     // 请求失败的原因，直接展示给用户
  setError: (error) => set({ error }),
}));
