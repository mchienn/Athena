import { useQuery } from '@tanstack/react-query';
import { Stethoscope, Calendar, ClipboardList, Pill, UserRound, ArrowRight } from 'lucide-react';
import { AccountLayout } from '../../components/account/AccountLayout';
import { authService } from '../../services';
import styles from './MedicalHistoryPage.module.css';

interface PrescriptionItem {
  medicine_name: string;
  dosage: string;
  quantity: number;
}

interface MedicalRecord {
  record_id: string;
  patient_id: string;
  visit_date: string;
  department: string;
  doctor_name: string;
  diagnosis: string;
  symptoms: string;
  treatment_plan: string;
  prescription: PrescriptionItem[];
  next_appointment_date?: string;
  created_at: string;
}

export function MedicalHistoryPage() {
  const { data: records, isLoading, error } = useQuery<MedicalRecord[]>({
    queryKey: ['medical_records'],
    queryFn: authService.getMedicalRecords,
  });

  if (isLoading) {
    return (
      <AccountLayout title="Hồ sơ sức khỏe">
        <p className={styles.loading}>Đang tải lịch sử khám bệnh...</p>
      </AccountLayout>
    );
  }

  if (error) {
    return (
      <AccountLayout title="Hồ sơ sức khỏe">
        <p className={styles.error}>Lỗi kết nối. Không thể tải hồ sơ sức khỏe lúc này.</p>
      </AccountLayout>
    );
  }

  return (
    <AccountLayout title="Hồ sơ sức khỏe">
      <div className={styles.container}>
        <p className={styles.description}>
          Lịch sử các lượt khám chữa bệnh và đơn thuốc đã kê tại Bệnh viện Tim Hà Nội.
        </p>

        {!records || records.length === 0 ? (
          <div className={styles.empty}>
            <ClipboardList size={48} />
            <h3>Chưa có lịch sử khám</h3>
            <p>Khi bạn hoàn thành các lượt khám tại bệnh viện, thông tin bệnh án sẽ xuất hiện ở đây.</p>
          </div>
        ) : (
          <div className={styles.timeline}>
            {records.map((record) => (
              <div key={record.record_id} className={styles.timelineItem}>
                <div className={styles.timelineMarker}>
                  <div className={styles.markerCircle}>
                    <Stethoscope size={18} />
                  </div>
                </div>
                <div className={styles.timelineContent}>
                  <div className={styles.cardHeader}>
                    <div className={styles.visitMeta}>
                      <span className={styles.date}>
                        <Calendar size={14} />
                        {record.visit_date}
                      </span>
                      <span className={styles.department}>{record.department}</span>
                    </div>
                    <span className={styles.doctor}>
                      <UserRound size={14} />
                      Bác sĩ: <strong>{record.doctor_name}</strong>
                    </span>
                  </div>

                  <div className={styles.cardBody}>
                    <div className={styles.detailsGrid}>
                      <div>
                        <strong>Triệu chứng lâm sàng:</strong>
                        <p>{record.symptoms || 'Không ghi nhận'}</p>
                      </div>
                      <div>
                        <strong>Chẩn đoán xác định:</strong>
                        <p className={styles.diagnosis}>{record.diagnosis}</p>
                      </div>
                    </div>

                    <div className={styles.treatment}>
                      <strong>Lời dặn & Kế hoạch điều trị:</strong>
                      <p>{record.treatment_plan || 'Theo dõi và uống thuốc theo đơn.'}</p>
                    </div>

                    {record.prescription && record.prescription.length > 0 && (
                      <div className={styles.prescription}>
                        <div className={styles.prescriptionHeader}>
                          <Pill size={14} />
                          <strong>Đơn thuốc được kê:</strong>
                        </div>
                        <table className={styles.prescriptionTable}>
                          <thead>
                            <tr>
                              <th>Tên thuốc</th>
                              <th>Liều dùng</th>
                              <th>SL</th>
                            </tr>
                          </thead>
                          <tbody>
                            {record.prescription.map((med, idx) => (
                              <tr key={idx}>
                                <td className={styles.medicineName}>{med.medicine_name}</td>
                                <td>{med.dosage}</td>
                                <td className={styles.quantity}>{med.quantity}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}

                    {record.next_appointment_date && (
                      <div className={styles.nextAppointment}>
                        <ArrowRight size={14} />
                        Hẹn tái khám vào ngày: <strong>{record.next_appointment_date}</strong>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </AccountLayout>
  );
}
export default MedicalHistoryPage;
