import { useEffect, useMemo, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { CalendarCheck, Check, LoaderCircle, ShieldCheck, WifiOff } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { appointmentService, doctorService, scheduleService } from '../../../services';
import { useBooking } from '../../../hooks/useBooking';
import type { BookingData } from '../../../types';
import { StatePanel } from '../../common/StatePanel';
import styles from './BookingFlow.module.css';

const bookingSchema = z.object({
  patientName: z.string().trim().min(2, 'Vui lòng nhập họ tên'),
  patientPhone: z
    .string()
    .trim()
    .regex(/^(0|\+84)\d{9}$/, 'Số điện thoại không hợp lệ'),
  patientEmail: z.union([z.literal(''), z.email('Email không hợp lệ')]),
  patientDob: z.string().min(1, 'Vui lòng chọn ngày sinh'),
  patientGender: z.enum(['male', 'female'], {
    message: 'Vui lòng chọn giới tính',
  }),
  symptoms: z.string().max(500, 'Nội dung tối đa 500 ký tự'),
  facilityId: z.string().min(1, 'Vui lòng chọn cơ sở'),
  specialtyId: z.string().min(1, 'Vui lòng chọn chuyên khoa'),
  doctorId: z.string(),
  date: z.string().min(1, 'Vui lòng chọn ngày khám'),
  time: z.string().min(1, 'Vui lòng chọn giờ khám'),
  confirmed: z.boolean().refine((value) => value, {
    message: 'Bạn cần xác nhận thông tin trước khi đặt lịch',
  }),
});

type BookingFormValues = z.infer<typeof bookingSchema>;

export function BookingFlow() {
  const booking = useBooking();
  const navigate = useNavigate();
  const [submitError, setSubmitError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const facilities = useQuery({
    queryKey: ['facilities'],
    queryFn: scheduleService.facilities,
  });
  const specialties = useQuery({
    queryKey: ['specialties'],
    queryFn: doctorService.specialties,
  });
  const doctors = useQuery({
    queryKey: ['doctors'],
    queryFn: () => doctorService.list(),
  });

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    formState: { errors },
  } = useForm<BookingFormValues>({
    resolver: zodResolver(bookingSchema),
    mode: 'onSubmit',
    reValidateMode: 'onChange',
    defaultValues: {
      patientName: booking.data.patientName,
      patientPhone: booking.data.patientPhone,
      patientEmail: booking.data.patientEmail,
      patientDob: booking.data.patientDob,
      patientGender:
        booking.data.patientGender === 'male' || booking.data.patientGender === 'female'
          ? booking.data.patientGender
          : undefined,
      symptoms: booking.data.symptoms,
      facilityId: booking.data.facilityId,
      specialtyId: booking.data.specialtyId,
      doctorId: booking.data.doctorId,
      date: booking.data.date,
      time: booking.data.time,
      confirmed: false,
    },
  });

  const selectedFacility = watch('facilityId');
  const selectedSpecialty = watch('specialtyId');
  const selectedDoctor = watch('doctorId');
  const selectedDate = watch('date');

  const schedules = useQuery({
    queryKey: ['schedule', selectedDoctor],
    queryFn: () => scheduleService.list(selectedDoctor),
  });

  const availableDoctors = useMemo(
    () =>
      doctors.data?.filter(
        (doctor) =>
          (!selectedFacility || doctor.facilityId === selectedFacility) &&
          (!selectedSpecialty || doctor.specialtyId === selectedSpecialty),
      ) ?? [],
    [doctors.data, selectedFacility, selectedSpecialty],
  );

  const selectedSchedule = schedules.data?.find((day) => day.date === selectedDate);

  useEffect(() => {
    const subscription = watch((values) => {
      booking.update({
        patientName: values.patientName ?? '',
        patientPhone: values.patientPhone ?? '',
        patientEmail: values.patientEmail ?? '',
        patientDob: values.patientDob ?? '',
        patientGender: values.patientGender ?? '',
        symptoms: values.symptoms ?? '',
        facilityId: values.facilityId ?? '',
        specialtyId: values.specialtyId ?? '',
        doctorId: values.doctorId ?? '',
        date: values.date ?? '',
        time: values.time ?? '',
      });
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [booking.update, watch]);

  const submitBooking = async (values: BookingFormValues) => {
    setSubmitting(true);
    setSubmitError('');

    const payload: BookingData = {
      patientName: values.patientName,
      patientPhone: values.patientPhone,
      patientEmail: values.patientEmail,
      patientDob: values.patientDob,
      patientGender: values.patientGender,
      symptoms: values.symptoms,
      facilityId: values.facilityId,
      specialtyId: values.specialtyId,
      doctorId: values.doctorId,
      date: values.date,
      time: values.time,
    };

    try {
      const appointment = await appointmentService.create(payload);
      booking.reset();
      navigate('/dat-lich/xac-nhan', { state: { appointment } });
    } catch {
      setSubmitError(
        'Khung giờ có thể vừa được đặt hoặc kết nối bị gián đoạn. Vui lòng kiểm tra và thử lại.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  if (facilities.isLoading || specialties.isLoading || doctors.isLoading) {
    return <StatePanel kind="loading" title="Đang chuẩn bị biểu mẫu đặt lịch" />;
  }

  if (facilities.isError || specialties.isError || doctors.isError) {
    return (
      <StatePanel
        kind="offline"
        title="Không thể tải dữ liệu đặt lịch"
        onRetry={() => {
          void facilities.refetch();
          void specialties.refetch();
          void doctors.refetch();
        }}
      />
    );
  }

  return (
    <form
      className={styles.form}
      onSubmit={(event) => void handleSubmit(submitBooking)(event)}
    >
      <header className={styles.formHeader}>
        <span><CalendarCheck size={22} /></span>
        <div>
          <h2>Thông tin đặt lịch</h2>
          <p>Điền đầy đủ thông tin để bệnh viện tiếp nhận lịch khám.</p>
        </div>
      </header>

      <div className={styles.formContent}>
        <fieldset className={styles.section}>
          <legend>Thông tin người khám</legend>
          <label className={styles.fullWidth}>
            <span className={styles.labelText}>Họ và tên <em className={styles.required}>*</em></span>
            <input {...register('patientName')} placeholder="Nguyễn Văn A" />
            {errors.patientName && <small>{errors.patientName.message}</small>}
          </label>

          <div className={styles.twoColumns}>
            <label>
              <span className={styles.labelText}>Số điện thoại <em className={styles.required}>*</em></span>
              <input
                {...register('patientPhone', {
                  setValueAs: (value: string) => value.replace(/\s/g, ''),
                })}
                inputMode="tel"
                placeholder="0912 345 678"
              />
              {errors.patientPhone && <small>{errors.patientPhone.message}</small>}
            </label>
            <label>
              Email
              <input {...register('patientEmail')} type="email" placeholder="email@example.com" />
              {errors.patientEmail && <small>{errors.patientEmail.message}</small>}
            </label>
          </div>

          <div className={styles.twoColumns}>
            <label>
              <span className={styles.labelText}>Ngày sinh <em className={styles.required}>*</em></span>
              <input {...register('patientDob')} type="date" />
              {errors.patientDob && <small>{errors.patientDob.message}</small>}
            </label>
            <div className={styles.genderGroup}>
              <span>Giới tính *</span>
              <div>
                <label><input {...register('patientGender')} type="radio" value="male" /> Nam</label>
                <label><input {...register('patientGender')} type="radio" value="female" /> Nữ</label>
              </div>
              {errors.patientGender && <small>{errors.patientGender.message}</small>}
            </div>
          </div>

          <label className={styles.fullWidth}>
            Triệu chứng hoặc yêu cầu
            <textarea
              {...register('symptoms')}
              rows={3}
              placeholder="Mô tả ngắn triệu chứng hoặc yêu cầu hỗ trợ..."
            />
            {errors.symptoms && <small>{errors.symptoms.message}</small>}
          </label>
        </fieldset>

        <fieldset className={styles.section}>
          <legend>Thông tin lịch khám</legend>
          <label>
            <span className={styles.labelText}>Cơ sở khám <em className={styles.required}>*</em></span>
            <select
              {...register('facilityId', {
                onChange: () => {
                  setValue('doctorId', '');
                  setValue('time', '');
                },
              })}
            >
              <option value="">Chọn cơ sở</option>
              {facilities.data?.map((facility) => (
                <option key={facility.id} value={facility.id}>{facility.shortName}</option>
              ))}
            </select>
            {errors.facilityId && <small>{errors.facilityId.message}</small>}
          </label>

          <label>
            <span className={styles.labelText}>Chuyên khoa</span>
            <select
              {...register('specialtyId', {
                onChange: () => {
                  setValue('doctorId', '');
                  setValue('time', '');
                },
              })}
            >
              <option value="">Chọn chuyên khoa</option>
              {specialties.data?.map((specialty) => (
                <option key={specialty.id} value={specialty.id}>{specialty.name}</option>
              ))}
            </select>
            {errors.specialtyId && <small>{errors.specialtyId.message}</small>}
          </label>

          <label>
            Bác sĩ
            <select {...register('doctorId')} disabled={!selectedFacility || !selectedSpecialty}>
              <option value="">Bác sĩ phù hợp sớm nhất</option>
              {availableDoctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.title} {doctor.name}
                </option>
              ))}
            </select>
          </label>

          <div className={styles.twoColumns}>
            <label>
              <span className={styles.labelText}>Ngày khám <em className={styles.required}>*</em></span>
              <select
                {...register('date', {
                  onChange: () => setValue('time', ''),
                })}
              >
                <option value="">Chọn thứ / ngày</option>
                {schedules.data?.map((day) => (
                  <option key={day.date} value={day.date}>{day.label}</option>
                ))}
              </select>
              {errors.date && <small>{errors.date.message}</small>}
            </label>
            <label>
              <span className={styles.labelText}>Giờ khám <em className={styles.required}>*</em></span>
              <select {...register('time')} disabled={!selectedSchedule}>
                <option value="">Chọn giờ</option>
                {selectedSchedule?.slots.map((slot) => (
                  <option
                    key={slot.id}
                    value={slot.status === 'available' ? slot.time : ''}
                    disabled={slot.status !== 'available'}
                  >
                    {slot.time} — {slot.status === 'available' ? 'Còn chỗ' : 'Hết lịch'}
                  </option>
                ))}
              </select>
              {errors.time && <small>{errors.time.message}</small>}
            </label>
          </div>
        </fieldset>

        <div className={styles.confirmation}>
          <ShieldCheck size={20} />
          <label>
            <input {...register('confirmed')} type="checkbox" />
            <span>Tôi xác nhận các thông tin đã cung cấp là chính xác.</span>
          </label>
        </div>
        {errors.confirmed && <small className={styles.confirmationError}>{errors.confirmed.message}</small>}

        {submitError && (
          <div className={styles.submitError} role="alert">
            <WifiOff size={18} /> {submitError}
          </div>
        )}

        <button className={styles.submitButton} type="submit" disabled={submitting}>
          {submitting ? (
            <><LoaderCircle className={styles.spin} size={18} /> Đang đặt lịch...</>
          ) : (
            <>Đặt lịch <Check size={18} /></>
          )}
        </button>
      </div>
    </form>
  );
}
