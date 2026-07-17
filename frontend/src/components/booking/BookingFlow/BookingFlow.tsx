import { useEffect, useMemo, useState } from 'react';
import { zodResolver } from '@hookform/resolvers/zod';
import { CalendarCheck, Check, LoaderCircle, ShieldCheck, WifiOff } from 'lucide-react';
import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { appointmentService, authService, doctorService, scheduleService } from '../../../services';
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
  patientDob: z.string().min(1, 'Vui lòng chọn ngày sinh'),
  patientGender: z.enum(['male', 'female'], {
    message: 'Vui lòng chọn giới tính',
  }),
  patientAddress: z.string().trim().min(5, 'Vui lòng nhập địa chỉ'),
  facilityId: z.string().min(1, 'Vui lòng chọn cơ sở'),
  doctorId: z.string().min(1, 'Vui lòng chọn bác sĩ'),
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
  const doctors = useQuery({
    queryKey: ['doctors'],
    queryFn: () => doctorService.list(),
  });
  const profile = useQuery({
    queryKey: ['patient_profile'],
    queryFn: authService.getDetailedProfile,
    enabled: authService.isAuthenticated(),
    retry: false,
  });

  const {
    register,
    handleSubmit,
    getValues,
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
      patientDob: booking.data.patientDob,
      patientGender:
        booking.data.patientGender === 'male' || booking.data.patientGender === 'female'
          ? booking.data.patientGender
          : undefined,
      patientAddress: booking.data.patientAddress,
      facilityId: booking.data.facilityId,
      doctorId: booking.data.doctorId,
      date: booking.data.date,
      time: booking.data.time,
      confirmed: false,
    },
  });

  const selectedFacility = watch('facilityId');
  const selectedDoctor = watch('doctorId');
  const selectedDate = watch('date');

  const schedules = useQuery({
    queryKey: ['schedule', selectedDoctor],
    queryFn: () => scheduleService.list(selectedDoctor),
  });

  const availableDoctors = useMemo(
    () =>
      doctors.data?.filter(
        (doctor) => !selectedFacility || doctor.facilityId === selectedFacility,
      ) ?? [],
    [doctors.data, selectedFacility],
  );

  const selectedSchedule = schedules.data?.find((day) => day.date === selectedDate);

  useEffect(() => {
    const subscription = watch((values) => {
      booking.update({
        patientName: values.patientName ?? '',
        patientPhone: values.patientPhone ?? '',
        patientDob: values.patientDob ?? '',
        patientGender: values.patientGender ?? '',
        patientAddress: values.patientAddress ?? '',
        facilityId: values.facilityId ?? '',
        doctorId: values.doctorId ?? '',
        date: values.date ?? '',
        time: values.time ?? '',
      });
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [booking.update, watch]);

  useEffect(() => {
    if (!profile.data) return;

    const values = getValues();
    const gender = profile.data.gender.trim().toLowerCase() === 'nữ' ? 'female' : 'male';
    const autofill: Partial<BookingFormValues> = {
      patientName: values.patientName || profile.data.full_name,
      patientPhone: values.patientPhone || profile.data.phone,
      patientDob: values.patientDob || profile.data.dob,
      patientGender: values.patientGender || gender,
      patientAddress: values.patientAddress || profile.data.address || '',
    };

    Object.entries(autofill).forEach(([field, value]) => {
      setValue(field as keyof BookingFormValues, value, { shouldValidate: false });
    });
  }, [getValues, profile.data, setValue]);

  const submitBooking = async (values: BookingFormValues) => {
    setSubmitting(true);
    setSubmitError('');

    const payload: BookingData = {
      patientName: values.patientName,
      patientPhone: values.patientPhone,
      patientEmail: '',
      patientDob: values.patientDob,
      patientGender: values.patientGender,
      patientAddress: values.patientAddress,
      symptoms: '',
      facilityId: values.facilityId,
      specialtyId: doctors.data?.find((doctor) => doctor.id === values.doctorId)?.specialtyId ?? '',
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

  if (facilities.isLoading || doctors.isLoading) {
    return <StatePanel kind="loading" title="Đang chuẩn bị biểu mẫu đặt lịch" />;
  }

  if (facilities.isError || doctors.isError) {
    return (
      <StatePanel
        kind="offline"
        title="Không thể tải dữ liệu đặt lịch"
        onRetry={() => {
          void facilities.refetch();
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
          <legend>Thông tin cá nhân</legend>
          {authService.isAuthenticated() && (
            <p className={styles.profileNotice}>
              {profile.isLoading
                ? 'Đang lấy thông tin từ hồ sơ bệnh nhân...'
                : profile.isError
                  ? 'Không thể tự điền hồ sơ. Bạn vẫn có thể nhập thông tin bên dưới.'
                  : 'Thông tin đã được điền từ hồ sơ. Bạn có thể chỉnh sửa nếu cần.'}
            </p>
          )}
          <label className={styles.fullWidth}>
            <span className={styles.labelText}>Họ tên <em className={styles.required}>*</em></span>
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
              <span className={styles.labelText}>Ngày sinh <em className={styles.required}>*</em></span>
              <input {...register('patientDob')} type="date" />
              {errors.patientDob && <small>{errors.patientDob.message}</small>}
            </label>
          </div>

          <div className={styles.genderGroup}>
            <span className={styles.labelText}>Giới tính <em className={styles.required}>*</em></span>
            <div>
              <label><input {...register('patientGender')} type="radio" value="male" /> Nam</label>
              <label><input {...register('patientGender')} type="radio" value="female" /> Nữ</label>
            </div>
            {errors.patientGender && <small>{errors.patientGender.message}</small>}
          </div>

          <label className={styles.fullWidth}>
            <span className={styles.labelText}>Địa chỉ <em className={styles.required}>*</em></span>
            <textarea
              {...register('patientAddress')}
              rows={2}
              placeholder="Nhập địa chỉ hiện tại"
            />
            {errors.patientAddress && <small>{errors.patientAddress.message}</small>}
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
                  setValue('date', '');
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
            <span className={styles.labelText}>Bác sĩ <em className={styles.required}>*</em></span>
            <select
              {...register('doctorId', {
                onChange: () => {
                  setValue('date', '');
                  setValue('time', '');
                },
              })}
              disabled={!selectedFacility}
            >
              <option value="">Chọn bác sĩ</option>
              {availableDoctors.map((doctor) => (
                <option key={doctor.id} value={doctor.id}>
                  {doctor.title} {doctor.name}
                </option>
              ))}
            </select>
            {errors.doctorId && <small>{errors.doctorId.message}</small>}
          </label>

          <div className={styles.twoColumns}>
            <label>
              <span className={styles.labelText}>Ngày khám <em className={styles.required}>*</em></span>
              <select
                {...register('date', {
                  onChange: () => setValue('time', ''),
                })}
                disabled={!selectedDoctor}
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
