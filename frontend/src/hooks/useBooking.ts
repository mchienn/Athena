import { useCallback, useState } from 'react';
import type { BookingData } from '../types';

const initialData: BookingData = { facilityId: '', specialtyId: '', doctorId: '', date: '', time: '', patientName: '', patientPhone: '', patientEmail: '', patientDob: '', patientGender: '', patientAddress: '', symptoms: '' };

export function useBooking() {
  const [step, setStep] = useState(1);
  const [data, setData] = useState<BookingData>(() => {
    const stored = sessionStorage.getItem('booking-draft');
    return stored ? { ...initialData, ...JSON.parse(stored) as Partial<BookingData> } : initialData;
  });
  const update = useCallback((values: Partial<BookingData>) => setData((current) => {
    const next = { ...current, ...values };
    sessionStorage.setItem('booking-draft', JSON.stringify(next));
    return next;
  }), []);
  const next = () => setStep((current) => Math.min(6, current + 1));
  const previous = () => setStep((current) => Math.max(1, current - 1));
  const reset = () => { setData(initialData); setStep(1); sessionStorage.removeItem('booking-draft'); };
  return { step, data, update, next, previous, reset, setStep };
}
