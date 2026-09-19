import { useDraggable } from '@dnd-kit/core'

export interface DragData {
  kind: 'dish'
  dishId: number
  dishName: string
  source?: { day: number; slot: string; line: string }
}

export function DraggableDish({ data, children, disabled, className = '',
                               onLockToggle }: {
  data: DragData
  children: React.ReactNode
  disabled?: boolean
  className?: string
  onLockToggle?: () => void
}) {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({ id: `dish-${data.dishId}-${data.source?.day ?? 'palette'}-${data.source?.slot ?? ''}-${data.source?.line ?? ''}`,
                  data, disabled })
  const style = transform
    ? { transform: `translate3d(${transform.x}px,${transform.y}px,0)`,
        zIndex: 999, opacity: isDragging ? 0.8 : 1 }
    : undefined
  return (
    <div ref={setNodeRef} style={style}
         className={`dish-card ${className}`}
         {...attributes}
         {...listeners}>
      {children}
    </div>
  )
}
