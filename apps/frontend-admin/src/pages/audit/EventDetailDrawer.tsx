import { Dialog } from "@novelgen/ui";
import { JsonViewer } from "../../components/JsonViewer";

interface Props {
  event: {
    event_id: string;
    timestamp: string;
    actor_email: string;
    action: string;
    resource_type: string;
    resource_id: string;
    details: Record<string, unknown>;
  };
  onClose(): void;
}

export function EventDetailDrawer({ event, onClose }: Props) {
  return (
    <Dialog
      open
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={`审计事件 ${event.event_id.slice(0, 8)}`}
      description={`${event.action} · ${event.resource_type} · ${event.actor_email}`}
    >
      <div className="space-y-3 text-sm">
        <div>
          <span className="text-xs text-muted-foreground">时间：</span>
          <span>{new Date(event.timestamp).toLocaleString()}</span>
        </div>
        <div>
          <span className="text-xs text-muted-foreground">Resource ID：</span>
          <code className="text-xs">{event.resource_id}</code>
        </div>
        <div>
          <p className="mb-1 text-xs text-muted-foreground">details（原文）</p>
          <JsonViewer value={event.details} />
        </div>
      </div>
    </Dialog>
  );
}
