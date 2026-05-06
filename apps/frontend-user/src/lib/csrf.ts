export function getCsrfToken(): string {
  const match = /(?:^|;\s*)csrf=([^;]+)/.exec(document.cookie);
  return match ? decodeURIComponent(match[1]) : "";
}
