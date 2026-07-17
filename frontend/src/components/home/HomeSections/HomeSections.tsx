import {
  Activity,
  ArrowRight,
  Baby,
  Building2,
  ExternalLink,
  HeartPulse,
  MapPin,
  ScanLine,
  Stethoscope,
  Waves,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { doctorService } from '../../../services';
import { DoctorCard } from '../../common/DoctorCard';
import { StatePanel } from '../../common/StatePanel';
import styles from './HomeSections.module.css';

const specialtyIcons = [Activity, HeartPulse, Waves, Stethoscope, Baby, ScanLine];

const hospitalFacilities = [
  {
    id: 'cs1',
    label: 'Cơ sở 1',
    address: 'Số 92 Trần Hưng Đạo, phường Cửa Nam, Hà Nội',
    mapUrl: 'https://www.google.com/maps/search/?api=1&query=92+Trần+Hưng+Đạo+phường+Cửa+Nam+Hà+Nội',
  },
  {
    id: 'cs2',
    label: 'Cơ sở 2',
    address: 'Số 695 Lạc Long Quân, phường Tây Hồ, Hà Nội',
    mapUrl: 'https://www.google.com/maps/search/?api=1&query=695+Lạc+Long+Quân+phường+Tây+Hồ+Hà+Nội',
  },
];

export function HomeSections() {
  const doctors = useQuery({
    queryKey: ['doctors'],
    queryFn: () => doctorService.list(),
  });
  const specialties = useQuery({
    queryKey: ['specialties'],
    queryFn: doctorService.specialties,
  });

  return (
    <>
      <section className="section section-soft">
        <div className="container">
          <div className={styles.headingRow}>
            <div>
              <p className="section-eyebrow">Chuyên khoa</p>
              <h2 className="section-heading">Chăm sóc tim mạch toàn diện</h2>
              <p className="section-lead">
                Hệ thống chuyên khoa sâu phối hợp đa ngành, từ phòng ngừa đến can thiệp và phục hồi.
              </p>
            </div>
            <Link to="/chuyen-khoa">Xem tất cả <ArrowRight size={17} /></Link>
          </div>
          {specialties.isLoading ? (
            <StatePanel kind="loading" />
          ) : (
            <div className={styles.specialtyGrid}>
              {specialties.data?.map((item, index) => {
                const Icon = specialtyIcons[index];
                return (
                  <Link key={item.id} to={`/chuyen-khoa#${item.id}`}>
                    <span><Icon size={22} /></span>
                    <div>
                      <strong>{item.name}</strong>
                      <small>{item.description}</small>
                    </div>
                    <ArrowRight size={16} />
                  </Link>
                );
              })}
            </div>
          )}
        </div>
      </section>

      <section className="section">
        <div className="container">
          <div className={styles.headingRow}>
            <div>
              <p className="section-eyebrow">Đội ngũ y bác sĩ</p>
              <h2 className="section-heading">Chuyên gia tận tâm, giàu kinh nghiệm</h2>
            </div>
            <Link to="/bac-si">Tìm bác sĩ <ArrowRight size={17} /></Link>
          </div>
          {doctors.isLoading ? (
            <StatePanel kind="loading" />
          ) : (
            <div className={styles.doctorGrid}>
              {doctors.data?.slice(0, 4).map((doctor) => (
                <DoctorCard doctor={doctor} key={doctor.id} />
              ))}
            </div>
          )}
        </div>
      </section>

      <section className={styles.journey}>
        <div className="container">
          <p className="section-eyebrow">Quy trình đơn giản</p>
          <h2>Đặt lịch khám chỉ trong vài phút</h2>
          <div>
            {['Chọn cơ sở', 'Chọn bác sĩ phù hợp', 'Chọn ngày giờ còn trống', 'Nhận xác nhận lịch khám'].map(
              (item, index) => (
                <article key={item}>
                  <span>{index + 1}</span>
                  <strong>{item}</strong>
                </article>
              ),
            )}
          </div>
          <Link to="/dat-lich">Đặt lịch ngay <ArrowRight size={17} /></Link>
        </div>
      </section>

      <section className={`section section-soft ${styles.facilitiesSection}`}>
        <div className="container">
          <p className="section-eyebrow">Hệ thống cơ sở</p>
          <h2 className="section-heading">Thuận tiện thăm khám tại Hà Nội</h2>
          <div className={styles.facilityGrid}>
            {hospitalFacilities.map((facility) => (
              <article key={facility.id} className={styles.facilityCard}>
                <div className={styles.facilityImage} aria-label={`Vị trí ảnh ${facility.label}`}>
                  <Building2 size={48} aria-hidden="true" />
                  <span>Hình ảnh {facility.label}</span>
                </div>
                <div className={styles.facilityContent}>
                  <span className={styles.facilityLabel}>{facility.label}</span>
                  <h3>Bệnh viện Tim Hà Nội</h3>
                  <p><MapPin size={19} /> <span>{facility.address}</span></p>
                  <a href={facility.mapUrl} target="_blank" rel="noreferrer">
                    Xem trên bản đồ <ExternalLink size={15} />
                  </a>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>
    </>
  );
}
