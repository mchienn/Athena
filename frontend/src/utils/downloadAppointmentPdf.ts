export async function downloadAppointmentPdf(
  element: HTMLElement,
  appointmentCode: string,
): Promise<void> {
  await document.fonts.ready;
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import('html2canvas'),
    import('jspdf'),
  ]);
  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
    backgroundColor: '#ffffff',
    logging: false,
  });
  const pdf = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const margin = 12;
  const availableWidth = pageWidth - margin * 2;
  const availableHeight = pageHeight - margin * 2;
  const imageRatio = canvas.height / canvas.width;
  let imageWidth = availableWidth;
  let imageHeight = imageWidth * imageRatio;
  if (imageHeight > availableHeight) {
    imageHeight = availableHeight;
    imageWidth = imageHeight / imageRatio;
  }
  pdf.addImage(
    canvas.toDataURL('image/png'),
    'PNG',
    (pageWidth - imageWidth) / 2,
    margin,
    imageWidth,
    imageHeight,
    undefined,
    'FAST',
  );
  pdf.save(`phieu-lich-kham-${appointmentCode}.pdf`);
}
