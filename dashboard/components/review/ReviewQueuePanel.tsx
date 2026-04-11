import { Table } from '../primitives/data_views'

export function ReviewQueuePanel({ items }: { items: Array<{ kind: string; reason: string }> }) {
  return <Table title='Review queue / checkpoints' rows={items.map((i) => [i.kind, i.reason])} />
}
