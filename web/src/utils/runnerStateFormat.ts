const EMPTY_VALUE = "暂无数据";

function isMissing(value: number | string | null | undefined): value is null | undefined | "" {
  return value === null || value === undefined || value === "";
}

export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (isMissing(value)) return EMPTY_VALUE;
  return Number(value).toFixed(digits).replace(/\.0+$/, "");
}

export function formatDistance(value: number | null | undefined): string {
  if (isMissing(value)) return EMPTY_VALUE;
  return `${formatNumber(value, 1)} km`;
}

export function formatMinutes(value: number | null | undefined): string {
  if (isMissing(value)) return EMPTY_VALUE;
  return `${formatNumber(value, 1)} 分钟`;
}

export function formatCount(value: number | null | undefined, unit = "次"): string {
  if (isMissing(value)) return EMPTY_VALUE;
  return `${value}${unit}`;
}

export function formatPercent(value: number | null | undefined): string {
  if (isMissing(value)) return EMPTY_VALUE;
  return `${formatNumber(value * 100, 1)}%`;
}

export function formatRatio(value: number | null | undefined): string {
  if (isMissing(value)) return EMPTY_VALUE;
  return `${Number(value).toFixed(2)}×`;
}

export function formatRpe(value: number | null | undefined): string {
  if (isMissing(value)) return EMPTY_VALUE;
  return formatNumber(value, 1);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return EMPTY_VALUE;
  const [datePart] = value.split("T");
  return datePart || EMPTY_VALUE;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return EMPTY_VALUE;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

export { EMPTY_VALUE };
