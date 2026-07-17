import { BookingChat } from '../../components/assistant/BookingChat';
import { BookingFlow } from '../../components/booking/BookingFlow';
import { PageHero } from '../../components/common/PageHero';
import styles from './BookingPage.module.css';

export function BookingPage() {
  return (
    <>
      <PageHero
        simple
        title="Đặt lịch khám"
        description="Điền thông tin đặt lịch và trao đổi trực tiếp với trợ lý nếu bạn cần hỗ trợ lựa chọn chuyên khoa hoặc bác sĩ."
      />
      <section className={styles.section}>
        <div className={`container ${styles.workspace}`}>
          <div className={styles.formPane}>
            <BookingFlow />
          </div>
          <div className={styles.chatPane}>
            <BookingChat />
          </div>
        </div>
      </section>
    </>
  );
}
