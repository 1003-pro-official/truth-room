import type { ReactNode } from 'react'

type Props = {
  title?: string
  wide?: boolean
  alert?: boolean
  dismissible?: boolean
  onClose?: () => void
  children: ReactNode
}

export function Modal({
  title,
  wide,
  alert,
  dismissible = true,
  onClose,
  children,
}: Props) {
  return (
    <div className="modal-root" role="presentation" onClick={dismissible ? onClose : undefined}>
      <div
        className={`modal-card${wide ? ' wide' : ''}${alert ? ' alert' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={title || 'dialog'}
        onClick={(e) => e.stopPropagation()}
      >
        {dismissible && onClose ? (
          <button type="button" className="modal-close" aria-label="Close" onClick={onClose}>
            ×
          </button>
        ) : null}
        {title ? <h2 className="modal-title">{title}</h2> : null}
        {children}
      </div>
    </div>
  )
}
