export interface Facility { id: string; name: string; shortName: string; address: string; phone: string; hours: string; image: string; }
export interface Specialty { id: string; name: string; description: string; icon: string; doctorCount: number; }
export interface Doctor { id: string; name: string; title: string; specialtyId: string; specialty: string; experience: number; rating: number; reviews: number; facilityId: string; image: string; languages: string[]; education: string[]; about: string; }
export interface TimeSlot { id: string; time: string; status: 'available' | 'full' | 'just_booked'; }
export interface ScheduleDay { date: string; label: string; slots: TimeSlot[]; }
export interface PriceItem { id: string; category: string; service: string; code: string; price: number; insurance: boolean; }
export interface Appointment { id: string; code: string; doctorName: string; specialty: string; facilityName: string; date: string; time: string; status: 'upcoming' | 'completed' | 'cancelled'; patientName: string; }
export interface BookingData { facilityId: string; specialtyId: string; doctorId: string; date: string; time: string; patientName: string; patientPhone: string; patientEmail: string; patientDob: string; patientGender: 'male' | 'female' | 'other' | ''; patientAddress: string; symptoms: string; }
export type AssistantIntent = 'general' | 'find_doctor' | 'schedule' | 'pricing' | 'guide' | 'emergency';
export interface AssistantAction { id: string; label: string; href?: string; value?: string; }
export interface Citation { title: string; url: string; }
export interface AssistantStructuredData { doctors?: Doctor[]; schedules?: ScheduleDay[]; prices?: PriceItem[]; checklist?: string[]; }
export interface AssistantMessage { id: string; role: 'user' | 'assistant'; intent: AssistantIntent; answer: string; actions: AssistantAction[]; structured_data: AssistantStructuredData; emergency: boolean; citations: Citation[]; }
export interface ChatSummary { id: string; title: string; createdAt: number; updatedAt: number; }
export interface ApiErrorShape { status: number; code: string; message: string; }
