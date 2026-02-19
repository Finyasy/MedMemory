/**
 * Clinician portal entry: single page only (per DOCTOR_DASHBOARD_REPORT.dm).
 * Renders ClinicianDashboardPage which includes login/signup, patient list,
 * upload queue, and patient workspace (documents, records, technical chat).
 */
import ClinicianDashboardPage from './ClinicianDashboardPage';

export default function ClinicianApp() {
  return <ClinicianDashboardPage />;
}
