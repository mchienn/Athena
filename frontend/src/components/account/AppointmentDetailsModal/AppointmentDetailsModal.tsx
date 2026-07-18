import { useEffect, useRef, useState } from 'react';
import { Download, X } from 'lucide-react';
import type { Appointment } from '../../../types';
import { downloadAppointmentPdf } from '../../../utils/downloadAppointmentPdf';
import { AppointmentReceipt } from '../AppointmentReceipt';
import styles from './AppointmentDetailsModal.module.css';

interface AppointmentDetailsModalProps {
  appointment: Appointment;
  onClose: () => void;
}

export function AppointmentDetailsModal({
  appointment,
  onClose,
}: AppointmentDetailsModalProps) {
  const receiptRef = useRef<HTMLDivElement>(null);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [onClose]);

  const downloadPdf = async () => {
    if (!receiptRef.current || downloading) return;
    setDownloading(true);
    try {
      await downloadAppointmentPdf(receiptRef.current, appointment.code);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div
      className={styles.overlay}
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className={styles.dialog}
        role="dialog"
        aria-modal="true"
        aria-label="Phiếu thông tin lịch khám"
      >
        <button className={styles.closeButton} type="button" onClick={onClose} aria-label="Đóng">
          <X />
        </button>

        <AppointmentReceipt appointment={appointment} ref={receiptRef} />

        <div className={styles.actions}>
          <button type="button" onClick={() => void downloadPdf()} disabled={downloading}>
            <Download /> {downloading ? 'Đang tạo PDF...' : 'Tải xuống'}
          </button>
          <button type="button" onClick={onClose}>Đóng</button>
        </div>
      </section>
    </div>
  );
}
