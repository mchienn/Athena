import { CalendarDays, CheckCircle2 } from 'lucide-react';
import { Link } from 'react-router-dom';
import styles from './BookingConfirmationPage.module.css';

export function BookingConfirmationPage() {
  return (
    <section className={styles.page}>
      <div className={`container ${styles.successCard}`}>
        <CheckCircle2 aria-hidden="true" />
        <h1>Đặt lịch thành công</h1>
        <Link to="/lich-kham">
          <CalendarDays />
          Xem lịch khám
        </Link>
      </div>
    </section>
  );
}
