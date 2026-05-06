interface JsonViewerProps {
  value: unknown;
  maxHeight?: number;
}

export function JsonViewer({ value, maxHeight = 400 }: JsonViewerProps) {
  const text = (() => {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  })();
  return (
    <pre
      className="rounded-md bg-muted/50 p-3 text-xs leading-relaxed"
      style={{ maxHeight, overflow: "auto" }}
    >
      <code>{text}</code>
    </pre>
  );
}
