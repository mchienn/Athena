import { forwardRef } from 'react';
import {
  CalendarDays,
  Cake,
  Clock3,
  CreditCard,
  HeartPulse,
  House,
  MapPin,
  MapPinned,
  Phone,
  Stethoscope,
  UserRound,
  UsersRound,
} from 'lucide-react';
import type { Appointment } from '../../../types';
import styles from './AppointmentReceipt.module.css';

function genderLabel(value?: string): string {
  if (value === 'male') return 'Nam';
  if (value === 'female') return 'Nữ';
  return value || 'Chưa cập nhật';
}

function shiftLabel(appointment: Appointment): string {
  if (appointment.shift === 'morning') return 'Buổi sáng';
  if (appointment.shift === 'afternoon') return 'Buổi chiều';
  return appointment.time;
}

export const AppointmentReceipt = forwardRef<HTMLDivElement, { appointment: Appointment }>(
  function AppointmentReceipt({ appointment }, ref) {
    return (
      <div className={styles.receipt} ref={ref}>
        <header className={styles.receiptHeader}>
          <img src="/logos/hanoi-heart-hospital.svg" alt="" width="58" height="58" />
          <div>
            <p>Bệnh viện Tim Hà Nội</p>
            <h2>Phiếu thông tin lịch khám</h2>
          </div>
          <HeartPulse aria-hidden="true" />
        </header>

        <div className={styles.codeRow}>
          <span>Mã đặt khám</span>
          <strong>{appointment.code}</strong>
        </div>

        <div className={styles.detailsGrid}>
          <article><CalendarDays /><span>Ngày khám</span><strong>{appointment.date}</strong></article>
          <article><Clock3 /><span>Buổi khám</span><strong>{shiftLabel(appointment)}</strong></article>
          <article><Stethoscope /><span>Bác sĩ</span><strong>{appointment.doctorName}</strong></article>
          <article><MapPin /><span>Địa điểm</span><strong>{appointment.facilityName}</strong></article>
          <article><Phone /><span>Số điện thoại hỗ trợ</span><strong>024 3942 2430</strong></article>
        </div>

        <section className={styles.patientSection}>
          <h3><UserRound /> Thông tin người khám</h3>
          <div className={styles.patientGrid}>
            <article><UserRound /><span>Họ tên</span><strong>{appointment.patientName}</strong></article>
            {appointment.patientCccd && (
              <article><CreditCard /><span>Số căn cước công dân</span><strong>{appointment.patientCccd}</strong></article>
            )}
            <article><Phone /><span>Số điện thoại</span><strong>{appointment.patientPhone || 'Chưa cập nhật'}</strong></article>
            <article><Cake /><span>Ngày sinh</span><strong>{appointment.patientDob || 'Chưa cập nhật'}</strong></article>
            <article><UsersRound /><span>Giới tính</span><strong>{genderLabel(appointment.patientGender)}</strong></article>
            <article className={styles.patientWide}><House /><span>Địa chỉ</span><strong>{appointment.patientAddress || 'Chưa cập nhật'}</strong></article>
            <article className={styles.patientWide}><MapPinned /><span>Quê quán</span><strong>{appointment.patientHometown || 'Chưa cập nhật'}</strong></article>
          </div>
        </section>

        {appointment.symptoms && (
          <section className={styles.symptomsSection}>
            <h3>Triệu chứng</h3>
            <p>{appointment.symptoms}</p>
          </section>
        )}

        <footer className={styles.receiptFooter}>
          <strong>Lưu ý khi đến khám</strong>
          <p>Vui lòng có mặt trước giờ hẹn 15 phút và mang theo giấy tờ tùy thân, thẻ BHYT nếu có.</p>
        </footer>
      </div>
    );
  },
);
