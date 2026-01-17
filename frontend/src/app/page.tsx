/**
 * ReviewSignal 7.0 - Landing Page (Redirect to Dashboard)
 */

import { redirect } from 'next/navigation';

export default function HomePage() {
  redirect('/dashboard');
}
