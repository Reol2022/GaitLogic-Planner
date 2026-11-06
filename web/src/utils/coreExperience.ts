/** UX preferences only. JWT claims here are never used for authorization. */
export function preferenceKey(token: string | null, feature: string): string | null {
  if (!token) return null;
  try {
    const part = token.split(".")[1];
    const payload = JSON.parse(atob(part.replace(/-/g, "+").replace(/_/g, "/")));
    const subject = String(payload.sub ?? "");
    if (!/^[\w-]{1,80}$/.test(subject)) return null;
    return `gaitlogic:experience:${subject}:${feature}`;
  } catch { return null; }
}

export function localDate(value = new Date()): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

export type CoachTopic = "today" | "recent" | "week" | "plan";
export function coachEntry(topic: CoachTopic, date?: string) {
  return { path: "/coach", query: { topic, ...(date ? { date } : {}) } };
}
export function coachEntryPrompt(topic: unknown, date: unknown): string | null {
  const day = typeof date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null;
  const prompts: Record<CoachTopic, string> = {
    today: `请读取${day ? `${day}的` : "今天的"}训练计划，解释训练目的及需要注意的事项。`,
    recent: "请读取最近7天的实际训练，分析执行情况，区分计划、已关联记录和缺失数据。",
    week: `请复盘${day ? `${day}所在周` : "本周"}的计划与实际训练，指出关键发现与不确定性，暂不修改计划。`,
    plan: "请读取当前有效训练计划，讨论接下来的安排；只提供分析，不修改正式计划。",
  };
  return typeof topic === "string" && Object.prototype.hasOwnProperty.call(prompts, topic) ? prompts[topic as CoachTopic] : null;
}

export function syncNextStep(status: string, errorCode?: string | null): string {
  if (status === "queued") return "任务已排队，尚未开始读取活动。若长时间未开始，可取消后再操作。";
  if (status === "running") return "正在同步。数量以已返回结果为准，不代表全部活动已提交。";
  if (status === "succeeded") return "同步已完成。请确认活动关联，再补充主观感受；没有新增活动也可能是正常结果。";
  if (status === "partially_succeeded") return "部分数据已提交。先查看待确认活动和错误详情，不要重复导入已成功记录。";
  if (status === "cancelled") return "任务已取消。已提交的数据以实际记录为准。";
  if (["TOKEN_DECRYPTION_FAILED", "REAUTHENTICATION_REQUIRED", "AUTHENTICATION_REQUIRED"].includes(errorCode || "")) return "连接需要重新认证，请先断开并重新连接 Garmin。";
  if (["RATE_LIMITED", "PROVIDER_ACCESS_DENIED_COOLDOWN"].includes(errorCode || "")) return "设备平台正在限制访问，请按服务端提示等待，不要频繁重试。";
  return "同步未完成。请查看错误提示，再手动重试；重试不会自动表示成功。";
}
